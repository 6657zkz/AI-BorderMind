"""竞品域算子：竞品定位 / 评论情感。"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel

from ..base import Operator


class ProductPositionParams(BaseModel):
    product_id: str
    market_code: str


class ProductPositionQuery(Operator):
    name = "product_position"
    description = "读 AI 分析层(Gold)：竞品优劣定位（top_pros/top_cons 方面频次 + 定位标签）"
    outputs = "最新一条 product_position"
    param_schema = ProductPositionParams

    def _build_sql(self, product_id: str, market_code: str, **kw) -> tuple[str, dict]:
        sql = """
        SELECT top_pros, top_cons, positioning_label, ts
        FROM product_position
        WHERE product_id = :product_id AND market_code = :market_code
        ORDER BY ts DESC
        LIMIT 1
        """
        return sql, {"product_id": product_id, "market_code": market_code}


class ReviewSentimentParams(BaseModel):
    product_id: str


class ReviewSentiment(Operator):
    name = "review_sentiment"
    description = "单个产品评论的方面×情感分布（正/负/中性计数 + 平均情感分）"
    outputs = "[{aspect, polarity, cnt, avg_score}] 按计数降序"
    param_schema = ReviewSentimentParams

    def _build_sql(self, product_id: str, **kw) -> tuple[str, dict]:
        sql = """
        SELECT ra.aspect, ra.polarity, count(*) AS cnt,
               round(avg(ra.score)::numeric, 4) AS avg_score
        FROM review_aspect ra
        WHERE ra.product_id = :product_id
        GROUP BY ra.aspect, ra.polarity
        ORDER BY cnt DESC
        """
        return sql, {"product_id": product_id}
