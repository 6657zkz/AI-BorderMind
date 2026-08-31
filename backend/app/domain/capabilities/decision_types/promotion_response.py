from ..contracts import DecisionTypeDefinition

PROMOTION_RESPONSE = DecisionTypeDefinition(
    decision_type_id="promotion-response",
    enabled=True,
    task_contract_ids=("price-band", "margin-check", "recommendation"),
    required_context_keys=frozenset({"market", "cost_boundary", "target_margin"}),
    optional_context_keys=frozenset({"competitor"}),
    allowed_constraint_keys=frozenset({"response_boundary"}),
    allowed_evidence_ids=frozenset(
        {"market-price-band", "margin-assessment", "promotion-recommendation"}
    ),
    allowed_comparison_kinds=frozenset({"competitor_to_own"}),
)
