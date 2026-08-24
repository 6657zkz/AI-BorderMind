"""Role 层专家基类。

一个专家 = 工作流 DAG 的一个节点 {role, task, needs_data, 算子清单, depends_on}。
数据获取走固定算子（params 从项目上下文补齐，缺的算子跳过由 graph 触发画像澄清），
LLM 只做推理产出结论；每次推理的算子结果即证据链输入。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from ..llm import LLMClient, get_client
from ..operators import OperatorError, OperatorResult, get_operator

logger = logging.getLogger("chuhai.workflow")

_MAX_ROWS_IN_PROMPT = 20


@dataclass
class ExpertContext:
    query: str
    project_ctx: dict[str, Any]
    upstream: dict[str, Any] = field(default_factory=dict)  # key=role 的上游专家结论


@dataclass
class ExpertResult:
    role: str
    conclusion: dict[str, Any]
    evidence: list[OperatorResult]
    skipped: list[dict] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "conclusion": self.conclusion,
            "evidence": [e.as_dict() for e in self.evidence],
            "skipped": self.skipped,
            "error": self.error,
        }


_JSON_OUTPUT_REQ = (
    "基于给定的数据与项目上下文，给出结构化结论 JSON："
    '{"summary": "一句话结论", "arguments": ["论据1（引用具体数据）", ...], '
    '"recommendation": "可执行建议", "risks": ["风险1", ...]}。'
    "只输出 JSON，不要解释。数据不足时在 summary 里明确说明缺什么。"
)


class ExpertAgent:
    role: ClassVar[str]
    display_name: ClassVar[str]
    description: ClassVar[str]
    task: ClassVar[str]
    system_prompt: ClassVar[str] = ""  # 富人格提示词（身份/使命/规则/工作流）；缺省用 task
    needs_data: ClassVar[bool] = True
    # 元素为算子名，或 (算子名, 参数提示) —— 参数提示补齐项目上下文没有的必需参数（如 signal_type）
    operators: ClassVar[list] = []
    depends_on: ClassVar[list[str]] = []

    # ---- 数据获取：固定算子 ----
    def query_data(self, db: Session, ctx: ExpertContext) -> tuple[list[OperatorResult], list[dict]]:
        results: list[OperatorResult] = []
        skipped: list[dict] = []
        product_ids = (ctx.project_ctx.get("profile") or {}).get("product_ids") or []
        for spec in self.operators:
            op_name, hints = spec if isinstance(spec, tuple) else (spec, {})
            op = get_operator(op_name)
            params = {k: v for k, v in ctx.project_ctx.items() if k in op.param_schema.model_fields}
            params.update(hints)
            if "product_id" in op.param_schema.model_fields:
                # 产品级算子：按项目锁定的竞品循环取数（打法分析依赖）
                if not product_ids:
                    skipped.append({"operator": op_name, "reason": "项目未指定竞品（打法分析需要）"})
                    continue
                for pid in product_ids[:3]:
                    try:
                        results.append(op.execute(db, **{**params, "product_id": pid}))
                    except OperatorError as exc:
                        skipped.append({"operator": op_name, "reason": str(exc)})
                continue
            if not params:
                skipped.append({"operator": op_name, "reason": "项目上下文缺少必要实体参数"})
                continue
            try:
                results.append(op.execute(db, **params))
            except OperatorError as exc:
                skipped.append({"operator": op_name, "reason": str(exc)})
        return results, skipped

    # ---- 推理：LLM 只使用数据、产出结构化结论 ----
    def run(self, db: Session, ctx: ExpertContext, llm: LLMClient | None = None) -> ExpertResult:
        evidence: list[OperatorResult] = []
        skipped: list[dict] = []
        if self.needs_data:
            evidence, skipped = self.query_data(db, ctx)
            logger.info(
                "  %s 取数: operators=%d rows=%s skipped=%d",
                self.role, len(evidence),
                [len(e.rows) for e in evidence], len(skipped),
            )
        t0 = time.monotonic()
        try:
            client = llm or get_client()
            conclusion = self._reason(client, ctx, evidence)
        except Exception as exc:
            logger.warning("  %s LLM 推理失败: %s", self.role, exc)
            return ExpertResult(role=self.role, 
                                conclusion={}, 
                                evidence=evidence,
                                skipped=skipped, 
                                error=f"专家推理失败: {exc}")
        logger.info("  %s LLM 推理 done %dms conclusion_len=%d", 
                    self.role,
                    int((time.monotonic() - t0) * 1000), 
                    len(json.dumps(conclusion, ensure_ascii=False)))
        return ExpertResult(role=self.role, 
                            conclusion=conclusion,
                            evidence=evidence, 
                            skipped=skipped)

    def _reason(self, llm: LLMClient, ctx: ExpertContext, evidence: list[OperatorResult]) -> dict:
        persona = self.system_prompt or f"你是{self.display_name}（{self.role}）。任务：{self.task}"
        system = f"{persona}\n\n{_JSON_OUTPUT_REQ}"
        data_lines = []
        for e in evidence:
            data_lines.append(
                f"### {e.operator} (params={json.dumps(e.params, ensure_ascii=False)}, {e.elapsed_ms}ms)\n"
                f"```\n{json.dumps(e.rows[: _MAX_ROWS_IN_PROMPT], ensure_ascii=False, indent=1)}\n```"
            )
        user = (
            f"用户查询：{ctx.query}\n"
            f"项目上下文：{json.dumps(ctx.project_ctx, ensure_ascii=False)}\n\n"
        )
        if data_lines:
            user += "参考数据（算子执行结果）：\n" + "\n".join(data_lines)
        if ctx.upstream:
            user += (
                "\n上游专家结论：\n"
                + json.dumps(ctx.upstream, ensure_ascii=False)
            )
        return llm.complete_json([{"role": "user", "content": user}], system=system, temperature=0)
