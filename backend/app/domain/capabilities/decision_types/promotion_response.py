"""竞品促销应对决策类型的任务蓝图和白名单。"""

from ..contracts import DecisionTypeDefinition

PROMOTION_RESPONSE = DecisionTypeDefinition(
    # 决策类型的稳定目录 ID，也是 DecisionGraph 的引用值。
    decision_type_id="promotion-response",
    # 只有启用的决策类型才能被 planning 编译为 ExecutionPlan。
    enabled=True,
    # 决策类型允许展开的任务契约 ID，任务自身定义输入和依赖。
    task_contract_ids=("price-band", "margin-check", "recommendation"),
    # DecisionGraph.scope 中必须允许并最终满足的业务上下文字段。
    required_context_keys=frozenset({"market", "cost_boundary", "target_margin"}),
    # DecisionGraph.scope 中允许但不是所有请求都必须提供的上下文。
    optional_context_keys=frozenset({"competitor"}),
    # DecisionGraph.constraints 可以携带的业务约束字段。
    allowed_constraint_keys=frozenset({"response_boundary"}),
    # Graph 可以请求的 Evidence 白名单。
    allowed_evidence_ids=frozenset(
        {"market-price-band", "margin-assessment", "promotion-recommendation"}
    ),
    # Graph 可以声明的实体比较关系类型。
    allowed_comparison_kinds=frozenset({"competitor_to_own"}),
)
