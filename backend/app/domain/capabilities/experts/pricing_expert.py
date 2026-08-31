"""定价专家角色的静态 Playbook 契约元数据。"""

from ..contracts import ExpertRoleDefinition, OutputField

PRICING_EXPERT = ExpertRoleDefinition(
    # 专家角色的稳定目录 ID，任务通过该 ID 声明允许使用它。
    expert_role_id="pricing-expert",
    # 专家负责的业务判断范围，不代表这里会创建 Agent 或调用 LLM。
    purpose="Evaluate promotion response options using verified pricing evidence.",
    # 专家判断前必须具备的证据类型。
    required_evidence_ids=frozenset({"market-price-band", "margin-assessment"}),
    # 专家角色允许产出的结构化结果字段。
    output_fields=(OutputField("recommendation", "recommendation"),),
)
