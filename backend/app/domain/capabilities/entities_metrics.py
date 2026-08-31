"""竞品促销应对所需的实体和指标目录定义。"""

from .contracts import EntityDefinition, MetricDefinition

# 可被 DecisionGraph 引用和比较的业务实体。
COMPETITOR_PRODUCT = EntityDefinition("competitor-product", "A competitor product.")
OWN_PRODUCT = EntityDefinition("own-product", "An owned product.")
MARKET = EntityDefinition("market", "A sales market.")

# 可被 Evidence 关联的业务指标；semantic_type 表示领域语义，不是 Python 类型。
PRICE = MetricDefinition("price", "Observed or proposed product price.", "currency_amount")
MARGIN = MetricDefinition("margin", "Product margin.", "percentage")

# 总注册入口按这两个集合批量写入 registry。
ENTITIES = (COMPETITOR_PRODUCT, OWN_PRODUCT, MARKET)
METRICS = (PRICE, MARGIN)
