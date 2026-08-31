from app.domain.capabilities import build_capability_catalog
from app.domain.planning import DecisionGraph, NeedsClarification, Planned, Rejected, compile_execution_plan
from app.domain.planning import Comparison, EvidenceRequirement, TriggerContext


def make_graph(catalog, scope):
    return DecisionGraph(
        graph_id="real-graph",
        catalog_version=catalog.version,
        decision_type_id="promotion-response",
        trigger=TriggerContext(source="user", reference_id="message-1"),
        scope=scope,
        constraints={"response_boundary": "no_price_below_cost"},
        required_evidence=(EvidenceRequirement("market-price-band", "price"),),
        comparisons=(Comparison("competitor_to_own", "competitor-product", "own-product"),),
        entity_references=frozenset({"competitor-product", "own-product"}),
        metric_references=frozenset({"price", "margin"}),
    )


def test_real_catalog_compiles_promotion_response():
    catalog = build_capability_catalog()
    graph = make_graph(
        catalog,
        {"market": "US", "cost_boundary": 20, "target_margin": 0.3},
    )

    result = compile_execution_plan(graph.validate(catalog), {}, catalog)

    assert isinstance(result, Planned)
    assert result.plan.topological_node_ids == (
        "margin-check",
        "price-band",
        "recommendation",
    )


def test_real_catalog_preserves_planning_outcomes():
    catalog = build_capability_catalog()

    clarification = compile_execution_plan(
        make_graph(catalog, {"market": "US", "cost_boundary": 20}).validate(catalog),
        {},
        catalog,
    )
    rejection = compile_execution_plan(
        make_graph(catalog, {"market": "US", "target_margin": 0.3}).validate(catalog),
        {},
        catalog,
    )

    assert isinstance(clarification, NeedsClarification)
    assert isinstance(rejection, Rejected)
    assert rejection.issues[0].code == "missing_required_input"
