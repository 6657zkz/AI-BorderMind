from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from app.domain.capabilities.contracts import CapabilityCatalog, InputRequirement, TaskContractDefinition

from .decision_graph import DecisionGraph
from .execution_plan import ExecutionPlan, InputBinding, PlanNode
from .outcomes import (
    ClarificationRequest,
    NeedsClarification,
    Planned,
    PlanningIssue,
    Rejected,
    ValidDecisionGraph,
)

Value = Any


def compile_execution_plan(
    validated_graph: ValidDecisionGraph,
    project_profile: Mapping[str, Value],
    catalog: CapabilityCatalog,
) -> Planned | NeedsClarification | Rejected:
    """将已验证业务图和项目画像确定性编译为唯一可执行的 DAG。

    Args:
        validated_graph: 已通过 ``DecisionGraph.validate`` 的业务图包装对象。
        project_profile: 编译时可用于补全非 Graph 输入的项目画像值；该函数不会修改它。
        catalog: 与业务图版本对应的只读能力目录。

    Returns:
        输入和依赖均完整时返回 Planned；缺少可澄清字段时返回 NeedsClarification；
        目录、依赖或不可澄清输入无效时返回 Rejected。
    """
    # graph 是本次编译的业务语义真源，不从外部重新识别决策类型。
    graph = validated_graph.graph
    # decision_type 给出可展开的任务蓝图和决策类型级限制。
    decision_type = catalog.get_decision_type(graph.decision_type_id)
    if decision_type is None or not decision_type.enabled:
        return Rejected(
            (
                PlanningIssue(
                    code="unavailable_decision_type",
                    path="decision_type_id",
                    message="Selected decision type is unavailable for compilation.",
                    related_catalog_id=graph.decision_type_id,
                ),
            )
        )

    # contracts 只包含该决策类型声明的任务，issues 记录任务引用本身的问题。
    contracts, issues = _resolve_contracts(decision_type.task_contract_ids, catalog)
    if issues:
        return Rejected(tuple(issues))

    # 检查任务之间的依赖和它们引用的能力是否均在目录中注册。
    issues = _validate_contracts(contracts, catalog)
    if issues:
        return Rejected(tuple(issues))

    # topological_task_ids 是执行器可据以安排依赖顺序的稳定任务 ID 序列。
    topological_task_ids = _topological_order(contracts)
    if isinstance(topological_task_ids, Rejected):
        return topological_task_ids

    # clarifications 收集用户可补充的缺失输入；bindings_by_task 保存每个节点的受控输入来源。
    clarifications: list[ClarificationRequest] = []
    bindings_by_task: dict[str, tuple[InputBinding, ...]] = {}
    for task_id in topological_task_ids:
        contract = contracts[task_id]
        bindings, missing = _bind_inputs(contract, graph, project_profile, contracts)
        bindings_by_task[task_id] = tuple(bindings)
        clarifications.extend(
            ClarificationRequest(
                key=requirement.key,
                reason_code="missing_required_input",
                decision_type_id=graph.decision_type_id,
                task_id=task_id,
                accepted_value_shape=requirement.accepted_value_shape,
                blocks_all_planning=len(contracts) == 1,
            )
            for requirement in missing
            if requirement.clarifiable
        )
        issues.extend(
            PlanningIssue(
                code="missing_required_input",
                path=f"tasks.{task_id}.inputs.{requirement.key}",
                message="Task requires an input that cannot be clarified.",
                related_catalog_id=task_id,
            )
            for requirement in missing
            if not requirement.clarifiable
        )

    if issues:
        return Rejected(tuple(issues))
    if clarifications:
        return NeedsClarification(tuple(clarifications))

    # nodes 保留拓扑顺序，未来运行模块只可消费这些经编译的节点定义。
    nodes = tuple(
        _build_node(task_id, contracts[task_id], bindings_by_task[task_id]) for task_id in topological_task_ids
    )
    return Planned(
        ExecutionPlan(
            plan_id=f"{graph.graph_id}:plan",
            source_graph_id=graph.graph_id,
            catalog_version=graph.catalog_version,
            project_profile_snapshot=deepcopy(dict(project_profile)),
            nodes=nodes,
            topological_node_ids=topological_task_ids,
        )
    )


def _resolve_contracts(
    task_ids: tuple[str, ...], catalog: CapabilityCatalog
) -> tuple[dict[str, TaskContractDefinition], list[PlanningIssue]]:
    """从目录解析决策类型声明的任务，并报告重复或未知任务。

    Args:
        task_ids: 决策类型蓝图中按声明顺序列出的任务 ID。
        catalog: 用于查询任务契约的只读能力目录。

    Returns:
        第一个元素为按 ID 索引的已解析任务契约；第二个元素为重复或未知任务问题。
    """
    contracts: dict[str, TaskContractDefinition] = {}
    issues: list[PlanningIssue] = []
    for task_id in task_ids:
        if task_id in contracts:
            issues.append(
                PlanningIssue(
                    code="duplicate_task_contract",
                    path="decision_type.task_contract_ids",
                    message="Decision type contains the same task contract more than once.",
                    related_catalog_id=task_id,
                )
            )
            continue
        contract = catalog.get_task_contract(task_id)
        if contract is None:
            issues.append(
                PlanningIssue(
                    code="unknown_task_contract",
                    path="decision_type.task_contract_ids",
                    message="Decision type references an unregistered task contract.",
                    related_catalog_id=task_id,
                )
            )
            continue
        contracts[task_id] = contract
    return contracts, issues


def _validate_contracts(
    contracts: Mapping[str, TaskContractDefinition], catalog: CapabilityCatalog
) -> list[PlanningIssue]:
    """验证任务依赖、Operator 和专家角色均属于选定能力目录。

    Args:
        contracts: 当前决策类型已解析的任务契约，以任务 ID 为键。
        catalog: 用于检查任务所引用能力是否存在的只读目录。

    Returns:
        不在当前蓝图中的依赖或未注册能力对应的问题列表。
    """
    issues: list[PlanningIssue] = []
    for task_id, contract in contracts.items():
        for dependency_id in contract.dependencies:
            if dependency_id not in contracts:
                issues.append(
                    PlanningIssue(
                        code="unknown_task_dependency",
                        path=f"tasks.{task_id}.dependencies",
                        message="Task dependency is not part of the selected decision type.",
                        related_catalog_id=dependency_id,
                    )
                )
        for operator_id in sorted(contract.allowed_operator_ids):
            if not catalog.has_operator(operator_id):
                issues.append(
                    PlanningIssue(
                        code="unknown_operator",
                        path=f"tasks.{task_id}.allowed_operator_ids",
                        message="Task contract references an unregistered operator.",
                        related_catalog_id=operator_id,
                    )
                )
        for expert_role_id in sorted(contract.allowed_expert_role_ids):
            if not catalog.has_expert_role(expert_role_id):
                issues.append(
                    PlanningIssue(
                        code="unknown_expert_role",
                        path=f"tasks.{task_id}.allowed_expert_role_ids",
                        message="Task contract references an unregistered expert role.",
                        related_catalog_id=expert_role_id,
                    )
                )
    return issues


def _topological_order(
    contracts: Mapping[str, TaskContractDefinition],
) -> tuple[str, ...] | Rejected:
    """生成稳定拓扑序；没有可推进节点时返回依赖环错误。

    Args:
        contracts: 当前计划内的全部任务契约及其依赖关系。

    Returns:
        按依赖完成顺序排列的任务 ID 元组；检测到环时返回 Rejected。
    """
    # resolved 记录已被放入序列的任务；unresolved 保存尚未满足依赖的任务。
    resolved: list[str] = []
    unresolved = set(contracts)
    while unresolved:
        # ready 是当前所有依赖都已解析的节点；排序保证计划和测试结果稳定。
        ready = sorted(
            task_id
            for task_id in unresolved
            if all(dependency_id in resolved for dependency_id in contracts[task_id].dependencies)
        )
        if not ready:
            return Rejected(
                (
                    PlanningIssue(
                        code="cyclic_task_dependencies",
                        path="decision_type.task_contract_ids",
                        message="Task contracts contain a dependency cycle.",
                    ),
                )
            )
        resolved.extend(ready)
        unresolved.difference_update(ready)
    return tuple(resolved)


def _bind_inputs(
    contract: TaskContractDefinition,
    graph: DecisionGraph,
    project_profile: Mapping[str, Value],
    contracts: Mapping[str, TaskContractDefinition],
) -> tuple[list[InputBinding], list[InputRequirement]]:
    """为任务的每个必需输入创建合法来源绑定或标记为缺失。

    Args:
        contract: 正在编译的任务契约。
        graph: 提供用户/事件范围、约束和上下文的业务图。
        project_profile: 可补充任务输入的项目画像。
        contracts: 当前决策类型的全部任务契约，用于查询上游输出字段。

    Returns:
        第一个列表为成功解析的输入绑定；第二个列表为尚无合法来源的输入声明。
    """
    bindings: list[InputBinding] = []
    missing: list[InputRequirement] = []
    for requirement in contract.input_requirements:
        binding = _find_input_binding(requirement.key, contract, graph, project_profile, contracts)
        if binding is None:
            missing.append(requirement)
        else:
            bindings.append(binding)
    return bindings, missing


def _find_input_binding(
    key: str,
    contract: TaskContractDefinition,
    graph: DecisionGraph,
    project_profile: Mapping[str, Value],
    contracts: Mapping[str, TaskContractDefinition],
) -> InputBinding | None:
    """按 Graph、项目画像、显式依赖输出的优先顺序解析一个输入来源。

    Args:
        key: 要绑定的任务输入字段名。
        contract: 消费该字段的任务契约，用于限定可用上游依赖。
        graph: 优先级最高的请求/事件业务输入。
        project_profile: Graph 未提供时可使用的项目级输入。
        contracts: 当前计划内任务契约，用于验证上游输出声明。

    Returns:
        找到受控来源时返回 InputBinding；所有合法来源均不存在时返回 None。
    """
    # Graph 中的显式请求值优先于项目画像默认值。
    for source_kind, source in (
        ("graph_scope", graph.scope),
        ("graph_constraint", graph.constraints),
        ("graph_context", graph.context_snapshot),
        ("project_profile", project_profile),
    ):
        if key in source:
            return InputBinding(input_key=key, source_kind=source_kind, source_key=key)

    # 仅允许从直接依赖且已声明的输出字段取值，禁止跨节点隐式读取。
    for dependency_id in contract.dependencies:
        dependency = contracts[dependency_id]
        if any(field.key == key for field in dependency.output_fields):
            return InputBinding(
                input_key=key,
                source_kind="upstream_output",
                source_key=key,
                source_node_id=dependency_id,
            )
    return None


def _build_node(task_id: str, contract: TaskContractDefinition, bindings: tuple[InputBinding, ...]) -> PlanNode:
    """把已验证的任务契约和输入绑定转换为不可变计划节点。

    Args:
        task_id: 当前任务的目录 ID，也是本计划中的节点 ID。
        contract: 提供能力白名单、输出字段和执行策略的任务契约。
        bindings: 编译阶段已解析完成的受控输入来源。

    Returns:
        可被未来运行模块调度的 PlanNode；此函数不执行节点。
    """
    return PlanNode(
        node_id=task_id,
        task_contract_id=task_id,
        purpose=contract.purpose,
        depends_on=contract.dependencies,
        allowed_operator_ids=contract.allowed_operator_ids,
        allowed_expert_role_ids=contract.allowed_expert_role_ids,
        input_bindings=bindings,
        quality_requirements=contract.quality_requirements,
        failure_policy=contract.failure_policy,
        skip_policy=contract.skip_policy,
        clarification_policy=contract.clarification_policy,
        retry_policy=contract.retry_policy,
        output_fields=tuple((field.key, field.semantic_type, field.required) for field in contract.output_fields),
        evidence_requirements=contract.evidence_requirements,
    )
