"""监控调度：APScheduler 时间触发，定时跑巡检（变化检测 → 信号落库）。

在 FastAPI 启动时调用 setup_monitor(project_ctx) 注册并启动。
"""

from __future__ import annotations

from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .service import run_monitor

_scheduler: BackgroundScheduler | None = None


def setup_monitor(project_ctx: dict[str, Any], interval_minutes: int = 60) -> BackgroundScheduler:
    """启动后台调度：每 interval_minutes 分钟对 project_ctx 巡检一次。"""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(
        run_monitor,
        IntervalTrigger(minutes=interval_minutes),
        kwargs={"project_ctx": project_ctx},
        id="monitor",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    return _scheduler


def shutdown_monitor() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
