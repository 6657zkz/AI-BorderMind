"""评论突增检测：近 7 天评论数较前 30 天基线翻 3 倍以上，提示舆情/爆款信号。"""

from __future__ import annotations

from typing import Any, ClassVar

from sqlalchemy import text
from sqlalchemy.orm import Session

from .base import Detector, SignalCandidate

_WINDOW_DAY = 86_400_000


class ReviewSurgeDetector(Detector):
    name = "review_surge"
    description = "类目下某产品评论突增（近 7 天 / 前 30 天基线 ≥ 3 倍）"

    def detect(self, db: Session, ctx: dict[str, Any]) -> list[SignalCandidate]:
        category = ctx.get("category_id")
        if not category:
            return []
        latest_ts = db.execute(
            text("SELECT COALESCE(max(ts), 0) FROM review")
        ).scalar()
        t1 = latest_ts - 7 * _WINDOW_DAY
        t2 = latest_ts - 30 * _WINDOW_DAY
        sql = """
        WITH recent AS (
            SELECT r.product_id, count(*) AS c
            FROM review r JOIN product p ON p.product_id = r.product_id
            WHERE p.category_id = :category AND r.ts >= :t1
            GROUP BY r.product_id
        ),
        baseline AS (
            SELECT r.product_id, count(*) AS c
            FROM review r JOIN product p ON p.product_id = r.product_id
            WHERE p.category_id = :category AND r.ts BETWEEN :t2 AND :t1
            GROUP BY r.product_id
        )
        SELECT r.product_id, r.c AS cur, COALESCE(b.c, 0) AS base
        FROM recent r LEFT JOIN baseline b USING (product_id)
        WHERE r.c >= 3 AND r.c >= COALESCE(b.c, 0) * 3
        """
        rows = db.execute(
            text(sql), {"category": category, "t1": t1, "t2": t2}
        ).mappings().all()
        return [
            SignalCandidate(
                signal_type="review_surge",
                entity=r["product_id"],
                summary=(
                    f"竞品 {r['product_id']} 近 7 天新增评论 {r['cur']} 条"
                    f"（前 30 天基线 {r['base']} 条），增长异常，疑似爆款或舆情事件"
                ),
                confidence="high" if r["cur"] >= 10 else "medium",
            )
            for r in rows
        ]
