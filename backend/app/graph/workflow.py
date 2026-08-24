"""研判工作流（LangGraph）：意图 → 画像澄清 → 需求重写/拆解 → 专家 DAG → 整合。

静态节点 + 动态参与：拆解器从角色库选中 state.roles，未选中的节点透传（reducer 合并）。
DAG 边由各专家的 depends_on 构成，全部喂给整合专家。
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..agents import ALL_ROLES, EXECUTIVE_ROLE, get_agent
from .nodes.research import (
    _make_expert_node,
    final_node,
    intent_node,
    plan_node,
    rewrite_node,
)
from .state import ResearchState


def build_workflow():
    g = StateGraph(ResearchState)
    g.add_node("intent", intent_node)
    g.add_node("plan", plan_node)
    g.add_node("rewrite", rewrite_node)
    for role in ALL_ROLES:
        g.add_node(role, _make_expert_node(role))
    g.add_node(EXECUTIVE_ROLE, _make_expert_node(EXECUTIVE_ROLE))
    g.add_node("final", final_node)

    g.add_edge(START, "intent")
    g.add_edge("intent", "plan")

    def _route_plan(s):
        if s.get("clarification") or s.get("mode") == "chat":
            return "final"
        return "rewrite"

    g.add_conditional_edges("plan", _route_plan)

    def _next_role(state: ResearchState) -> str:
        roles = state.get("roles") or []
        completed = set(state.get("results") or {})
        if EXECUTIVE_ROLE in completed:
            return "final"
        for role in roles:
            if role != EXECUTIVE_ROLE and role not in completed:
                return role
        return EXECUTIVE_ROLE

    g.add_conditional_edges("rewrite", _next_role)
    for role in ALL_ROLES:
        g.add_conditional_edges(role, _next_role)
    g.add_conditional_edges(EXECUTIVE_ROLE, _next_role)
    g.add_edge("final", END)

    return g.compile()


workflow = build_workflow()


def run_research(query: str, project_ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """一次研判请求 = 一个工作流 DAG。返回最终 state（含 final / evidence）。"""
    initial: dict[str, Any] = {
        "query": query,
        "project_ctx": project_ctx or {},
        "mode": "research",
        "rewritten": None,
        "roles": [],
        "results": {},
        "upstream": {},
        "clarification": None,
        "final": None,
    }
    return workflow.invoke(initial)
