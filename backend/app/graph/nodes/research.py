"""研判工作流节点：意图识别 → 画像澄清 → 需求重写/任务拆解 → 专家 DAG → 汇总。

用户一次需求 = 一个工作流：判断是否需补充画像 → 重写统一任务标题 →
从专家角色库自动拆解匹配 → 按 depends_on 构成 DAG 并行执行 → 整合输出。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langgraph.config import get_stream_writer

from ...agents import (
    AGENTS,
    CATALOG,
    EXECUTIVE_ROLE,
    ExpertContext,
    ExpertResult,
    get_agent,
    topo_order,
)
from ...db import SessionLocal
from ...llm import LLMError, get_client

logger = logging.getLogger("chuhai.workflow")

CHAT_KEYWORDS = ["你好", "你是谁", "能做什么", "谢谢", "介绍一下", "help"]
CHAT_SYSTEM = "你是出海参谋（跨境出海决策智能体）。请用中文简洁回答，非市场研判问题不调用数据。"

# 规则兜底：关键词 → 主分析角色（LLM 拆解失败时用）
_FALLBACK_RULES: dict[str, list[str]] = {
    "demand_researcher": ["需求", "趋势", "搜索量", "增长"],
    "competitive_analyst": ["竞争格局", "格局", "竞争"],
    "price_band_analyst": ["价格带", "价格分布", "价格分位"],
    "feedback_analyst": ["差评", "评论", "口碑", "痛点", "根因"],
    "cost_modeler": ["成本", "毛利", "地板", "供应链", "运费"],
    "competitor_benchmark": ["竞品", "对标", "对手"],
    "pricing_optimizer": ["定价", "价格", "价位", "怎么定价"],
    "selling_point_analyst": ["卖点", "差异化", "优势"],
    "search_gap_analyst": ["搜索词", "流量", "关键词", "空白"],
    "selection_score": ["选品", "机会", "能不能做", "值得做", "要不要", "能不能"],
    "strategy_node": ["打法", "竞争打法", "策略"],
}
_DEFAULT_ROLES = ["selection_score", "pricing_optimizer", "strategy_node"]


def _fallback_roles(query: str) -> list[str]:
    matched = [role for role, kws in _FALLBACK_RULES.items() if any(kw in query for kw in kws)]
    return matched or list(_DEFAULT_ROLES)


def _with_deps(roles: list[str]) -> list[str]:
    """补全 depends_on 依赖，保证收口节点有上游输入。"""
    result = set(roles)
    changed = True
    while changed:
        changed = False
        for r in list(result):
            for dep in AGENTS[r].depends_on:
                if dep not in result:
                    result.add(dep)
                    changed = True
    return [r for r in AGENTS if r in result and r != EXECUTIVE_ROLE]


def intent_node(state: dict[str, Any]) -> dict[str, Any]:
    if any(kw in state["query"] for kw in CHAT_KEYWORDS):
        logger.info("intent=chat query=%r", state["query"])
        return {"mode": "chat", "roles": [], "rewritten": None}
    logger.info("intent=research query=%r", state["query"])
    return {"mode": "research"}


def plan_node(state: dict[str, Any]) -> dict[str, Any]:
    """画像澄清：数据专家都需要品类+市场前提，缺了就反问（只问数据里没有的）。"""
    if state["mode"] == "chat":
        return {"clarification": None}
    ctx = state["project_ctx"] or {}
    if not ctx.get("category_id") or not ctx.get("market_code"):
        logger.info("plan=clarification(缺品类/市场) ctx=%s", ctx)
        return {"clarification": "本次研判需要先确认两个前提：面向哪个品类、哪个目标市场？（例如：TWS 耳机 / 美国站 / 印度尼西亚）"}
    logger.info("plan=proceed ctx=%s", ctx)
    return {"clarification": None}


def rewrite_node(state: dict[str, Any]) -> dict[str, Any]:
    """需求重写 + 任务拆解：LLM 从角色库选主分析角色 + 生成统一任务标题。"""
    query = state["query"]
    ctx = state["project_ctx"] or {}
    llm = get_client()
    catalog_lines = "\n".join(f"- {c['name']}（{c['role']}）：{c['desc']}" for c in CATALOG)
    system = (
        "你是跨境市场洞察系统的任务拆解器。用户一次需求 = 一个工作流。\n"
        "① 把用户需求改写为一句统一任务标题（含市场/品类 + 意图）；\n"
        "② 从专家角色清单中选择完成该任务所需的主分析角色（可多选，选最贴合的，别全选；"
        "选品/定价/打法类收口节点会自动补上其依赖）。\n"
        f"专家角色清单：\n{catalog_lines}\n"
        '只输出 JSON：{"rewritten": "统一任务标题", "roles": ["role1", "role2"]}。roles 只从清单选，不编造。'
    )
    scope_label = ctx.get("name") or f"{ctx.get('category_id') or '待定品类'}/{ctx.get('market_code') or '?'}"
    user = f"项目范围：{scope_label}\n用户需求：{query}"
    data = llm.complete_json([{"role": "user", "content": user}], system=system, temperature=0)
    roles = [r for r in data.get("roles", []) if r in AGENTS and r != EXECUTIVE_ROLE]
    if not roles:
        roles = _fallback_roles(query)
    roles = topo_order(_with_deps(roles)) + [EXECUTIVE_ROLE]
    rewritten = (data.get("rewritten") or "").strip() or f"{scope_label} {query}"
    logger.info("rewrite=%s roles=%s", rewritten, roles)
    return {"rewritten": rewritten, "roles": roles}


def _make_expert_node(role: str):
    agent = get_agent(role)

    def node(state: dict[str, Any]) -> dict[str, Any]:
        if role != EXECUTIVE_ROLE and role not in state["roles"]:
            return {}  # 未选中，透传
        t0 = time.monotonic()
        writer = get_stream_writer()  # 自定义流事件 → SSE 逐专家展示进度
        writer({"type": "expert_start", "role": role})
        with SessionLocal() as db:
            ctx = ExpertContext(
                query=state["query"],
                project_ctx=state["project_ctx"] or {},
                upstream=state.get("upstream") or {},
            )
            result: ExpertResult = agent.run(db, ctx)
        elapsed = (time.monotonic() - t0) * 1000
        writer({"type": "expert_done", "role": role, "error": result.error})
        logger.info(
            "expert=%s done elapsed=%dms evidence=%d skipped=%d error=%s",
            role, int(elapsed), len(result.evidence), len(result.skipped), result.error,
        )
        return {"results": {role: result.as_dict()}, "upstream": {role: result.conclusion}}

    return node


def final_node(state: dict[str, Any]) -> dict[str, Any]:
    if state["mode"] == "chat":
        try:
            answer = get_client().complete(
                [{"role": "user", "content": state["query"]}], system=CHAT_SYSTEM
            )
        except LLMError as exc:
            answer = f"（LLM 未配置，无法回答）{exc}"
        return {"final": {"mode": "chat", "answer": answer}}

    if state.get("clarification"):
        return {"final": {"mode": "research", "clarification": state["clarification"]}}

    results: dict[str, Any] = state["results"]
    roles = state["roles"]
    sections = {r: results[r] for r in roles if r in results}
    evidence = [
        e
        for r in roles
        for e in (results[r].get("evidence") or [])
        if r in results
    ]
    conclusion = sections.get(EXECUTIVE_ROLE, {}).get("conclusion")
    return {
        "final": {
            "mode": "research",
            "rewritten": state.get("rewritten"),
            "answer": conclusion,
            "sections": sections,
            "evidence": evidence,
            "roles": roles,
        }
    }
