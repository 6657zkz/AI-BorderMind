from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from ..db import Project


@dataclass(frozen=True)
class DecisionParameterDefinition:
    field_id: str
    parse: Callable[[str], str | None]
    invalid_message: str


def _parse_percentage(raw: str) -> str | None:
    matches = re.findall(r"(\d{1,2}(?:\.\d+)?)\s*%", raw)
    if not matches:
        return None
    value = float(matches[-1])
    if not 0 < value < 100:
        return None
    return f"{value:g}%"


DECISION_PARAMETERS: dict[str, DecisionParameterDefinition] = {
    "target_margin": DecisionParameterDefinition(
        field_id="target_margin",
        parse=_parse_percentage,
        invalid_message="目标毛利率格式无效，请输入百分比，例如 30%",
    ),
}


def parse_decision_parameter(field_id: str, raw: str) -> str | None:
    definition = DECISION_PARAMETERS.get(field_id)
    return definition.parse(raw) if definition else None


def extract_decision_parameters(message: str) -> dict[str, str]:
    return {
        field_id: value
        for field_id, definition in DECISION_PARAMETERS.items()
        if (value := definition.parse(message)) is not None
    }


def apply_decision_parameter(
    db: Session,
    project_id: str,
    field_id: str,
    raw: str,
) -> Project | None:
    value = parse_decision_parameter(field_id, raw)
    if value is None:
        return None
    project = db.get(Project, project_id)
    if project is None:
        return None
    profile = dict(project.profile_json or {})
    profile[field_id] = value
    project.profile_json = profile
    db.commit()
    db.refresh(project)
    return project
