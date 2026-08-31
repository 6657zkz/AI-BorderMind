from ..contracts import OperatorDefinition

PRICE_PERCENTILES = OperatorDefinition(
    operator_id="price-percentiles",
    purpose="Calculate market price percentiles.",
    input_keys=("market",),
    output_keys=("price_band",),
)
