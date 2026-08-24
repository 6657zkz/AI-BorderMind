from __future__ import annotations

from app.graph.nodes import research
from app.planning import plan_request


class StubPlanner:
    def __init__(self, response: dict) -> None:
        self.response = response

    def complete_json(self, *args, **kwargs):
        return self.response


def planned_request(*, with_margin: bool):
    return plan_request(
        "美国站 TWS 耳机定价评估",
        {
            "category_id": "cat_tws",
            "market_code": "US",
            "profile": {"target_margin": "30%"} if with_margin else {},
        },
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


def test_plan_node_requests_scope_as_structured_clarification() -> None:
    update = research.plan_node({"mode": "research", "project_ctx": {}})

    assert update["clarification"] == "请补充研判范围：面向哪个品类、哪个目标市场？例如：TWS 耳机，美国站。"
    assert update["clarifications"] == [
        {
            "field_id": "scope",
            "question": update["clarification"],
            "options": [],
            "required_for": ["scope"],
        }
    ]
def test_rewrite_node_uses_compiled_plan_roles(monkeypatch) -> None:
    planned = planned_request(with_margin=True)
    monkeypatch.setattr(research, "plan_request", lambda *args, **kwargs: planned)

    update = research.rewrite_node({"query": "定价", "project_ctx": {}})

    assert update["roles"] == [
        "competitor_benchmark",
        "cost_modeler",
        "price_band_analyst",
        "pricing_optimizer",
        "executive_expert",
    ]
    assert update["execution_plan"]["goals"] == ["pricing_strategy"]
    assert "clarification" not in update


def test_rewrite_node_blocks_execution_for_structured_clarification(monkeypatch) -> None:
    planned = planned_request(with_margin=False)
    monkeypatch.setattr(research, "plan_request", lambda *args, **kwargs: planned)

    update = research.rewrite_node({"query": "定价", "project_ctx": {}})

    assert "roles" not in update
    assert update["clarification"] == "你的目标毛利率是多少？"
    assert update["clarifications"] == [
        {
            "field_id": "target_margin",
            "question": "你的目标毛利率是多少？",
            "required_for": ["pricing_optimizer"],
            "options": ["20%", "30%", "40%"],
        }
    ]
