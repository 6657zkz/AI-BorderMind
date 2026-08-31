"""毛利计算 Operator 的目录元数据。"""

from ..contracts import OperatorDefinition

MARGIN_CALCULATION = OperatorDefinition(
    # Operator 的稳定目录 ID，任务通过该 ID 声明允许使用它。
    operator_id="margin-calculation",
    # Operator 提供的确定性毛利计算能力说明。
    purpose="Calculate margin against a cost boundary.",
    # 允许接收的输入字段名，不是实际执行参数。
    input_keys=("cost_boundary", "target_margin"),
    # 允许产出的结构化字段名，不包含实际计算逻辑。
    output_keys=("margin_assessment",),
)
