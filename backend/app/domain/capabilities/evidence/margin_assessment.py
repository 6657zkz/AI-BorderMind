"""毛利边界评估 Evidence 的目录定义。"""

from ..contracts import EvidenceDefinition

MARGIN_ASSESSMENT = EvidenceDefinition(
    # Evidence 的稳定目录 ID，任务通过该 ID 声明所需证据。
    evidence_id="margin-assessment",
    # Evidence 能够支持的业务判断用途。
    purpose="Margin boundary assessment evidence.",
    # Evidence 关联的已注册毛利指标。
    metric_ids=frozenset({"margin"}),
)
