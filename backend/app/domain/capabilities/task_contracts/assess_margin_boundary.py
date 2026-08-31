from ..contracts import InputRequirement, OutputField, TaskContractDefinition

ASSESS_MARGIN_BOUNDARY = TaskContractDefinition(
    task_id="margin-check",
    purpose="Assess the margin boundary.",
    input_requirements=(InputRequirement("cost_boundary", clarifiable=False),),
    allowed_operator_ids=frozenset({"margin-calculation"}),
    output_fields=(OutputField("margin_assessment", "margin_assessment"),),
    evidence_requirements=("margin-assessment",),
)
