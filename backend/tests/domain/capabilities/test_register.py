import pytest

from app.domain.capabilities import (
    CapabilityRegistry,
    EntityDefinition,
    InvalidCapabilityCatalogError,
    TaskContractDefinition,
    DuplicateCapabilityError,
    build_capability_catalog,
)


def test_default_catalog_contains_promotion_response():
    catalog = build_capability_catalog()

    assert catalog.version == "catalog-v1"
    assert catalog.get_decision_type("promotion-response") is not None
    assert catalog.get_task_contract("recommendation") is not None
    assert catalog.has_entity("competitor-product")
    assert catalog.has_metric("price")
    assert catalog.has_operator("price-percentiles")
    assert catalog.has_expert_role("pricing-expert")
    assert catalog.has_evidence("market-price-band")


def test_registry_rejects_duplicate_ids():
    registry = CapabilityRegistry("catalog-v1")
    entity = EntityDefinition("product", "A product.")

    registry.register_entity(entity)

    with pytest.raises(DuplicateCapabilityError):
        registry.register_entity(entity)


def test_freeze_detaches_catalog_from_registry():
    registry = CapabilityRegistry("catalog-v1")
    registry.register_entity(EntityDefinition("product", "A product."))

    catalog = registry.freeze()

    with pytest.raises(InvalidCapabilityCatalogError):
        registry.register_entity(EntityDefinition("market", "A market."))

    assert catalog.has_entity("product")
    assert not catalog.has_entity("market")


def test_freeze_rejects_unknown_task_reference():
    from app.domain.capabilities import DecisionTypeDefinition

    registry = CapabilityRegistry("catalog-v1")
    registry.register_decision_type(
        DecisionTypeDefinition(
            decision_type_id="decision",
            enabled=True,
            task_contract_ids=("missing-task",),
        )
    )

    with pytest.raises(InvalidCapabilityCatalogError):
        registry.freeze()


def test_frozen_catalog_has_no_registration_method():
    catalog = build_capability_catalog()

    assert not hasattr(catalog, "register_entity")
    assert catalog.get_task_contract("missing") is None
    assert not catalog.has_operator("missing")
