from ..contracts import InputRequirement, OutputField, TaskContractDefinition

ASSESS_PRICE_BAND = TaskContractDefinition(
    task_id="price-band",
    purpose="Assess the market price band.",
    input_requirements=(InputRequirement("market"),),
    allowed_operator_ids=frozenset({"price-percentiles"}),
    output_fields=(OutputField("price_band", "price_distribution"),),
    evidence_requirements=("market-price-band",),
)
