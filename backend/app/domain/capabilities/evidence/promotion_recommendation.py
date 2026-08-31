"""促销响应建议 Evidence 的目录定义。"""

from ..contracts import EvidenceDefinition

PROMOTION_RECOMMENDATION = EvidenceDefinition(
    # Evidence 的稳定目录 ID，建议任务通过该 ID 声明所需证据。
    evidence_id="promotion-recommendation",
    # Evidence 用于承载结构化促销响应建议的依据。
    purpose="Structured promotion response recommendation evidence.",
    # 建议同时关联价格和毛利指标，支持结果审阅。
    metric_ids=frozenset({"price", "margin"}),
)
