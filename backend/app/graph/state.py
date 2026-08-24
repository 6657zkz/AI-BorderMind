"""工作流状态：LangGraph StateGraph 的 TypedDict。"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict


def _merge_dict(a: dict | None, b: dict | None) -> dict:
    if a is None:
        return b or {}
    if b is None:
        return a
    return {**a, **b}


class ResearchState(TypedDict, total=False):
    query: str
    project_ctx: dict[str, Any]
    mode: str                       # research / chat
    rewritten: str | None           # 统一任务标题（重写需求产出）
    roles: list[str]                # 本次选中的专家（拆解器产出）
    results: Annotated[dict[str, Any], _merge_dict]    # role -> ExpertResult.as_dict()
    upstream: Annotated[dict[str, Any], _merge_dict]   # role -> conclusion
    clarification: str | None       # 画像澄清问题（缺品类/市场时）
    final: dict[str, Any] | None    # 汇总结论
    error: str | None
