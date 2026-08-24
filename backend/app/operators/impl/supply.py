"""供应链域算子：成本端与风险 + 内部成本结构。"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from ..base import Operator
from ._helpers import days_to_ms, now_ms


class SupplySignalQueryParams(BaseModel):
    signal_type: str = Field(
        description="freight_index / fx_rate / raw_material / port_congestion / tariff"
    )
    region: str | None = None
    days: int = Field(default=90, ge=1, le=730)


class SupplySignalQuery(Operator):
    name = "supply_signal_query"
    description = "供应链信号时序（海运费/汇率/原料/拥堵/关税）——跨境成本端与风险"
    outputs = "[{ts, signal_type, region, value, unit, source}]"
    param_schema = SupplySignalQueryParams

    def _build_sql(
        self, signal_type: str, region: str | None, days: int, **kw
    ) -> tuple[str, dict]:
        sql = """
        SELECT ts, signal_type, region, value, unit, source
        FROM supply_signal
        WHERE signal_type = :signal_type
          AND ts >= :start_ts
        """
        bind = {"signal_type": signal_type, "start_ts": now_ms() - days_to_ms(days)}
        if region is not None:
            sql += " AND region = :region"
            bind["region"] = region
        sql += "\n        ORDER BY ts"
        return sql, bind


class InternalSkuParams(BaseModel):
    merchant_id: str
    category_id: str | None = None


class InternalSkuQuery(Operator):
    name = "internal_sku_query"
    description = "读内部数据层(L2)：商家 SKU 成本结构（COGS/物流/佣金/目标毛利）——卖家自身视角"
    outputs = "[{sku, category_id, market_code, cost_cogs, shipping_cost, commission_rate, target_margin}]"
    param_schema = InternalSkuParams

    def _build_sql(self, merchant_id: str, category_id: str | None, **kw) -> tuple[str, dict]:
        sql = """
        SELECT sku, category_id, market_code, cost_cogs, shipping_cost,
               commission_rate, target_margin
        FROM internal_sku
        WHERE merchant_id = :merchant_id
        """
        bind = {"merchant_id": merchant_id}
        if category_id is not None:
            sql += " AND category_id = :category_id"
            bind["category_id"] = category_id
        return sql, bind
