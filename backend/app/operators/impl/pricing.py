"""定价域算子：价格带 / 成本地板 / 竞品价格时序。"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from ..base import Operator
from ._helpers import days_to_ms, now_ms


class PricePercentileParams(BaseModel):
    category_id: str
    market_code: str
    days: int = Field(default=30, ge=1, le=365)


class PricePercentile(Operator):
    name = "price_percentile"
    description = "类目-市场竞品最新价的价格分位 p25/p50/p75（指标查询时算，不落库）"
    outputs = "{p25, p50, p75, n_products}"
    param_schema = PricePercentileParams

    def _build_sql(self, category_id: str, market_code: str, days: int, **kw) -> tuple[str, dict]:
        sql = """
        WITH latest AS (
            SELECT DISTINCT ON (pt.product_id) pt.price
            FROM price_tick pt
            JOIN product p ON p.product_id = pt.product_id
            WHERE p.category_id = :category_id
              AND pt.market_code = :market_code
              AND pt.ts >= :start_ts
            ORDER BY pt.product_id, pt.ts DESC
        )
        SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY price) AS p25,
               percentile_cont(0.50) WITHIN GROUP (ORDER BY price) AS p50,
               percentile_cont(0.75) WITHIN GROUP (ORDER BY price) AS p75,
               count(*) AS n_products
        FROM latest
        """
        return sql, {
            "category_id": category_id,
            "market_code": market_code,
            "start_ts": now_ms() - days_to_ms(days),
        }


class PricingBandParams(BaseModel):
    category_id: str
    market_code: str


class PricingBandQuery(Operator):
    name = "pricing_band"
    description = "读 AI 分析层(Gold)：类目-市场定价带（p25/p50/p75 + 完整成本地板 price_floor + 建议价格窗）"
    outputs = "最新一条 pricing_band"
    param_schema = PricingBandParams

    def _build_sql(self, category_id: str, market_code: str, **kw) -> tuple[str, dict]:
        sql = """
        SELECT p25, p50, p75, price_floor, recommended_window, ts
        FROM pricing_band
        WHERE category_id = :category_id AND market_code = :market_code
        ORDER BY ts DESC
        LIMIT 1
        """
        return sql, {"category_id": category_id, "market_code": market_code}


class CompetitorPriceHistoryParams(BaseModel):
    product_id: str
    days: int = Field(default=90, ge=1, le=730)


class CompetitorPriceHistory(Operator):
    name = "competitor_price_history"
    description = "单个竞品 Listing 的价格 + 销售排名时序（定价与竞争度信号）"
    outputs = "[{ts, price, discount_pct, buybox_price, sales_rank}]"
    param_schema = CompetitorPriceHistoryParams

    def _build_sql(self, product_id: str, days: int, **kw) -> tuple[str, dict]:
        sql = """
        SELECT ts, price, discount_pct, buybox_price, sales_rank
        FROM price_tick
        WHERE product_id = :product_id AND ts >= :start_ts
        ORDER BY ts
        """
        return sql, {"product_id": product_id, "start_ts": now_ms() - days_to_ms(days)}
