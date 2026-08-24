"""变化检测基类：持续监控的核心（对比历史、算变化、判断告警）。

规则写 SQL 检测阈值（对齐方案「LLM 不写 SQL、规则写 SQL」），
产出 SignalCandidate，由 service 统一落 signal 表。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from sqlalchemy.orm import Session


@dataclass
class SignalCandidate:
    signal_type: str
    entity: str
    summary: str
    confidence: str = "medium"  # low / medium / high
    evidence_url: str | None = None


class Detector:
    name: ClassVar[str]
    description: ClassVar[str] = ""

    def detect(self, db: Session, ctx: dict[str, Any]) -> list[SignalCandidate]:
        raise NotImplementedError
