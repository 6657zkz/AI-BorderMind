from ..contracts import EvidenceDefinition

MARKET_PRICE_BAND = EvidenceDefinition(
    evidence_id="market-price-band",
    purpose="Market price distribution evidence.",
    metric_ids=frozenset({"price"}),
)
