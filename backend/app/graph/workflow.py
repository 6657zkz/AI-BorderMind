"""研判工作流：意图、范围澄清、受控规划、ExecutionPlan 运行和结论汇总。"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from .nodes.research import execute_node, final_node, intent_node, plan_node, rewrite_node
from .state import ResearchState


def build_workflow():
    graph = StateGraph(ResearchState)
    graph.add_node("intent", intent_node)
    graph.add_node("plan", plan_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("execute", execute_node)
    graph.add_node("final", final_node)

    graph.add_edge(START, "intent")
    graph.add_edge("intent", "plan")

    def route_plan(state: ResearchState) -> str:
        if state.get("clarification") or state.get("mode") == "chat":
            return "final"
        return "rewrite"

    def route_rewrite(state: ResearchState) -> str:
        return "final" if state.get("clarification") else "execute"

    graph.add_conditional_edges("plan", route_plan)
    graph.add_conditional_edges("rewrite", route_rewrite)
    graph.add_edge("execute", "final")
    graph.add_edge("final", END)
    return graph.compile()


workflow = build_workflow()


def run_research(
    query: str,
    project_ctx: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    initial: dict[str, Any] = {
        "query": query,
        "run_id": run_id,
        "project_ctx": project_ctx or {},
        "history": history or [],
        "mode": "research",
        "decision_graph": None,
        "execution_plan": None,
        "clarifications": [],
        "roles": [],
        "results": {},
        "upstream": {},
        "clarification": None,
        "final": None,
    }
    return workflow.invoke(initial)
