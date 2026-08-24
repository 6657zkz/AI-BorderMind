"""evidence 接口：按 chain_id 回溯证据链（前端「证据回溯」页）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..evidence import get_chain, recent_chains

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/recent")
def api_recent_chains(limit: int = 10):
    return {"chains": recent_chains(limit=limit)}


@router.get("/{chain_id}")
def api_get_chain(chain_id: str):
    chain = get_chain(chain_id)
    if chain is None:
        raise HTTPException(status_code=404, detail="证据链不存在（内存仅保留最近 50 条）")
    return chain.as_dict()
