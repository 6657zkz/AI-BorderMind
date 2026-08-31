from ..contracts import OperatorDefinition

MARGIN_CALCULATION = OperatorDefinition(
    operator_id="margin-calculation",
    purpose="Calculate margin against a cost boundary.",
    input_keys=("cost_boundary", "target_margin"),
    output_keys=("margin_assessment",),
)
