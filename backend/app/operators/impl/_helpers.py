"""算子共享工具。"""

from __future__ import annotations

import time

_DAY_MS = 86_400_000


def now_ms() -> int:
    return int(time.time() * 1000)


def days_to_ms(days: int) -> int:
    return days * _DAY_MS
