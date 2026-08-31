import pytest

from app.domain.capabilities import (
    CapabilityRegistry,
    DecisionTypeDefinition,
    DuplicateCapabilityError,
    EntityDefinition,
    InvalidCapabilityCatalogError,
    build_capability_catalog,
)


def test_default_catalog_contains_promotion_response():
    """默认总目录应包含可供 planning 使用的完整示例能力组合。"""
    catalog = build_capability_catalog()

    # 版本用于保证 Graph 和目录的语义来自同一份定义。
    assert catalog.version == "catalog-v1"
    # 验证决策类型和任务契约已完成注册。
    assert catalog.get_decision_type("promotion-response") is not None
    assert catalog.get_task_contract("recommendation") is not None
    # 验证 Graph 可能引用的基础实体、指标和 Evidence 均已登记。
    assert catalog.has_entity("competitor-product")
    assert catalog.has_metric("price")
    assert catalog.has_operator("price-percentiles")
    assert catalog.has_expert_role("pricing-expert")
    assert catalog.has_evidence("market-price-band")


def test_registry_rejects_duplicate_ids():
    """同一类型的重复 ID 不能覆盖先注册的定义。"""
    registry = CapabilityRegistry("catalog-v1")
    entity = EntityDefinition("product", "A product.")

    registry.register_entity(entity)

    with pytest.raises(DuplicateCapabilityError):
        registry.register_entity(entity)


def test_freeze_detaches_catalog_from_registry():
    """冻结目录应与构建器隔离，并禁止构建器继续改变目录。"""
    registry = CapabilityRegistry("catalog-v1")
    registry.register_entity(EntityDefinition("product", "A product."))

    # freeze 返回独立的只读快照，而不是直接暴露 registry 的内部字典。
    catalog = registry.freeze()

    with pytest.raises(InvalidCapabilityCatalogError):
        registry.register_entity(EntityDefinition("market", "A market."))

    assert catalog.has_entity("product")
    assert not catalog.has_entity("market")


def test_freeze_rejects_unknown_task_reference():
    """冻结前应拒绝决策类型引用不存在的任务契约。"""
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
    """冻结后的目录只提供查询能力，不提供注册入口。"""
    catalog = build_capability_catalog()

    assert not hasattr(catalog, "register_entity")
    assert catalog.get_task_contract("missing") is None
    assert not catalog.has_operator("missing")
