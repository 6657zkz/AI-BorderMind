from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.domain.capabilities.contracts import (
    DecisionTypeDefinition,
    InputRequirement,
    OutputField,
    TaskContractDefinition,
)
from app.domain.planning import Comparison, DecisionGraph, EvidenceRequirement, TriggerContext


@dataclass
class InMemoryCatalog:
    """为 planning 测试提供最小、可变且不访问外部系统的能力目录。"""

    decision_types: dict[str, DecisionTypeDefinition]
    task_contracts: dict[str, TaskContractDefinition]
    version: str = "catalog-v1"
    entities: frozenset[str] = frozenset({"competitor-product", "own-product"})
    metrics: frozenset[str] = frozenset({"price", "margin"})
    operators: frozenset[str] = frozenset({"price-percentiles"})
    expert_roles: frozenset[str] = frozenset({"pricing-expert"})
    evidence: frozenset[str] = frozenset({"market-price-band"})

    def get_decision_type(self, decision_type_id: str):
        """按 ID 返回测试决策类型定义。"""
        return self.decision_types.get(decision_type_id)

    def get_task_contract(self, task_id: str):
        """按 ID 返回测试任务契约。"""
        return self.task_contracts.get(task_id)

    def has_entity(self, entity_id: str) -> bool:
        """判断测试实体是否注册。"""
        return entity_id in self.entities

    def has_metric(self, metric_id: str) -> bool:
        """判断测试指标是否注册。"""
        return metric_id in self.metrics

    def has_operator(self, operator_id: str) -> bool:
        """判断测试 Operator 是否注册。"""
        return operator_id in self.operators

    def has_expert_role(self, expert_role_id: str) -> bool:
        """判断测试专家角色是否注册。"""
        return expert_role_id in self.expert_roles

    def has_evidence(self, evidence_id: str) -> bool:
        """判断测试证据类型是否注册。"""
        return evidence_id in self.evidence


@pytest.fixture
def catalog() -> InMemoryCatalog:
    """构造含并行任务和汇总任务的完整测试能力目录。"""
    price_band = TaskContractDefinition(
        task_id="price-band",
        purpose="Assess market price band.",
        input_requirements=(InputRequirement("market"),),
        allowed_operator_ids=frozenset({"price-percentiles"}),
        output_fields=(OutputField("price_band", "price_distribution"),),
        evidence_requirements=("market-price-band",),
    )
    margin = TaskContractDefinition(
        task_id="margin-check",
        purpose="Assess margin boundary.",
        input_requirements=(InputRequirement("cost_boundary", clarifiable=False),),
        output_fields=(OutputField("margin_assessment", "margin_assessment"),),
    )
    recommendation = TaskContractDefinition(
        task_id="recommendation",
        purpose="Compare response options.",
        input_requirements=(
            InputRequirement("price_band"),
            InputRequirement("margin_assessment"),
            InputRequirement("target_margin", accepted_value_shape="percentage"),
        ),
        dependencies=("price-band", "margin-check"),
        allowed_expert_role_ids=frozenset({"pricing-expert"}),
        output_fields=(OutputField("recommendation", "recommendation"),),
    )
    decision_type = DecisionTypeDefinition(
        decision_type_id="promotion-response",
        enabled=True,
        task_contract_ids=("price-band", "margin-check", "recommendation"),
        required_context_keys=frozenset({"market", "cost_boundary", "target_margin"}),
        optional_context_keys=frozenset({"competitor"}),
        allowed_constraint_keys=frozenset({"response_boundary"}),
        allowed_evidence_ids=frozenset({"market-price-band"}),
        allowed_comparison_kinds=frozenset({"competitor_to_own"}),
    )
    return InMemoryCatalog(
        decision_types={decision_type.decision_type_id: decision_type},
        task_contracts={contract.task_id: contract for contract in (price_band, margin, recommendation)},
    )


@pytest.fixture
def valid_graph() -> DecisionGraph:
    """构造与测试目录完全匹配的有效业务图。"""
    return DecisionGraph(
        graph_id="graph-1",
        catalog_version="catalog-v1",
        decision_type_id="promotion-response",
        trigger=TriggerContext(source="user", reference_id="message-1"),
        scope={"market": "US", "cost_boundary": 20, "target_margin": 0.3},
        constraints={"response_boundary": "no_price_below_cost"},
        required_evidence=(EvidenceRequirement("market-price-band", "price"),),
        comparisons=(Comparison("competitor_to_own", "competitor-product", "own-product"),),
        entity_references=frozenset({"competitor-product", "own-product"}),
        metric_references=frozenset({"price", "margin"}),
    )
