from __future__ import annotations

import pytest

from app.planning import PlanningError, plan_request


class StubPlanner:
    def __init__(self, response: object) -> None:
        self.response = response

    def complete_json(self, *args, **kwargs):
        return self.response


def test_plan_request_compiles_registered_decision_type() -> None:
    planned = plan_request(
        "美国 TWS 耳机是否值得进入，目标毛利 30%？",
        {"category_id": "cat_tws", "market_code": "US", "profile": {"target_margin": "30%"}},
        llm=StubPlanner(
            {
                "title": "美国站 TWS 耳机选品评估",
                "decision_types": ["product_selection"],
                "capabilities": [],
                "entities": ["market", "category"],
                "metrics": ["demand_growth"],
            }
        ),
    )

    assert planned.title == "美国站 TWS 耳机选品评估"
    assert planned.decision_graph.query == "美国 TWS 耳机是否值得进入，目标毛利 30%？"
    assert planned.execution_plan.goals == ["product_selection"]
    assert [node.id for node in planned.execution_plan.nodes] == [
        "competitive_analyst",
        "demand_researcher",
        "feedback_analyst",
        "price_band_analyst",
        "selection_score",
        "executive_expert",
    ]
    assert planned.execution_plan.clarifications == []


def test_plan_request_extracts_margin_from_original_query() -> None:
    planned = plan_request(
        "美国站 TWS 耳机怎么定价？我希望毛利 40%",
        {"category_id": "cat_tws", "market_code": "US", "profile": {}},
        llm=StubPlanner(
            {
                "title": "美国站 TWS 耳机定价评估",
                "decision_types": ["pricing_strategy"],
                "capabilities": [],
                "entities": ["market", "category", "internal_sku"],
                "metrics": ["cost_floor", "target_margin"],
            }
        ),
    )

    assert planned.execution_plan.clarifications == []
def test_plan_request_returns_structured_margin_clarification() -> None:
    planned = plan_request(
        "美国站 TWS 耳机怎么定价？",
        {"category_id": "cat_tws", "market_code": "US", "profile": {}},
        llm=StubPlanner(
            {
                "title": "美国站 TWS 耳机定价评估",
                "decision_types": ["pricing_strategy"],
                "capabilities": [],
                "entities": ["market", "category", "internal_sku"],
                "metrics": ["cost_floor", "target_margin"],
            }
        ),
    )

    assert [need.field_id for need in planned.execution_plan.clarifications] == ["target_margin"]
    assert planned.execution_plan.clarifications[0].options == ["20%", "30%", "40%"]


def test_plan_request_rejects_unknown_llm_reference() -> None:
    with pytest.raises(PlanningError, match="未注册目标"):
        plan_request(
            "测试请求",
            llm=StubPlanner(
                {
                    "title": "测试",
                    "decision_types": ["arbitrary_workflow"],
                    "capabilities": [],
                    "entities": [],
                    "metrics": [],
                }
            ),
        )


def test_plan_request_rejects_disabled_decision_type() -> None:
    with pytest.raises(PlanningError, match="当前未开放规划能力"):
        plan_request(
            "制定竞争打法",
            llm=StubPlanner(
                {
                    "title": "竞争打法",
                    "decision_types": ["competitive_strategy"],
                    "capabilities": [],
                    "entities": [],
                    "metrics": [],
                }
            ),
        )


def test_plan_request_falls_back_to_registered_capability() -> None:
    planned = plan_request(
        "分析评论痛点",
        {"category_id": "cat_tws", "market_code": "US"},
        llm=StubPlanner(
            {"title": "评论痛点分析", "decision_types": [], "capabilities": [], "entities": [], "metrics": []}
        ),
    )

    assert [node.id for node in planned.execution_plan.nodes] == ["feedback_analyst", "executive_expert"]
