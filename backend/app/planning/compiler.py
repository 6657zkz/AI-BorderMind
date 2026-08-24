from __future__ import annotations

from collections import deque

from .catalog import ANALYSIS_TASKS, CAPABILITIES, DECISION_TYPES, KNOWN_ENTITIES, KNOWN_METRICS
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
    unknown_goals = goals - DECISION_TYPES.keys()
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

    if not goals and not requested:
        raise PlanningError("决策图必须至少引用一个决策类型或能力")

    selected = set(requested)
    for goal in goals:
        selected.update(DECISION_TYPES[goal].required_capabilities)

    _expand_dependencies(selected)
    disabled = sorted(
        capability_id
        for capability_id in selected
        if not CAPABILITIES[capability_id].planning_enabled
    )
    if disabled:
        raise PlanningError(f"当前未开放规划能力: {disabled}")
    if len(selected) + 1 > _MAX_PLAN_NODES:
        raise PlanningError("执行计划超过最大节点数")

    ordered = _topological_capabilities(selected)
    plan_nodes = [
        _plan_node(
            capability_id=capability_id,
            depends_on=[dependency for dependency in CAPABILITIES[capability_id].requires if dependency in selected],
            source=NodeSource.USER if capability_id in requested else NodeSource.COMPILER,
            explanation="用户请求的能力" if capability_id in requested else "由决策类型蓝图或能力依赖自动补齐",
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
            _plan_node(
                capability_id="executive_expert",
                depends_on=terminal_nodes,
                source=NodeSource.COMPILER,
                explanation="统一整合各决策类型的终结结论",
            )
        )

    return ExecutionPlan(
        goals=sorted(goals),
        nodes=plan_nodes,
        clarifications=_missing_clarifications(goals, profile),
    )


def _plan_node(
    *,
    capability_id: str,
    depends_on: list[str],
    source: NodeSource,
    explanation: str,
) -> PlanNode:
    capability = CAPABILITIES[capability_id]
    task = ANALYSIS_TASKS[capability.analysis_task_id]
    return PlanNode(
        id=capability.id,
        capability_id=capability.id,
        analysis_task_id=task.id,
        expert_role_id=capability.expert_role_id,
        data_capability_ids=list(capability.data_capability_ids),
        output_contract=list(task.required_outputs),
        depends_on=depends_on,
        source=source,
        data_requirements=list(capability.data_requirements),
        explanation=explanation,
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
        for need in DECISION_TYPES[goal].profile_requirements:
            if profile.get(need.field_id) in (None, ""):
                missing.append(need)
    return missing[:3]
