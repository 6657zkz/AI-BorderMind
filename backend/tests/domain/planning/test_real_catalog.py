from app.domain.capabilities import build_capability_catalog
from app.domain.planning import Comparison, DecisionGraph, EvidenceRequirement, TriggerContext
from app.domain.planning import NeedsClarification, Planned, Rejected, compile_execution_plan


def make_graph(catalog, scope):
    """用真实能力目录构造一个竞品促销应对业务图。"""
    return DecisionGraph(
        # Graph ID 用于标识本次业务语义快照，并参与生成计划 ID。
        graph_id="real-graph",
        # Graph 必须携带与目录完全相同的版本，才能通过校验。
        catalog_version=catalog.version,
        # 该决策类型决定允许的上下文、证据、比较关系和任务蓝图。
        decision_type_id="promotion-response",
        # 当前 Graph 来源于用户消息；这里不代表实现了触发策略。
        trigger=TriggerContext(source="user", reference_id="message-1"),
        # scope 是本次请求提供的业务上下文，供任务输入绑定。
        scope=scope,
        # constraints 是决策需要遵守的业务边界。
        constraints={"response_boundary": "no_price_below_cost"},
        # Graph 需要的 Evidence 及其关联指标。
        required_evidence=(EvidenceRequirement("market-price-band", "price"),),
        # 竞品商品与我方商品之间的允许比较关系。
        comparisons=(Comparison("competitor_to_own", "competitor-product", "own-product"),),
        # Graph 引用的业务实体白名单。
        entity_references=frozenset({"competitor-product", "own-product"}),
        # Graph 引用的业务指标白名单。
        metric_references=frozenset({"price", "margin"}),
    )


def test_real_catalog_compiles_promotion_response():
    """真实目录应能驱动 planning 编译出稳定 DAG。"""
    catalog = build_capability_catalog()
    graph = make_graph(
        catalog,
        {"market": "US", "cost_boundary": 20, "target_margin": 0.3},
    )

    # 先校验业务语义图，再把成功结果交给计划编译器。
    result = compile_execution_plan(graph.validate(catalog), {}, catalog)

    assert isinstance(result, Planned)
    # margin-check 和 price-band 无相互依赖，因此按稳定排序先并行，再执行 recommendation。
    assert result.plan.topological_node_ids == (
        "margin-check",
        "price-band",
        "recommendation",
    )


def test_real_catalog_preserves_planning_outcomes():
    """真实目录应保持可澄清和不可澄清缺失的规划语义。"""
    catalog = build_capability_catalog()

    # target_margin 可由用户补充，因此缺失时返回结构化澄清请求。
    clarification = compile_execution_plan(
        make_graph(catalog, {"market": "US", "cost_boundary": 20}).validate(catalog),
        {},
        catalog,
    )
    # cost_boundary 是不可澄清的硬输入，缺失时必须拒绝规划。
    rejection = compile_execution_plan(
        make_graph(catalog, {"market": "US", "target_margin": 0.3}).validate(catalog),
        {},
        catalog,
    )

    assert isinstance(clarification, NeedsClarification)
    assert isinstance(rejection, Rejected)
    assert rejection.issues[0].code == "missing_required_input"
