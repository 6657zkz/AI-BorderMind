from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import AnalysisRun, AnalysisRunEvent
from ._shared import json_safe, timestamp


def append_run_event(
    db: Session,
    *,
    run_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    node_id: str | None = None,
) -> AnalysisRunEvent:
    db.execute(
        select(AnalysisRun).where(AnalysisRun.run_id == run_id).with_for_update()
    ).scalar_one()
    next_seq = (db.execute(
        select(func.coalesce(func.max(AnalysisRunEvent.seq), 0)).where(AnalysisRunEvent.run_id == run_id)
    ).scalar_one() or 0) + 1
    event = AnalysisRunEvent(
        run_id=run_id,
        seq=next_seq,
        node_id=node_id,
        event_type=event_type,
        payload_json=json_safe(payload or {}),
    )
    db.add(event)
    db.flush()
    return event


def get_run_events(db: Session, run_id: str, *, after_seq: int = 0) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AnalysisRunEvent)
        .where(AnalysisRunEvent.run_id == run_id, AnalysisRunEvent.seq > after_seq)
        .order_by(AnalysisRunEvent.seq)
    ).scalars()
    return [
        {
            "schema_version": 2,
            "event_id": f"{event.run_id}:{event.seq}",
            "run_id": event.run_id,
            "seq": event.seq,
            "node_id": event.node_id,
            "type": event.event_type,
            "at": timestamp(event.created_at),
            "data": event.payload_json or {},
        }
        for event in rows
    ]
