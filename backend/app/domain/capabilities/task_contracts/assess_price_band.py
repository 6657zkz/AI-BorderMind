"""市场价格带评估任务契约。"""

from ..contracts import InputRequirement, OutputField, TaskContractDefinition

ASSESS_PRICE_BAND = TaskContractDefinition(
    # 任务 ID 同时作为目录引用和 ExecutionPlan 节点 ID。
    task_id="price-band",
    # 任务的业务目的，不包含具体执行代码。
    purpose="Assess the market price band.",
    # 任务必须接收的输入；缺失时默认可以向用户发起澄清。
    input_requirements=(InputRequirement("market"),),
    # 该任务允许使用的受控 Operator 白名单。
    allowed_operator_ids=frozenset({"price-percentiles"}),
    # 任务成功后可供下游节点绑定的结构化输出。
    output_fields=(OutputField("price_band", "price_distribution"),),
    # 任务需要产出或引用的 Evidence 类型。
    evidence_requirements=("market-price-band",),
)
