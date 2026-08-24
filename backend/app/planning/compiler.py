from __future__ import annotations

from collections import deque

from .catalog import CAPABILITIES, GOALS, KNOWN_ENTITIES, KNOWN_METRICS
from .contracts import (
    ClarificationNeed,
    DecisionGraph,
    DecisionNodeKind,
    ExecutionPlan,
    NodeSource,
    PlanNode,
    PlanningError,
)

_MAX_PLAN_NODES = 16


def compile_plan(graph: DecisionGraph, profile: dict | None = None) -> ExecutionPlan:
    profile = profile or {}
    goals = graph.refs(DecisionNodeKind.GOAL)
    unknown_goals = goals - GOALS.keys()
    if unknown_goals:
        raise PlanningError(f"未注册目标: {sorted(unknown_goals)}")

    unknown_metrics = graph.refs(DecisionNodeKind.METRIC) - KNOWN_METRICS
    if unknown_metrics:
        raise PlanningError(f"未注册指标: {sorted(unknown_metrics)}")

    unknown_entities = graph.refs(DecisionNodeKind.ENTITY) - KNOWN_ENTITIES
    if unknown_entities:
        raise PlanningError(f"未注册实体: {sorted(unknown_entities)}")

    requested = graph.refs(DecisionNodeKind.CAPABILITY)
    unknown_capabilities = requested - CAPABILITIES.keys()
    if unknown_capabilities:
        raise PlanningError(f"未注册能力: {sorted(unknown_capabilities)}")

    selected = set(requested)
    for goal in goals:
        selected.update(GOALS[goal].required_capabilities)

    _expand_dependencies(selected)
    if len(selected) + 1 > _MAX_PLAN_NODES:
        raise PlanningError("执行计划超过最大节点数")

    ordered = _topological_capabilities(selected)
    plan_nodes = [
        PlanNode(
            id=capability_id,
            capability_id=capability_id,
            depends_on=[dep for dep in CAPABILITIES[capability_id].requires if dep in selected],
            source=NodeSource.USER if capability_id in requested else NodeSource.COMPILER,
            data_requirements=list(CAPABILITIES[capability_id].data_requirements),
            explanation="用户请求的能力" if capability_id in requested else "由目标蓝图或能力依赖自动补齐",
        )
        for capability_id in ordered
    ]

    terminal_nodes = [
        node.id
        for node in plan_nodes
        if not any(node.id in other.depends_on for other in plan_nodes)
    ]
    if "executive_expert" not in selected:
        plan_nodes.append(
            PlanNode(
                id="executive_expert",
                capability_id="executive_expert",
                depends_on=terminal_nodes,
                source=NodeSource.COMPILER,
                explanation="统一整合各目标的终结结论",
            )
        )

    return ExecutionPlan(
        goals=sorted(goals),
        nodes=plan_nodes,
        clarifications=_missing_clarifications(goals, profile),
    )


def _expand_dependencies(selected: set[str]) -> None:
    queue = deque(selected)
    while queue:
        capability_id = queue.popleft()
        for dependency in CAPABILITIES[capability_id].requires:
            if dependency not in selected:
                selected.add(dependency)
                queue.append(dependency)


def _topological_capabilities(selected: set[str]) -> list[str]:
    pending = set(selected)
    completed: set[str] = set()
    ordered: list[str] = []
    while pending:
        ready = sorted(
            capability_id
            for capability_id in pending
            if set(CAPABILITIES[capability_id].requires) <= completed
        )
        if not ready:
            raise PlanningError("能力目录存在循环依赖")
        ordered.extend(ready)
        completed.update(ready)
        pending.difference_update(ready)
    return ordered


def _missing_clarifications(goals: set[str], profile: dict) -> list[ClarificationNeed]:
    missing: list[ClarificationNeed] = []
    for goal in sorted(goals):
        for need in GOALS[goal].profile_requirements:
            if profile.get(need.field_id) in (None, ""):
                missing.append(need)
    return missing[:3]
