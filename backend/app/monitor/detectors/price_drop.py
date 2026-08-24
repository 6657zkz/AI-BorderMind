"""竞品降价检测：近 7 天最新价 vs 前 30 天基准价，跌幅超 10% 视为价格战信号。"""

from __future__ import annotations

from typing import Any, ClassVar

from sqlalchemy import text
from sqlalchemy.orm import Session

from .base import Detector, SignalCandidate

_WINDOW_DAY = 86_400_000


class PriceDropDetector(Detector):
    name = "price_drop"
    description = "竞品最新价较前 30 天下跌超 10%，提示价格战"

    def detect(self, db: Session, ctx: dict[str, Any]) -> list[SignalCandidate]:
        market = ctx.get("market_code")
        if not market:
            return []
        now = 0  # 实际用最新时间戳：取最近 price_tick 时间窗
        latest_ts = db.execute(text("SELECT COALESCE(max(ts), :n) FROM price_tick"), {"n": now}).scalar()
        if not latest_ts:
            return []
        t1 = latest_ts - 7 * _WINDOW_DAY
        t2 = latest_ts - 30 * _WINDOW_DAY
        sql = """
        WITH latest AS (
            SELECT DISTINCT ON (product_id) product_id, price
            FROM price_tick
            WHERE market_code = :market AND ts >= :t1
            ORDER BY product_id, ts DESC
        ),
        baseline AS (
            SELECT DISTINCT ON (product_id) product_id, price
            FROM price_tick
            WHERE market_code = :market AND ts BETWEEN :t2 AND :t1
            ORDER BY product_id, ts DESC
        )
        SELECT l.product_id, l.price AS cur, b.price AS prev,
               round((l.price - b.price) / b.price, 4) AS chg
        FROM latest l JOIN baseline b USING (product_id)
        WHERE b.price > 0 AND l.price < b.price * 0.9
        """
        rows = db.execute(text(sql), {"market": market, "t1": t1, "t2": t2}).mappings().all()
        signals = []
        for r in rows:
            signals.append(
                SignalCandidate(
                    signal_type="pricing_change",
                    entity=r["product_id"],
                    summary=(
                        f"竞品 {r['product_id']} 降价 {(1 - r['cur'] / r['prev']) * 100:.0f}%"
                        f"（{float(r['prev']):.2f} → {float(r['cur']):.2f}）"
                    ),
                    confidence="high" if r["chg"] <= -0.15 else "medium",
                )
            )
        return signals
