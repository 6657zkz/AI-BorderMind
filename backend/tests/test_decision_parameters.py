from __future__ import annotations

from app.project.decision_parameters import (
    extract_decision_parameters,
    parse_decision_parameter,
)


def test_extracts_registered_parameter_from_full_message() -> None:
    assert extract_decision_parameters("美国站耳机定价，我希望毛利 30%") == {"target_margin": "30%"}


def test_parses_registered_percentage_parameter() -> None:
    assert parse_decision_parameter("target_margin", "目标毛利为 40.5%") == "40.5%"
    assert parse_decision_parameter("target_margin", "目标毛利 0%") is None
    assert parse_decision_parameter("target_margin", "没有百分比") is None


def test_rejects_unregistered_parameter() -> None:
    assert parse_decision_parameter("lead_time_days", "30 天") is None
