"""需求趋势突变检测：近 7 天平均搜索量 vs 前 28 天，增速/跌幅超 20% 视为趋势转向。"""

from __future__ import annotations

from typing import Any, ClassVar

from sqlalchemy import text
from sqlalchemy.orm import Session

from .base import Detector, SignalCandidate

_WINDOW_DAY = 86_400_000


class TrendShiftDetector(Detector):
    name = "trend_shift"
    description = "类目搜索量近 7 天较前 28 天变化超 ±20%，需求趋势转向"

    def detect(self, db: Session, ctx: dict[str, Any]) -> list[SignalCandidate]:
        category = ctx.get("category_id")
        market = ctx.get("market_code")
        if not category or not market:
            return []
        latest_ts = db.execute(
            text("SELECT COALESCE(max(ts), 0) FROM search_volume")
        ).scalar()
        t1 = latest_ts - 7 * _WINDOW_DAY
        t2 = latest_ts - 28 * _WINDOW_DAY
        sql = """
        WITH recent AS (
            SELECT avg(volume) AS v FROM search_volume
            WHERE category_id = :category AND market_code = :market AND ts >= :t1
        ),
        baseline AS (
            SELECT avg(volume) AS v FROM search_volume
            WHERE category_id = :category AND market_code = :market AND ts BETWEEN :t2 AND :t1
        )
        SELECT r.v AS cur, b.v AS prev,
               CASE WHEN b.v > 0 THEN (r.v - b.v) / b.v ELSE NULL END AS chg
        FROM recent r, baseline b
        """
        row = db.execute(
            text(sql), {"category": category, "market": market, "t1": t1, "t2": t2}
        ).mappings().first()
        if row is None or row["chg"] is None or abs(row["chg"]) < 0.2:
            return []
        chg = float(row["chg"])
        direction = "上涨" if chg > 0 else "下滑"
        return [
            SignalCandidate(
                signal_type="trend_shift",
                entity=category,
                summary=(
                    f"类目 {category} 在 {market} 市场搜索量近 7 天较前 28 天{direction} "
                    f"{abs(chg) * 100:.0f}%（{float(row['prev']):.0f} → {float(row['cur']):.0f}）"
                ),
                confidence="high" if abs(chg) >= 0.5 else "medium",
            )
        ]
