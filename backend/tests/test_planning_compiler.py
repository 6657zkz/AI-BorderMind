from __future__ import annotations

import pytest

from app.planning import (
    DecisionGraph,
    DecisionNode,
    DecisionNodeKind,
    PlanningError,
    compile_plan,
)


def graph_for(*goals: str, capabilities: tuple[str, ...] = ()) -> DecisionGraph:
    nodes = [
        DecisionNode(id=f"goal_{goal}", kind=DecisionNodeKind.GOAL, ref=goal)
        for goal in goals
    ]
    nodes.extend(
        DecisionNode(id=f"capability_{capability}", kind=DecisionNodeKind.CAPABILITY, ref=capability)
        for capability in capabilities
    )
    return DecisionGraph(query="美国 TWS 耳机是否值得进入，且目标毛利为 30%？", nodes=nodes)


def test_combined_selection_and_pricing_plan_shares_price_band_once() -> None:
    plan = compile_plan(graph_for("product_selection", "pricing_strategy"), {"target_margin": "30%"})

    ids = [node.id for node in plan.nodes]
    assert ids.count("price_band_analyst") == 1
    assert ids.count("selection_score") == 1
    assert ids.count("pricing_optimizer") == 1
    assert ids.count("executive_expert") == 1

    nodes = {node.id: node for node in plan.nodes}
    assert set(nodes["selection_score"].depends_on) == {
        "demand_researcher",
        "competitive_analyst",
        "price_band_analyst",
        "feedback_analyst",
    }
    assert set(nodes["pricing_optimizer"].depends_on) == {
        "cost_modeler",
        "price_band_analyst",
        "competitor_benchmark",
    }
    assert set(nodes["executive_expert"].depends_on) == {"selection_score", "pricing_optimizer"}
    assert plan.clarifications == []


def test_pricing_plan_requests_only_missing_target_margin() -> None:
    plan = compile_plan(graph_for("pricing_strategy"))

    assert [need.field_id for need in plan.clarifications] == ["target_margin"]
    assert plan.clarifications[0].required_for == ["pricing_optimizer"]


def test_unknown_goal_is_rejected_before_execution() -> None:
    with pytest.raises(PlanningError, match="未注册目标"):
        compile_plan(graph_for("unregistered_goal"))


def test_unknown_capability_is_rejected_before_execution() -> None:
    with pytest.raises(PlanningError, match="未注册能力"):
        compile_plan(graph_for("product_selection", capabilities=("unsafe_sql_executor",)))


def test_plan_layers_expose_parallel_data_work() -> None:
    plan = compile_plan(graph_for("product_selection", "pricing_strategy"), {"target_margin": "30%"})
    layers = [[node.id for node in layer] for layer in plan.topological_layers()]

    assert set(layers[0]) == {
        "competitor_benchmark",
        "competitive_analyst",
        "cost_modeler",
        "demand_researcher",
        "feedback_analyst",
        "price_band_analyst",
    }
    assert set(layers[1]) == {"pricing_optimizer", "selection_score"}
    assert layers[2] == ["executive_expert"]
