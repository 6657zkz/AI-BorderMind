from ..contracts import EvidenceDefinition

MARGIN_ASSESSMENT = EvidenceDefinition(
    evidence_id="margin-assessment",
    purpose="Margin boundary assessment evidence.",
    metric_ids=frozenset({"margin"}),
)
