"""evidence 接口：从持久化证据链读取可追溯的算子执行记录。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from ..db import get_db
from ..evidence import get_chain, recent_chains

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/recent")
def api_recent_chains(limit: int = 10, db: DbSession = Depends(get_db)):
    return {"chains": recent_chains(db, limit=limit)}


@router.get("/{chain_id}")
def api_get_chain(chain_id: str, db: DbSession = Depends(get_db)):
    chain = get_chain(db, chain_id)
    if chain is None:
        raise HTTPException(status_code=404, detail="证据链不存在")
    return chain.as_dict()
