from ..contracts import ExpertRoleDefinition, OutputField

PRICING_EXPERT = ExpertRoleDefinition(
    expert_role_id="pricing-expert",
    purpose="Evaluate promotion response options using verified pricing evidence.",
    required_evidence_ids=frozenset({"market-price-band", "margin-assessment"}),
    output_fields=(OutputField("recommendation", "recommendation"),),
)
