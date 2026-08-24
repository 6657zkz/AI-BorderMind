"""算子注册表：本体解析 / LLM 依据 name + description 从库中选算子。"""

from __future__ import annotations

from .base import Operator, OperatorError
from .impl.competition import ProductPositionQuery, ReviewSentiment
from .impl.market import AspectComplaintShare, MarketOpportunityQuery, SearchVolumeTrend
from .impl.pricing import CompetitorPriceHistory, PricePercentile, PricingBandQuery
from .impl.supply import InternalSkuQuery, SupplySignalQuery

_OPERATOR_CLASSES = (
    SearchVolumeTrend,
    MarketOpportunityQuery,
    AspectComplaintShare,
    PricePercentile,
    PricingBandQuery,
    CompetitorPriceHistory,
    ProductPositionQuery,
    ReviewSentiment,
    SupplySignalQuery,
    InternalSkuQuery,
)

OPERATORS: dict[str, Operator] = {cls.name: cls() for cls in _OPERATOR_CLASSES}


def get_operator(name: str) -> Operator:
    try:
        return OPERATORS[name]
    except KeyError:
        raise OperatorError(f"未知算子: {name}") from None


def list_operators() -> list[dict]:
    """给本体解析 / LLM 选算子的元数据清单。"""
    return [
        {
            "name": op.name,
            "description": op.description,
            "outputs": op.outputs,
            "param_schema": op.param_schema.model_json_schema(),
        }
        for op in OPERATORS.values()
    ]
