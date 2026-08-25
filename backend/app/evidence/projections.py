from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import AnalysisClarification, AnalysisNodeRun, AnalysisRun
from ._shared import timestamp


def get_run_snapshot(db: Session, run_id: str) -> dict[str, Any] | None:
    run = db.get(AnalysisRun, run_id)
    if run is None:
        return None
    nodes = db.execute(
        select(AnalysisNodeRun)
        .where(AnalysisNodeRun.run_id == run_id)
        .order_by(AnalysisNodeRun.id)
    ).scalars().all()
    clarifications = db.execute(
        select(AnalysisClarification)
        .where(AnalysisClarification.run_id == run_id)
        .order_by(AnalysisClarification.id)
    ).scalars().all()
    return {
        "run_id": run.run_id,
        "session_id": run.session_id,
        "status": run.status,
        "query": run.query,
        "trigger_source": run.trigger_source,
        "project_context": run.project_context_json,
        "decision_graph": run.decision_graph_json,
        "execution_plan": run.execution_plan_json,
        "final": run.final_json,
        "error": run.error_json,
        "started_at": timestamp(run.started_at),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "nodes": [
            {
                "node_id": node.node_id,
                "role": node.role,
                "status": node.status,
                "input_summary": node.input_summary_json,
                "output_summary": node.output_summary_json,
                "skipped": node.skipped_json or [],
                "error": node.error,
                "retry_count": node.retry_count,
                "elapsed_ms": node.elapsed_ms,
            }
            for node in nodes
        ],
        "clarifications": [
            {
                "field_id": item.field_id,
                "question": item.question,
                "options": item.options_json or [],
                "status": item.status,
                "answer": item.answer_json,
            }
            for item in clarifications
        ],
    }
