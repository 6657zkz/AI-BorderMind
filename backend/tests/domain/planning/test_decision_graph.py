from app.domain.planning import DecisionGraph, Rejected


def test_decision_graph_validates_and_round_trips(catalog, valid_graph):
    """验证合法图可通过校验、快照往返且不共享可变数据。"""
    result = valid_graph.validate(catalog)

    assert result.graph == valid_graph
    snapshot = valid_graph.to_snapshot()
    restored = DecisionGraph.from_snapshot(snapshot)

    assert restored == valid_graph
    snapshot["scope"]["market"] = "DE"
    assert restored.scope["market"] == "US"


def test_decision_graph_rejects_unknown_references(catalog, valid_graph):
    """验证图中的未知实体和指标会在编译前被拒绝。"""
    graph = DecisionGraph(
        **{
            **valid_graph.__dict__,
            "entity_references": frozenset({"unknown-product"}),
            "metric_references": frozenset({"unknown-metric"}),
        }
    )

    result = graph.validate(catalog)

    assert isinstance(result, Rejected)
    assert [issue.code for issue in result.issues] == ["unknown_entity", "unknown_metric"]


def test_decision_graph_rejects_unknown_decision_type(catalog, valid_graph):
    """验证未注册的决策类型不能进入规划流程。"""
    graph = DecisionGraph(**{**valid_graph.__dict__, "decision_type_id": "missing"})

    result = graph.validate(catalog)

    assert isinstance(result, Rejected)
    assert result.issues[0].code == "unknown_decision_type"


def test_decision_graph_rejects_catalog_version_mismatch(catalog, valid_graph):
    """验证 Graph 与能力目录版本不一致时会被拒绝。"""
    graph = DecisionGraph(**{**valid_graph.__dict__, "catalog_version": "catalog-v0"})

    result = graph.validate(catalog)

    assert isinstance(result, Rejected)
    assert result.issues[0].code == "catalog_version_mismatch"
