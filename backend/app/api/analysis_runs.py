"""AnalysisRun 状态、事件回放、澄清与取消接口。"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from ..application import ResearchRunConflict, ResearchRunService
from ..db import AnalysisRun, get_db
from ..evidence import (
    answer_clarification,
    append_run_event,
    cancel_analysis_run as cancel_persisted_run,
    complete_analysis_run,
    fail_analysis_run,
    get_chain,
    get_run_events,
    get_run_snapshot,
)
from ..project import apply_decision_parameter
from ..session import append_message, resolve_context
from .schemas import ClarificationAnswerRequest

router = APIRouter(prefix="/api/analysis-runs", tags=["analysis-runs"])


@router.get("/{run_id}")
def get_analysis_run(run_id: str, db: DbSession = Depends(get_db)):
    snapshot = get_run_snapshot(db, run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="研判运行不存在")
    return snapshot


@router.get("/{run_id}/evidence")
def get_analysis_run_evidence(run_id: str, db: DbSession = Depends(get_db)):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="研判运行不存在")
    chain_id = (run.final_json or {}).get("chain_id")
    if not chain_id:
        return {"run_id": run_id, "chain": None}
    chain = get_chain(db, chain_id)
    return {"run_id": run_id, "chain": chain.as_dict() if chain else None}


@router.post("/{run_id}/cancel")
def cancel_analysis_run(run_id: str, db: DbSession = Depends(get_db)):
    run = cancel_persisted_run(db, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="研判运行不存在")
    return {"run_id": run_id, "status": run.status}


@router.post("/{run_id}/clarifications")
def submit_clarification(
    run_id: str,
    body: ClarificationAnswerRequest,
    db: DbSession = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None or run.status != "waiting_clarification":
        raise HTTPException(status_code=409, detail="研判运行当前不可续跑")

    project_ctx = resolve_context(db, run.session_id)
    if body.field_id == "scope":
        from ..project import apply_scope, parse_scope

        scope = parse_scope(db, body.value)
        if scope is None:
            raise HTTPException(status_code=422, detail="请同时提供品类和目标市场，例如：TWS 耳机，美国站")
        apply_scope(db, project_ctx["project_id"], scope)
    elif apply_decision_parameter(db, project_ctx["project_id"], body.field_id, body.value) is None:
        raise HTTPException(status_code=422, detail="决策参数不存在或格式无效")

    user_message = append_message(db, run.session_id, "user", body.value)
    try:
        run = ResearchRunService().resume(
            db,
            run_id=run_id,
            field_id=body.field_id,
            answer=body.value,
            user_message_id=user_message.id,
            project_ctx=project_ctx,
        )
    except ResearchRunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        final = ResearchRunService().execute(db, run=run)
        append_message(db, run.session_id, "assistant", json.dumps(final, ensure_ascii=False))
    except Exception:
        raise
    return {"run_id": run_id, "field_id": body.field_id, "status": "resumed", "final": final}


@router.get("/{run_id}/events")
async def stream_analysis_events(run_id: str, request: Request, after: int = 0, db: DbSession = Depends(get_db)):
    if db.get(AnalysisRun, run_id) is None:
        raise HTTPException(status_code=404, detail="研判运行不存在")
    db.close()

    async def event_stream():
        last_seq = after
        while True:
            from ..db import SessionLocal

            with SessionLocal() as worker_db:
                events = get_run_events(worker_db, run_id, after_seq=last_seq)
                snapshot = get_run_snapshot(worker_db, run_id)
            for event in events:
                last_seq = event["seq"]
                yield f"id: {event['seq']}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            if snapshot and snapshot["status"] in {"succeeded", "partial_succeeded", "failed", "timed_out", "cancelled"}:
                return
            if await request.is_disconnected():
                return
            yield ": keepalive\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
