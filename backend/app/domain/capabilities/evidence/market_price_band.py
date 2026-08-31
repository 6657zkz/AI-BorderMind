"""市场价格带 Evidence 的目录定义。"""

from ..contracts import EvidenceDefinition

MARKET_PRICE_BAND = EvidenceDefinition(
    # Evidence 的稳定目录 ID，Graph 和任务通过该 ID 引用它。
    evidence_id="market-price-band",
    # Evidence 能够支持的业务判断用途。
    purpose="Market price distribution evidence.",
    # Evidence 关联的已注册指标，保证证据可以追溯到业务语义。
    metric_ids=frozenset({"price"}),
)
