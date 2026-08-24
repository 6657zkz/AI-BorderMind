"""monitor 接口：信号查询 + 手动巡检触发。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import Signal, get_db
from ..monitor import run_monitor
from ..project import build_context
from .schemas import MonitorRunRequest

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


@router.get("/signals")
def api_list_signals(
    project_id: str | None = None, limit: int = 50, db: DbSession = Depends(get_db)
):
    stmt = select(Signal).order_by(Signal.observed_at.desc()).limit(min(limit, 200))
    if project_id:
        stmt = stmt.where(Signal.project_id == project_id)
    rows = db.execute(stmt).scalars().all()
    return {
        "signals": [
            {
                "id": s.id,
                "signal_type": s.signal_type,
                "entity": s.entity,
                "summary": s.summary,
                "evidence_url": s.evidence_url,
                "observed_at": s.observed_at,
                "confidence": s.confidence,
                "status": s.status,
                "project_id": s.project_id,
            }
            for s in rows
        ]
    }


@router.post("/run")
def api_run_monitor(body: MonitorRunRequest, db: DbSession = Depends(get_db)):
    try:
        project_ctx = build_context(db, body.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    created = run_monitor(project_ctx, db=db)
    return {"created": len(created)}
