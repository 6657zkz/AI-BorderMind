from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .contracts import (
    CapabilityCatalog,
    DecisionTypeDefinition,
    EntityDefinition,
    EvidenceDefinition,
    ExpertRoleDefinition,
    MetricDefinition,
    OperatorDefinition,
    TaskContractDefinition,
)
from .decision_types.promotion_response import PROMOTION_RESPONSE
from .entities_metrics import ENTITIES, METRICS
from .evidence.market_price_band import MARKET_PRICE_BAND
from .evidence.margin_assessment import MARGIN_ASSESSMENT
from .evidence.promotion_recommendation import PROMOTION_RECOMMENDATION
from .experts.pricing_expert import PRICING_EXPERT
from .operators.margin_calculation import MARGIN_CALCULATION
from .operators.price_percentiles import PRICE_PERCENTILES
from .task_contracts.assess_margin_boundary import ASSESS_MARGIN_BOUNDARY
from .task_contracts.assess_price_band import ASSESS_PRICE_BAND
from .task_contracts.recommend_promotion_response import RECOMMEND_PROMOTION_RESPONSE


class DuplicateCapabilityError(ValueError):
    pass


class InvalidCapabilityCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class FrozenCapabilityCatalog(CapabilityCatalog):
    _version: str
    _entities: Mapping[str, EntityDefinition]
    _metrics: Mapping[str, MetricDefinition]
    _operators: Mapping[str, OperatorDefinition]
    _expert_roles: Mapping[str, ExpertRoleDefinition]
    _evidence: Mapping[str, EvidenceDefinition]
    _task_contracts: Mapping[str, TaskContractDefinition]
    _decision_types: Mapping[str, DecisionTypeDefinition]

    @property
    def version(self) -> str:
        return self._version

    def get_decision_type(self, decision_type_id: str) -> DecisionTypeDefinition | None:
        return self._decision_types.get(decision_type_id)

    def get_task_contract(self, task_id: str) -> TaskContractDefinition | None:
        return self._task_contracts.get(task_id)

    def has_entity(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def has_metric(self, metric_id: str) -> bool:
        return metric_id in self._metrics

    def has_operator(self, operator_id: str) -> bool:
        return operator_id in self._operators

    def has_expert_role(self, expert_role_id: str) -> bool:
        return expert_role_id in self._expert_roles

    def has_evidence(self, evidence_id: str) -> bool:
        return evidence_id in self._evidence


class CapabilityRegistry:
    def __init__(self, version: str) -> None:
        self._version = version
        self._entities: dict[str, EntityDefinition] = {}
        self._metrics: dict[str, MetricDefinition] = {}
        self._operators: dict[str, OperatorDefinition] = {}
        self._expert_roles: dict[str, ExpertRoleDefinition] = {}
        self._evidence: dict[str, EvidenceDefinition] = {}
        self._task_contracts: dict[str, TaskContractDefinition] = {}
        self._decision_types: dict[str, DecisionTypeDefinition] = {}
        self._frozen = False

    def register_entity(self, definition: EntityDefinition) -> None:
        self._register(self._entities, definition.entity_id, definition)

    def register_metric(self, definition: MetricDefinition) -> None:
        self._register(self._metrics, definition.metric_id, definition)

    def register_operator(self, definition: OperatorDefinition) -> None:
        self._register(self._operators, definition.operator_id, definition)

    def register_expert_role(self, definition: ExpertRoleDefinition) -> None:
        self._register(self._expert_roles, definition.expert_role_id, definition)

    def register_evidence(self, definition: EvidenceDefinition) -> None:
        self._register(self._evidence, definition.evidence_id, definition)

    def register_task_contract(self, definition: TaskContractDefinition) -> None:
        self._register(self._task_contracts, definition.task_id, definition)

    def register_decision_type(self, definition: DecisionTypeDefinition) -> None:
        self._register(self._decision_types, definition.decision_type_id, definition)

    def freeze(self) -> FrozenCapabilityCatalog:
        if self._frozen:
            raise InvalidCapabilityCatalogError("Capability registry has already been frozen.")
        if not self._version:
            raise InvalidCapabilityCatalogError("Capability catalog version must not be empty.")
        self._validate_references()
        self._frozen = True
        return FrozenCapabilityCatalog(
            _version=self._version,
            _entities=MappingProxyType(dict(self._entities)),
            _metrics=MappingProxyType(dict(self._metrics)),
            _operators=MappingProxyType(dict(self._operators)),
            _expert_roles=MappingProxyType(dict(self._expert_roles)),
            _evidence=MappingProxyType(dict(self._evidence)),
            _task_contracts=MappingProxyType(dict(self._task_contracts)),
            _decision_types=MappingProxyType(dict(self._decision_types)),
        )

    def _register(self, target: dict[str, object], identifier: str, definition: object) -> None:
        if self._frozen:
            raise InvalidCapabilityCatalogError("Capability registry has already been frozen.")
        if not identifier:
            raise InvalidCapabilityCatalogError("Capability IDs must not be empty.")
        if identifier in target:
            raise DuplicateCapabilityError(f"Capability ID is already registered: {identifier}")
        target[identifier] = definition

    def _validate_references(self) -> None:
        for decision_type in self._decision_types.values():
            for task_id in decision_type.task_contract_ids:
                if task_id not in self._task_contracts:
                    raise InvalidCapabilityCatalogError(
                        f"Decision type references an unknown task contract: {task_id}"
                    )
            for evidence_id in decision_type.allowed_evidence_ids:
                if evidence_id not in self._evidence:
                    raise InvalidCapabilityCatalogError(
                        f"Decision type references unknown evidence: {evidence_id}"
                    )

        for task in self._task_contracts.values():
            for dependency_id in task.dependencies:
                if dependency_id not in self._task_contracts:
                    raise InvalidCapabilityCatalogError(
                        f"Task references an unknown dependency: {dependency_id}"
                    )
            for operator_id in task.allowed_operator_ids:
                if operator_id not in self._operators:
                    raise InvalidCapabilityCatalogError(
                        f"Task references an unknown operator: {operator_id}"
                    )
            for expert_role_id in task.allowed_expert_role_ids:
                if expert_role_id not in self._expert_roles:
                    raise InvalidCapabilityCatalogError(
                        f"Task references an unknown expert role: {expert_role_id}"
                    )
            for evidence_id in task.evidence_requirements:
                if evidence_id not in self._evidence:
                    raise InvalidCapabilityCatalogError(
                        f"Task references unknown evidence: {evidence_id}"
                    )

        for evidence in self._evidence.values():
            for metric_id in evidence.metric_ids:
                if metric_id not in self._metrics:
                    raise InvalidCapabilityCatalogError(
                        f"Evidence references an unknown metric: {metric_id}"
                    )

        for expert in self._expert_roles.values():
            for evidence_id in expert.required_evidence_ids:
                if evidence_id not in self._evidence:
                    raise InvalidCapabilityCatalogError(
                        f"Expert role references unknown evidence: {evidence_id}"
                    )


def build_capability_catalog() -> FrozenCapabilityCatalog:
    registry = CapabilityRegistry(version="catalog-v1")

    for definition in ENTITIES:
        registry.register_entity(definition)
    for definition in METRICS:
        registry.register_metric(definition)

    registry.register_operator(PRICE_PERCENTILES)
    registry.register_operator(MARGIN_CALCULATION)
    registry.register_expert_role(PRICING_EXPERT)
    registry.register_evidence(MARKET_PRICE_BAND)
    registry.register_evidence(MARGIN_ASSESSMENT)
    registry.register_evidence(PROMOTION_RECOMMENDATION)
    registry.register_task_contract(ASSESS_PRICE_BAND)
    registry.register_task_contract(ASSESS_MARGIN_BOUNDARY)
    registry.register_task_contract(RECOMMEND_PROMOTION_RESPONSE)
    registry.register_decision_type(PROMOTION_RESPONSE)

    return registry.freeze()
