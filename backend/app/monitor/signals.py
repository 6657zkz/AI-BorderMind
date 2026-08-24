"""信号落库：SignalCandidate → signal 表（status='new'，触发研判 / 推送）。"""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from ..db import Signal
from .detectors.base import SignalCandidate


def create_signal(
    db: Session,
    candidate: SignalCandidate,
    project_id: str | None = None,
) -> Signal:
    sig = Signal(
        signal_type=candidate.signal_type,
        entity=candidate.entity,
        summary=candidate.summary,
        evidence_url=candidate.evidence_url,
        observed_at=int(time.time() * 1000),
        confidence=candidate.confidence,
        status="new",
        project_id=project_id,
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    return sig
