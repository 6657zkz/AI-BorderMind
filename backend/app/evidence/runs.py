from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import AnalysisClarification, AnalysisNodeRun, AnalysisRun
from ._shared import json_safe, new_run_id
from .chains import EvidenceChain, build_chain
from .clarifications import record_clarifications
from .events import append_run_event


def create_analysis_run(
    db: Session,
    *,
    session_id: str,
    user_message_id: int,
    query: str,
    project_ctx: dict[str, Any],
    trigger_source: str = "chat",
) -> AnalysisRun:
    run = AnalysisRun(
        run_id=new_run_id(),
        session_id=session_id,
        user_message_id=user_message_id,
        trigger_source=trigger_source,
        status="planning",
        query=query,
        project_context_json=json_safe(project_ctx),
    )
    db.add(run)
    db.flush()
    append_run_event(db, run_id=run.run_id, event_type="run_created", payload={"status": run.status})
    db.commit()
    db.refresh(run)
    return run


def save_plan_snapshot(
    db: Session,
    *,
    run_id: str,
    decision_graph: dict[str, Any] | None,
    execution_plan: dict[str, Any],
) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError(f"研判运行不存在: {run_id}")
    run.decision_graph_json = json_safe(decision_graph) if decision_graph else None
    run.execution_plan_json = json_safe(execution_plan)
    run.status = "planned"
    append_run_event(
        db,
        run_id=run_id,
        event_type="plan_ready",
        payload={"node_ids": [node.get("id") for node in execution_plan.get("nodes") or []]},
    )
    db.commit()
    db.refresh(run)
    return run


def cancel_analysis_run(db: Session, *, run_id: str) -> AnalysisRun | None:
    run = db.execute(
        select(AnalysisRun).where(AnalysisRun.run_id == run_id).with_for_update()
    ).scalar_one_or_none()
    if run is None or run.status in {"succeeded", "partial_succeeded", "failed", "timed_out", "cancelled"}:
        return run
    run.status = "cancelled"
    run.completed_at = datetime.now(timezone.utc)
    clarifications = db.execute(
        select(AnalysisClarification).where(
            AnalysisClarification.run_id == run_id,
            AnalysisClarification.status == "waiting",
        )
    ).scalars()
    for clarification in clarifications:
        clarification.status = "cancelled"
    append_run_event(db, run_id=run_id, event_type="run_cancelled", payload={"status": run.status})
    db.commit()
    db.refresh(run)
    return run


def _has_final_decision(final: dict[str, Any]) -> bool:
    answer = final.get("answer")
    return isinstance(answer, dict) and bool(str(answer.get("summary") or "").strip())


def complete_analysis_run(
    db: Session,
    *,
    run_id: str,
    final: dict[str, Any],
    decision_graph: dict[str, Any] | None,
    execution_plan: dict[str, Any] | None,
) -> EvidenceChain | None:
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError(f"研判运行不存在: {run_id}")
    if run.status in {"failed", "cancelled", "timed_out"}:
        return None

    run.decision_graph_json = json_safe(decision_graph) if decision_graph else None
    run.execution_plan_json = json_safe(execution_plan) if execution_plan else None
    stored_final = copy.deepcopy(json_safe(final))
    stored_final.setdefault("run_id", run_id)
    chain: EvidenceChain | None = None
    clarification_needs = final.get("clarifications") or []
    if final.get("clarification") and clarification_needs:
        run.status = "waiting_clarification"
        record_clarifications(db, run_id=run_id, needs=clarification_needs)
    elif final.get("mode") == "research" and not _has_final_decision(final):
        run.status = "failed"
        run.error_json = {
            "code": final.get("reason_code") or "missing_final_decision",
            "message": final.get("reason") or "研判未形成可用的最终决策。",
        }
    elif final.get("mode") == "research":
        chain = build_chain(db, run_id=run_id, query=run.query, results=final.get("sections") or {})
        final["chain_id"] = chain.chain_id
        final["run_id"] = run_id
        stored_final["chain_id"] = chain.chain_id
        stored_final["run_id"] = run_id
        failed_nodes = db.execute(
            select(AnalysisNodeRun.id).where(
                AnalysisNodeRun.run_id == run_id,
                AnalysisNodeRun.status.in_(("failed", "timed_out")),
            )
        ).first()
        run.status = "partial_succeeded" if failed_nodes else "succeeded"
    else:
        run.status = "succeeded"

    run.final_json = stored_final
    if run.status != "failed":
        run.error_json = None
    if run.status != "waiting_clarification":
        run.completed_at = datetime.now(timezone.utc)
    append_run_event(
        db,
        run_id=run_id,
        event_type="run_waiting_clarification" if run.status == "waiting_clarification" else "run_completed",
        payload={"status": run.status, "chain_id": chain.chain_id if chain else None},
    )
    db.commit()
    return chain


def fail_analysis_run(
    db: Session,
    *,
    run_id: str,
    error: dict[str, Any],
    status: str = "failed",
) -> AnalysisRun | None:
    run = db.get(AnalysisRun, run_id)
    if run is None or run.status in {"succeeded", "partial_succeeded", "cancelled", "timed_out"}:
        return run
    run.status = status
    run.error_json = json_safe(error)
    run.completed_at = datetime.now(timezone.utc)
    append_run_event(db, run_id=run_id, event_type="run_failed", payload={"status": status, "error": error})
    db.commit()
    db.refresh(run)
    return run
