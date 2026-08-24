"""证据链：结论 → 数据来源（算子 SQL / 参数 / 耗时 / 时间戳）可回溯。

当前：内存记录 + 结构化导出（前端证据回溯 / 答辩引用）。
持久化：需新增 evidence 表（schema.sql 的 21 张表未含，暂不引入，避免擅自改 DDL）。
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

_MAX_CHAINS = 50
_recent: deque[EvidenceChain] = deque(maxlen=_MAX_CHAINS)


@dataclass
class EvidenceEntry:
    role: str
    operator: str
    params: dict[str, Any]
    sql: str
    rows: list[dict[str, Any]]
    executed_at: str
    elapsed_ms: int


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
            "entries": [e.__dict__ for e in self.entries],
        }


def build_chain(query: str, results: dict[str, Any]) -> EvidenceChain:
    """把各专家结果（ExpertResult.as_dict）拍平成一条证据链。"""
    chain = EvidenceChain(
        chain_id=f"ev_{uuid.uuid4().hex[:12]}",
        query=query,
        created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    for role, res in results.items():
        for ev in res.get("evidence") or []:
            chain.entries.append(
                EvidenceEntry(
                    role=role,
                    operator=ev.get("operator", ""),
                    params=ev.get("params", {}),
                    sql=ev.get("sql", ""),
                    rows=ev.get("rows", []),
                    executed_at=ev.get("executed_at", ""),
                    elapsed_ms=ev.get("elapsed_ms", 0),
                )
            )
    _recent.append(chain)
    return chain


def summarize_chain(chain: EvidenceChain) -> str:
    lines = [f"证据链 {chain.chain_id} | 查询: {chain.query}"]
    for e in chain.entries:
        lines.append(
            f"- [{e.role}] {e.operator} {e.elapsed_ms}ms\n"
            f"  SQL: {e.sql}\n  参数: {e.params}\n  行数: {len(e.rows)}"
        )
    return "\n".join(lines)


def recent_chains(limit: int = 10) -> list[dict[str, Any]]:
    return [c.as_dict() for c in list(_recent)[-limit:]]


def get_chain(chain_id: str) -> EvidenceChain | None:
    for c in _recent:
        if c.chain_id == chain_id:
            return c
    return None
