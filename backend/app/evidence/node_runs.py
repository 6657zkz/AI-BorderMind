from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import AnalysisNodeRun, AnalysisRun
from ._shared import json_safe
from .events import append_run_event


def start_node_run(
    db: Session,
    *,
    run_id: str,
    node_id: str,
    role: str,
    input_summary: dict[str, Any],
) -> AnalysisNodeRun:
    node_run = db.execute(
        select(AnalysisNodeRun).where(
            AnalysisNodeRun.run_id == run_id,
            AnalysisNodeRun.node_id == node_id,
        )
    ).scalar_one_or_none()
    if node_run is None:
        node_run = AnalysisNodeRun(
            run_id=run_id,
            node_id=node_id,
            role=role,
            status="running",
            input_summary_json=json_safe(input_summary),
        )
        db.add(node_run)
    else:
        node_run.role = role
        node_run.status = "running"
        node_run.input_summary_json = json_safe(input_summary)
        node_run.error = None
        node_run.retry_count += 1
        node_run.completed_at = None
        node_run.elapsed_ms = None

    run = db.get(AnalysisRun, run_id)
    if run is not None and run.status in {"created", "planning", "planned"}:
        run.status = "running"
    append_run_event(
        db,
        run_id=run_id,
        node_id=node_id,
        event_type="node_started",
        payload={"role": role, "retry_count": node_run.retry_count},
    )
    db.commit()
    db.refresh(node_run)
    return node_run


def finish_node_run(
    db: Session,
    *,
    run_id: str,
    node_id: str,
    conclusion: dict[str, Any],
    evidence_count: int,
    skipped: list[dict[str, Any]],
    error: str | None,
    elapsed_ms: int,
) -> AnalysisNodeRun | None:
    node_run = db.execute(
        select(AnalysisNodeRun).where(
            AnalysisNodeRun.run_id == run_id,
            AnalysisNodeRun.node_id == node_id,
        )
    ).scalar_one_or_none()
    if node_run is None:
        return None
    node_run.status = "failed" if error else "succeeded"
    node_run.output_summary_json = json_safe({"conclusion": conclusion, "evidence_count": evidence_count})
    node_run.skipped_json = json_safe(skipped)
    node_run.error = error
    node_run.elapsed_ms = elapsed_ms
    node_run.completed_at = datetime.now(timezone.utc)
    append_run_event(
        db,
        run_id=run_id,
        node_id=node_id,
        event_type="node_failed" if error else "node_succeeded",
        payload={"error": error, "elapsed_ms": elapsed_ms, "evidence_count": evidence_count},
    )
    db.commit()
    db.refresh(node_run)
    return node_run


def skip_node_run(
    db: Session,
    *,
    run_id: str,
    node_id: str,
    skipped: list[dict[str, Any]],
) -> AnalysisNodeRun | None:
    node_run = db.execute(
        select(AnalysisNodeRun).where(
            AnalysisNodeRun.run_id == run_id,
            AnalysisNodeRun.node_id == node_id,
        )
    ).scalar_one_or_none()
    if node_run is None:
        return None
    node_run.status = "skipped"
    node_run.output_summary_json = {"conclusion": {}, "evidence_count": 0}
    node_run.skipped_json = json_safe(skipped)
    node_run.error = None
    node_run.elapsed_ms = 0
    node_run.completed_at = datetime.now(timezone.utc)
    append_run_event(
        db,
        run_id=run_id,
        node_id=node_id,
        event_type="node_skipped",
        payload={"skipped": skipped},
    )
    db.commit()
    db.refresh(node_run)
    return node_run
