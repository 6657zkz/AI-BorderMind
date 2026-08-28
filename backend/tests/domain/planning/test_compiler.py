from app.domain.capabilities.contracts import TaskContractDefinition
from app.domain.planning import DecisionGraph, NeedsClarification, Planned, Rejected, compile_execution_plan


def test_compiler_builds_stable_dag(catalog, valid_graph):
    """验证编译器生成稳定拓扑序、并行节点和显式上游输入绑定。"""
    validation = valid_graph.validate(catalog)

    result = compile_execution_plan(validation, {"project_id": "project-1"}, catalog)

    assert isinstance(result, Planned)
    assert result.plan.topological_node_ids == ("margin-check", "price-band", "recommendation")
    nodes = {node.node_id: node for node in result.plan.nodes}
    assert nodes["margin-check"].depends_on == ()
    assert nodes["price-band"].depends_on == ()
    assert nodes["recommendation"].depends_on == ("price-band", "margin-check")
    assert {binding.source_node_id for binding in nodes["recommendation"].input_bindings} == {
        "price-band",
        "margin-check",
        None,
    }


def test_compiler_requests_clarification_for_missing_clarifiable_input(catalog, valid_graph):
    """验证可由用户补充的缺失字段产生结构化澄清请求。"""
    graph = DecisionGraph(**{**valid_graph.__dict__, "scope": {"market": "US", "cost_boundary": 20}})
    validation = graph.validate(catalog)

    result = compile_execution_plan(validation, {}, catalog)

    assert isinstance(result, NeedsClarification)
    assert [(request.task_id, request.key) for request in result.requests] == [
        ("recommendation", "target_margin")
    ]


def test_compiler_rejects_missing_non_clarifiable_input(catalog, valid_graph):
    """验证不可澄清的硬性缺失会阻止生成执行计划。"""
    graph = DecisionGraph(**{**valid_graph.__dict__, "scope": {"market": "US", "target_margin": 0.3}})
    validation = graph.validate(catalog)

    result = compile_execution_plan(validation, {}, catalog)

    assert isinstance(result, Rejected)
    assert result.issues[0].code == "missing_required_input"


def test_compiler_rejects_unknown_operator(catalog, valid_graph):
    """验证任务契约引用未注册 Operator 时会被拒绝。"""
    contract = catalog.task_contracts["price-band"]
    catalog.task_contracts["price-band"] = TaskContractDefinition(
        **{**contract.__dict__, "allowed_operator_ids": frozenset({"unknown-operator"})}
    )

    result = compile_execution_plan(valid_graph.validate(catalog), {}, catalog)

    assert isinstance(result, Rejected)
    assert result.issues[0].code == "unknown_operator"


def test_compiler_rejects_dependency_cycle(catalog, valid_graph):
    """验证任务依赖成环时不能生成 DAG。"""
    price_band = catalog.task_contracts["price-band"]
    margin = catalog.task_contracts["margin-check"]
    catalog.task_contracts["price-band"] = TaskContractDefinition(
        **{**price_band.__dict__, "dependencies": ("margin-check",)}
    )
    catalog.task_contracts["margin-check"] = TaskContractDefinition(
        **{**margin.__dict__, "dependencies": ("price-band",)}
    )

    result = compile_execution_plan(valid_graph.validate(catalog), {}, catalog)

    assert isinstance(result, Rejected)
    assert result.issues[0].code == "cyclic_task_dependencies"


def test_execution_plan_round_trips(catalog, valid_graph):
    """验证生成的执行计划可通过快照无损恢复。"""
    result = compile_execution_plan(valid_graph.validate(catalog), {"project_id": "project-1"}, catalog)

    restored = result.plan.from_snapshot(result.plan.to_snapshot())

    assert restored == result.plan
