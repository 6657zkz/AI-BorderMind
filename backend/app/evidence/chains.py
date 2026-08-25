from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import AnalysisNodeRun, EvidenceChainRecord, EvidenceEntryRecord
from ._shared import json_safe, timestamp


@dataclass
class EvidenceEntry:
    role: str
    operator: str
    params: dict[str, Any]
    sql: str
    rows: list[dict[str, Any]]
    executed_at: str | None
    elapsed_ms: int
    row_count: int = 0
    truncated: bool = False


@dataclass
class EvidenceChain:
    chain_id: str
    query: str
    created_at: str
    entries: list[EvidenceEntry] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "query": self.query,
            "created_at": self.created_at,
            "entries": [entry.__dict__ for entry in self.entries],
        }


def _node_run_ids(db: Session, run_id: str) -> dict[str, int]:
    rows = db.execute(
        select(AnalysisNodeRun)
        .where(AnalysisNodeRun.run_id == run_id)
        .order_by(AnalysisNodeRun.id)
    ).scalars()
    return {row.node_id: row.id for row in rows}


def build_chain(
    db: Session,
    *,
    run_id: str,
    query: str,
    results: dict[str, Any],
) -> EvidenceChain:
    existing = db.execute(
        select(EvidenceChainRecord).where(EvidenceChainRecord.run_id == run_id)
    ).scalar_one_or_none()
    if existing is not None:
        return _chain_from_record(db, existing)

    chain_record = EvidenceChainRecord(
        chain_id=f"ev_{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        query=query,
    )
    db.add(chain_record)
    db.flush()

    node_run_ids = _node_run_ids(db, run_id)
    ordinal = 0
    entries: list[EvidenceEntry] = []
    for node_id, result in results.items():
        for evidence in result.get("evidence") or []:
            rows = json_safe(evidence.get("rows") or [])
            entry = EvidenceEntry(
                role=evidence.get("role") or result.get("role") or node_id,
                operator=evidence.get("operator", ""),
                params=json_safe(evidence.get("params") or {}),
                sql=evidence.get("sql", ""),
                rows=rows,
                executed_at=evidence.get("executed_at"),
                elapsed_ms=int(evidence.get("elapsed_ms") or 0),
                row_count=int(evidence.get("row_count", len(rows))),
                truncated=bool(evidence.get("truncated", False)),
            )
            db.add(
                EvidenceEntryRecord(
                    chain_id=chain_record.chain_id,
                    node_run_id=node_run_ids.get(node_id),
                    ordinal=ordinal,
                    role=entry.role,
                    operator=entry.operator,
                    params_json=entry.params,
                    sql=entry.sql,
                    rows_json=entry.rows,
                    row_count=entry.row_count,
                    truncated=entry.truncated,
                    executed_at=entry.executed_at,
                    elapsed_ms=entry.elapsed_ms,
                )
            )
            entries.append(entry)
            ordinal += 1
    db.flush()
    return EvidenceChain(
        chain_id=chain_record.chain_id,
        query=chain_record.query,
        created_at=timestamp(chain_record.created_at),
        entries=entries,
    )


def _chain_from_record(db: Session, record: EvidenceChainRecord) -> EvidenceChain:
    entries = db.execute(
        select(EvidenceEntryRecord)
        .where(EvidenceEntryRecord.chain_id == record.chain_id)
        .order_by(EvidenceEntryRecord.ordinal)
    ).scalars()
    return EvidenceChain(
        chain_id=record.chain_id,
        query=record.query,
        created_at=timestamp(record.created_at),
        entries=[
            EvidenceEntry(
                role=entry.role,
                operator=entry.operator,
                params=entry.params_json or {},
                sql=entry.sql,
                rows=entry.rows_json or [],
                executed_at=entry.executed_at,
                elapsed_ms=entry.elapsed_ms,
                row_count=entry.row_count,
                truncated=entry.truncated,
            )
            for entry in entries
        ],
    )


def recent_chains(db: Session, limit: int = 10) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    records = db.execute(
        select(EvidenceChainRecord)
        .order_by(EvidenceChainRecord.created_at.desc())
        .limit(limit)
    ).scalars()
    return [_chain_from_record(db, record).as_dict() for record in records]


def get_chain(db: Session, chain_id: str) -> EvidenceChain | None:
    record = db.get(EvidenceChainRecord, chain_id)
    return _chain_from_record(db, record) if record is not None else None


def summarize_chain(chain: EvidenceChain) -> str:
    lines = [f"证据链 {chain.chain_id} | 查询: {chain.query}"]
    for entry in chain.entries:
        lines.append(
            f"- [{entry.role}] {entry.operator} {entry.elapsed_ms}ms\n"
            f"  SQL: {entry.sql}\n  参数: {entry.params}\n  行数: {entry.row_count}"
        )
    return "\n".join(lines)
