"""研判运行与证据持久化。

数据库是 AnalysisRun、节点执行记录和证据链的唯一权威来源；本模块仅提供
与既有证据接口兼容的 DTO，不保留进程内缓存。
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import (
    AnalysisClarification,
    AnalysisNodeRun,
    AnalysisRun,
    AnalysisRunEvent,
    EvidenceChainRecord,
    EvidenceEntryRecord,
)


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


def new_run_id() -> str:
    return f"ar_{uuid.uuid4().hex[:12]}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _timestamp(value: datetime | None) -> str:
    return (value or datetime.now(timezone.utc)).isoformat()


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
        project_context_json=_json_safe(project_ctx),
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
    run.decision_graph_json = _json_safe(decision_graph) if decision_graph else None
    run.execution_plan_json = _json_safe(execution_plan)
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
        payload_json=_json_safe(payload or {}),
    )
    db.add(event)
    db.flush()
    return event


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
    record.answer_json = _json_safe({"value": answer})
    record.answered_message_id = message_id
    record.answered_at = datetime.now(timezone.utc)
    append_run_event(
        db,
        run_id=run_id,
        event_type="clarification_answered",
        payload={"field_id": field_id},
    )
    db.commit()
    db.refresh(record)
    return record


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
        "started_at": _timestamp(run.started_at),
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
            "at": _timestamp(event.created_at),
            "data": event.payload_json or {},
        }
        for event in rows
    ]


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
            input_summary_json=_json_safe(input_summary),
        )
        db.add(node_run)
    else:
        node_run.role = role
        node_run.status = "running"
        node_run.input_summary_json = _json_safe(input_summary)
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
    node_run.output_summary_json = _json_safe(
        {"conclusion": conclusion, "evidence_count": evidence_count}
    )
    node_run.skipped_json = _json_safe(skipped)
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
    node_run.skipped_json = _json_safe(skipped)
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
    """将专家结果落为有序证据链；调用方负责提交包含 Run 终态的事务。"""
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
            rows = _json_safe(evidence.get("rows") or [])
            entry = EvidenceEntry(
                role=evidence.get("role") or result.get("role") or node_id,
                operator=evidence.get("operator", ""),
                params=_json_safe(evidence.get("params") or {}),
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
        created_at=_timestamp(chain_record.created_at),
        entries=entries,
    )


def complete_analysis_run(
    db: Session,
    *,
    run_id: str,
    final: dict[str, Any],
    decision_graph: dict[str, Any] | None,
    execution_plan: dict[str, Any] | None,
) -> EvidenceChain | None:
    """原子写入终态、计划快照和证据链，成功提交后才向调用方暴露 chain_id。"""
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError(f"研判运行不存在: {run_id}")
    if run.status in {"failed", "cancelled", "timed_out"}:
        return None

    run.decision_graph_json = _json_safe(decision_graph) if decision_graph else None
    run.execution_plan_json = _json_safe(execution_plan) if execution_plan else None
    stored_final = copy.deepcopy(_json_safe(final))
    stored_final.setdefault("run_id", run_id)
    chain: EvidenceChain | None = None
    if final.get("clarification"):
        run.status = "waiting_clarification"
        record_clarifications(db, run_id=run_id, needs=final.get("clarifications") or [])
    elif final.get("mode") == "research":
        chain = build_chain(
            db,
            run_id=run_id,
            query=run.query,
            results=final.get("sections") or {},
        )
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
    run.error_json = _json_safe(error)
    run.completed_at = datetime.now(timezone.utc)
    append_run_event(db, run_id=run_id, event_type="run_failed", payload={"status": status, "error": error})
    db.commit()
    db.refresh(run)
    return run


def _chain_from_record(db: Session, record: EvidenceChainRecord) -> EvidenceChain:
    entries = db.execute(
        select(EvidenceEntryRecord)
        .where(EvidenceEntryRecord.chain_id == record.chain_id)
        .order_by(EvidenceEntryRecord.ordinal)
    ).scalars()
    return EvidenceChain(
        chain_id=record.chain_id,
        query=record.query,
        created_at=_timestamp(record.created_at),
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
