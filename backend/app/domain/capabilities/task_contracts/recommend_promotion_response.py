from ..contracts import InputRequirement, OutputField, TaskContractDefinition

RECOMMEND_PROMOTION_RESPONSE = TaskContractDefinition(
    task_id="recommendation",
    purpose="Compare promotion response options.",
    input_requirements=(
        InputRequirement("price_band"),
        InputRequirement("margin_assessment"),
        InputRequirement("target_margin", accepted_value_shape="percentage"),
    ),
    dependencies=("price-band", "margin-check"),
    allowed_expert_role_ids=frozenset({"pricing-expert"}),
    output_fields=(OutputField("recommendation", "recommendation"),),
    evidence_requirements=("promotion-recommendation",),
)
