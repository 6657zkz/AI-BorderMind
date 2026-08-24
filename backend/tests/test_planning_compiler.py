from __future__ import annotations

import pytest

from app.agents.registry import AGENTS
from app.operators import OPERATORS
from app.planning import DecisionGraph, DecisionNode, DecisionNodeKind, PlanningError, compile_plan
from app.planning.catalog import CAPABILITIES, catalog_entries, validate_catalog


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
    assert nodes["pricing_optimizer"].analysis_task_id == "pricing_recommendation"
    assert nodes["pricing_optimizer"].expert_role_id == "pricing_optimizer"
    assert nodes["pricing_optimizer"].data_capability_ids == [
        "pricing_band",
        "price_percentile",
        "internal_sku_query",
    ]
    assert nodes["pricing_optimizer"].output_contract == [
        "pricing_recommendation",
        "recommended_price",
        "price_range",
    ]
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


def test_catalog_matches_discovered_personas_and_operators() -> None:
    assert validate_catalog(persona_roles=AGENTS, operator_ids=OPERATORS) == []
    assert {entry["role"] for entry in catalog_entries(include_legacy=True)} == set(AGENTS)


def test_disabled_capability_is_rejected_from_new_plan() -> None:
    with pytest.raises(PlanningError, match="当前未开放规划能力"):
        compile_plan(graph_for("competitive_strategy"))

    with pytest.raises(PlanningError, match="当前未开放规划能力"):
        compile_plan(graph_for("product_selection", capabilities=("search_gap_analyst",)))


def test_catalog_authorizes_persona_data_access() -> None:
    capability = CAPABILITIES["cost_modeler"]

    assert capability.operator_specs == [
        "internal_sku_query",
        ("supply_signal_query", {"signal_type": "freight_index"}),
        ("supply_signal_query", {"signal_type": "fx_rate"}),
    ]
