"""市场价格分位数 Operator 的目录元数据。"""

from ..contracts import OperatorDefinition

PRICE_PERCENTILES = OperatorDefinition(
    # Operator 的稳定目录 ID，任务通过该 ID 声明允许使用它。
    operator_id="price-percentiles",
    # Operator 提供的确定性数据能力说明。
    purpose="Calculate market price percentiles.",
    # 允许接收的输入字段名，不是实际执行参数。
    input_keys=("market",),
    # 允许产出的结构化字段名，不代表本阶段已经执行查询或计算。
    output_keys=("price_band",),
)
