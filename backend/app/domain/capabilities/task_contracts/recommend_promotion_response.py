"""促销响应建议任务契约。"""

from ..contracts import InputRequirement, OutputField, TaskContractDefinition

RECOMMEND_PROMOTION_RESPONSE = TaskContractDefinition(
    # 任务 ID 同时作为目录引用和 ExecutionPlan 节点 ID。
    task_id="recommendation",
    # 任务的业务目的；实际专家判断不在目录注册阶段执行。
    purpose="Compare promotion response options.",
    # 前两个输入来自直接依赖的输出，target_margin 来自 Graph 或项目画像。
    input_requirements=(
        InputRequirement("price_band"),
        InputRequirement("margin_assessment"),
        InputRequirement("target_margin", accepted_value_shape="percentage"),
    ),
    # 只有显式依赖的任务输出可以被编译器绑定到本任务。
    dependencies=("price-band", "margin-check"),
    # 本任务允许使用的专家角色白名单。
    allowed_expert_role_ids=frozenset({"pricing-expert"}),
    # 任务成功后生成的结构化建议字段。
    output_fields=(OutputField("recommendation", "recommendation"),),
    # 建议任务需要引用的 Evidence 类型。
    evidence_requirements=("promotion-recommendation",),
)
