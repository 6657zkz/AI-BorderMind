from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import AnalysisClarification
from ._shared import json_safe
from .events import append_run_event


def record_clarifications(db: Session, *, run_id: str, needs: list[dict[str, Any]]) -> None:
    for need in needs:
        record = db.execute(
            select(AnalysisClarification).where(
                AnalysisClarification.run_id == run_id,
                AnalysisClarification.field_id == need["field_id"],
            )
        ).scalar_one_or_none()
        if record is None:
            db.add(
                AnalysisClarification(
                    run_id=run_id,
                    field_id=need["field_id"],
                    question=need["question"],
                    options_json=need.get("options") or [],
                )
            )
    append_run_event(db, run_id=run_id, event_type="clarification_required", payload={"clarifications": needs})
    db.flush()


def answer_clarification(
    db: Session,
    *,
    run_id: str,
    field_id: str,
    answer: Any,
    message_id: int | None = None,
    commit: bool = True,
) -> AnalysisClarification | None:
    record = db.execute(
        select(AnalysisClarification).where(
            AnalysisClarification.run_id == run_id,
            AnalysisClarification.field_id == field_id,
            AnalysisClarification.status == "waiting",
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    record.status = "answered"
    record.answer_json = json_safe({"value": answer})
    record.answered_message_id = message_id
    record.answered_at = datetime.now(timezone.utc)
    append_run_event(
        db,
        run_id=run_id,
        event_type="clarification_answered",
        payload={"field_id": field_id},
    )
    if commit:
        db.commit()
        db.refresh(record)
    else:
        db.flush()
    return record
