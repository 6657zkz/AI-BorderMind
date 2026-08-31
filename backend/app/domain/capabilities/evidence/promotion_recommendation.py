from ..contracts import EvidenceDefinition

PROMOTION_RECOMMENDATION = EvidenceDefinition(
    evidence_id="promotion-recommendation",
    purpose="Structured promotion response recommendation evidence.",
    metric_ids=frozenset({"price", "margin"}),
)
