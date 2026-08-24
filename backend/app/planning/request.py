from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..project import extract_decision_parameters
from ..llm import get_client
from .catalog import CAPABILITIES, DECISION_TYPES, KNOWN_ENTITIES, KNOWN_METRICS
from .compiler import compile_plan
from .contracts import (
    DecisionGraph,
    DecisionNode,
    DecisionNodeKind,
    ExecutionPlan,
    NodeSource,
)


class JsonCompleter(Protocol):
    def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any: ...


@dataclass(frozen=True)
class PlannedRequest:
    title: str
    decision_graph: DecisionGraph
    execution_plan: ExecutionPlan


def plan_request(
    query: str,
    project_ctx: dict[str, Any] | None = None,
    *,
    llm: JsonCompleter | None = None,
) -> PlannedRequest:
    project_ctx = project_ctx or {}
    candidate = _candidate(query, project_ctx, llm or get_client())
    graph = _decision_graph(query, project_ctx, candidate)
    profile = {
        **dict(project_ctx.get("profile") or {}),
        **extract_decision_parameters(query),
    }
    return PlannedRequest(
        title=candidate["title"],
        decision_graph=graph,
        execution_plan=compile_plan(graph, profile),
    )


def _candidate(query: str, project_ctx: dict[str, Any], llm: JsonCompleter) -> dict[str, Any]:
    decision_types = "\n".join(
        f"- {definition.id}: {definition.name}"
        for definition in DECISION_TYPES.values()
        if all(CAPABILITIES[capability_id].planning_enabled for capability_id in definition.required_capabilities)
    )
    capabilities = "\n".join(
        f"- {definition.id}: {definition.name}（{definition.description}）"
        for definition in CAPABILITIES.values()
        if definition.planning_enabled
    )
    system = (
        "你是受控跨境经营决策规划器。只理解业务语义，不生成 SQL、不选择工具、"
        "不创建任务依赖。只能从下列稳定标识中选择决策类型和分析能力。\n"
        f"决策类型：\n{decision_types}\n"
        f"分析能力：\n{capabilities}\n"
        f"可引用实体：{sorted(KNOWN_ENTITIES)}\n"
        f"可引用指标：{sorted(KNOWN_METRICS)}\n"
        "若用户明确要求一个完整经营决策，优先选择决策类型；若只请求单项分析，可选择分析能力。"
        "只输出 JSON："
        '{"title":"中文任务标题","decision_types":["registered_id"],'
        '"capabilities":["registered_id"],"entities":["registered_id"],'
        '"metrics":["registered_id"]}。'
        "不要编造标识；每个数组可为空，但 decision_types 与 capabilities 至少一项非空。"
    )
    scope = {
        "category_id": project_ctx.get("category_id"),
        "market_code": project_ctx.get("market_code"),
        "profile": project_ctx.get("profile") or {},
    }
    raw = llm.complete_json(
        [{"role": "user", "content": f"项目范围：{scope}\n用户请求：{query}"}],
        system=system,
        temperature=0,
    )
    if not isinstance(raw, dict):
        raw = {}
    candidate = {
        "title": str(raw.get("title") or query).strip() or query,
        "decision_types": _string_list(raw.get("decision_types")),
        "capabilities": _string_list(raw.get("capabilities")),
        "entities": _string_list(raw.get("entities")),
        "metrics": _string_list(raw.get("metrics")),
    }
    if not candidate["decision_types"] and not candidate["capabilities"]:
        candidate["capabilities"] = [_fallback_capability(query)]
    return candidate


def _decision_graph(
    query: str,
    project_ctx: dict[str, Any],
    candidate: dict[str, Any],
) -> DecisionGraph:
    nodes: list[DecisionNode] = []
    for decision_type in candidate["decision_types"]:
        nodes.append(
            DecisionNode(
                id=f"decision_{decision_type}",
                kind=DecisionNodeKind.GOAL,
                ref=decision_type,
                source=NodeSource.USER,
            )
        )
    for capability in candidate["capabilities"]:
        nodes.append(
            DecisionNode(
                id=f"capability_{capability}",
                kind=DecisionNodeKind.CAPABILITY,
                ref=capability,
                source=NodeSource.USER,
            )
        )
    for entity in candidate["entities"]:
        nodes.append(
            DecisionNode(
                id=f"entity_{entity}",
                kind=DecisionNodeKind.ENTITY,
                ref=entity,
                source=NodeSource.COMPILER,
            )
        )
    for metric in candidate["metrics"]:
        nodes.append(
            DecisionNode(
                id=f"metric_{metric}",
                kind=DecisionNodeKind.METRIC,
                ref=metric,
                source=NodeSource.COMPILER,
            )
        )
    if project_ctx.get("market_code") and "market" not in candidate["entities"]:
        nodes.append(
            DecisionNode(
                id="entity_market",
                kind=DecisionNodeKind.ENTITY,
                ref="market",
                source=NodeSource.COMPILER,
            )
        )
    if project_ctx.get("category_id") and "category" not in candidate["entities"]:
        nodes.append(
            DecisionNode(
                id="entity_category",
                kind=DecisionNodeKind.ENTITY,
                ref="category",
                source=NodeSource.COMPILER,
            )
        )
    return DecisionGraph(query=query, nodes=nodes)


def _fallback_capability(query: str) -> str:
    if any(word in query for word in ("定价", "价格", "毛利", "成本")):
        return "pricing_optimizer"
    if any(word in query for word in ("需求", "趋势", "搜索量")):
        return "demand_researcher"
    if any(word in query for word in ("评论", "差评", "痛点")):
        return "feedback_analyst"
    if any(word in query for word in ("竞品", "对标", "竞争")):
        return "competitor_benchmark"
    return "selection_score"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(item for item in value if isinstance(item, str) and item))
