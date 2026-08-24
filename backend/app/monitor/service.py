"""监控服务：一次巡检 = 跑全部检测器 → 收集候选信号 → 落库。

供调度器（时间触发）与 API（手动触发）共用；db 为 None 时自开会话。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..db import SessionLocal, Signal
from .detectors.base import Detector, SignalCandidate
from .detectors.price_drop import PriceDropDetector
from .detectors.review_surge import ReviewSurgeDetector
from .detectors.trend_shift import TrendShiftDetector
from .signals import create_signal

DETECTORS: list[Detector] = [
    PriceDropDetector(),
    ReviewSurgeDetector(),
    TrendShiftDetector(),
]


def run_monitor(
    project_ctx: dict[str, Any] | None = None,
    db: Session | None = None,
) -> list[Signal]:
    ctx = project_ctx or {}
    own_db = db is None
    session: Session = db or SessionLocal()
    try:
        candidates: list[SignalCandidate] = []
        for det in DETECTORS:
            candidates.extend(det.detect(session, ctx))
        created: list[Signal] = []
        for cand in candidates:
            created.append(create_signal(session, cand, project_id=ctx.get("project_id")))
        return created
    finally:
        if own_db:
            session.close()
