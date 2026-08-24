"""选品域算子：需求端与机会评分。"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from ..base import Operator
from ._helpers import days_to_ms, now_ms


class SearchVolumeTrendParams(BaseModel):
    category_id: str
    market_code: str
    days: int = Field(default=30, ge=1, le=365)


class SearchVolumeTrend(Operator):
    name = "search_volume_trend"
    description = "类目在市场下的搜索量时序（需求端原始值，增长趋势在指标层算）"
    outputs = "[{ts, volume}] 按时间升序"
    param_schema = SearchVolumeTrendParams

    def _build_sql(self, category_id: str, market_code: str, days: int, **kw) -> tuple[str, dict]:
        sql = """
        SELECT ts, volume
        FROM search_volume
        WHERE category_id = :category_id AND market_code = :market_code
          AND ts >= :start_ts
        ORDER BY ts
        """
        return sql, {
            "category_id": category_id,
            "market_code": market_code,
            "start_ts": now_ms() - days_to_ms(days),
        }


class MarketOpportunityParams(BaseModel):
    category_id: str
    market_code: str


class MarketOpportunityQuery(Operator):
    name = "market_opportunity"
    description = "读 AI 分析层(Gold)：类目-市场的机会综合评分 + 可解释归因 drivers_json"
    outputs = "最新一条 market_opportunity（demand/competition/price_band_gap/opportunity_score/drivers_json）"
    param_schema = MarketOpportunityParams

    def _build_sql(self, category_id: str, market_code: str, **kw) -> tuple[str, dict]:
        sql = """
        SELECT demand_score, competition_score, price_band_gap,
               opportunity_score, drivers_json, ts
        FROM market_opportunity
        WHERE category_id = :category_id AND market_code = :market_code
        ORDER BY ts DESC
        LIMIT 1
        """
        return sql, {"category_id": category_id, "market_code": market_code}


class AspectComplaintShareParams(BaseModel):
    category_id: str
    days: int = Field(default=90, ge=1, le=730)


class AspectComplaintShare(Operator):
    name = "aspect_complaint_share"
    description = "类目下差评方面分布（差评即需求：高频负面方面 = 未满足的需求缺口）"
    outputs = "[{aspect, cnt, share}] share 为该方面占类目全部差评的比例"
    param_schema = AspectComplaintShareParams

    def _build_sql(self, category_id: str, days: int, **kw) -> tuple[str, dict]:
        sql = """
        WITH complaints AS (
            SELECT ra.aspect
            FROM review_aspect ra
            JOIN product p ON p.product_id = ra.product_id
            JOIN review r ON r.review_id = ra.review_id
            WHERE p.category_id = :category_id
              AND ra.polarity = 'neg'
              AND r.ts >= :start_ts
        )
        SELECT aspect, count(*) AS cnt,
               round(count(*) * 1.0 / sum(count(*)) OVER (), 4) AS share
        FROM complaints
        GROUP BY aspect
        ORDER BY cnt DESC
        """
        return sql, {"category_id": category_id, "start_ts": now_ms() - days_to_ms(days)}
