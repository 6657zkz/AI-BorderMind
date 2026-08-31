from .contracts import EntityDefinition, MetricDefinition

COMPETITOR_PRODUCT = EntityDefinition("competitor-product", "A competitor product.")
OWN_PRODUCT = EntityDefinition("own-product", "An owned product.")
MARKET = EntityDefinition("market", "A sales market.")

PRICE = MetricDefinition("price", "Observed or proposed product price.", "currency_amount")
MARGIN = MetricDefinition("margin", "Product margin.", "percentage")

ENTITIES = (COMPETITOR_PRODUCT, OWN_PRODUCT, MARKET)
METRICS = (PRICE, MARGIN)
