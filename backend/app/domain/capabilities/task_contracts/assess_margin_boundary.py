"""毛利边界评估任务契约。"""

from ..contracts import InputRequirement, OutputField, TaskContractDefinition

ASSESS_MARGIN_BOUNDARY = TaskContractDefinition(
    # 任务 ID 同时作为目录引用和 ExecutionPlan 节点 ID。
    task_id="margin-check",
    # 任务的业务目的，不包含具体毛利计算实现。
    purpose="Assess the margin boundary.",
    # 成本边界是不可通过猜测补齐的硬输入，缺失时直接拒绝规划。
    input_requirements=(InputRequirement("cost_boundary", clarifiable=False),),
    # 该任务允许使用的受控毛利计算 Operator。
    allowed_operator_ids=frozenset({"margin-calculation"}),
    # 任务成功后提供给 recommendation 节点的结构化输出。
    output_fields=(OutputField("margin_assessment", "margin_assessment"),),
    # 任务要求的毛利 Evidence 类型。
    evidence_requirements=("margin-assessment",),
)
