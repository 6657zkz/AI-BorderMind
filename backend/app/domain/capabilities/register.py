from __future__ import annotations

"""能力目录的构建期注册、校验和冻结入口。

本模块只负责装配静态契约，不执行 Operator、专家、网络请求或数据库访问。
"""

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
    """同一种能力的 ID 重复注册时抛出的构建期错误。"""


class InvalidCapabilityCatalogError(ValueError):
    """目录版本、引用关系或生命周期不合法时抛出的构建期错误。"""


@dataclass(frozen=True)
class FrozenCapabilityCatalog(CapabilityCatalog):
    """冻结后的只读目录，供 planning 查询能力元数据。"""

    # 目录版本必须与 DecisionGraph 使用的版本完全一致，保证可回放。
    _version: str
    # 按稳定 ID 索引的业务实体，只读映射避免外部修改目录。
    _entities: Mapping[str, EntityDefinition]
    # 按稳定 ID 索引的业务指标，只读映射避免外部修改目录。
    _metrics: Mapping[str, MetricDefinition]
    # 按稳定 ID 索引的受控数据算子元数据。
    _operators: Mapping[str, OperatorDefinition]
    # 按稳定 ID 索引的专家角色元数据。
    _expert_roles: Mapping[str, ExpertRoleDefinition]
    # 按稳定 ID 索引的 Evidence 定义。
    _evidence: Mapping[str, EvidenceDefinition]
    # 按任务 ID 索引的任务契约。
    _task_contracts: Mapping[str, TaskContractDefinition]
    # 按决策类型 ID 索引的决策蓝图。
    _decision_types: Mapping[str, DecisionTypeDefinition]

    @property
    def version(self) -> str:
        """返回目录版本，Graph 必须使用相同版本才能进入 planning。"""
        return self._version

    def get_decision_type(self, decision_type_id: str) -> DecisionTypeDefinition | None:
        """按 ID 查询决策类型；未知 ID 返回 None。"""
        return self._decision_types.get(decision_type_id)

    def get_task_contract(self, task_id: str) -> TaskContractDefinition | None:
        """按 ID 查询任务契约；未知 ID 返回 None。"""
        return self._task_contracts.get(task_id)

    def has_entity(self, entity_id: str) -> bool:
        """判断实体是否已经注册。"""
        return entity_id in self._entities

    def has_metric(self, metric_id: str) -> bool:
        """判断指标是否已经注册。"""
        return metric_id in self._metrics

    def has_operator(self, operator_id: str) -> bool:
        """判断受控数据算子是否已经注册。"""
        return operator_id in self._operators

    def has_expert_role(self, expert_role_id: str) -> bool:
        """判断专家角色是否已经注册。"""
        return expert_role_id in self._expert_roles

    def has_evidence(self, evidence_id: str) -> bool:
        """判断 Evidence 类型是否已经注册。"""
        return evidence_id in self._evidence


class CapabilityRegistry:
    """收集能力定义并在完成后生成冻结目录的构建器。"""

    def __init__(self, version: str) -> None:
        # 版本由总注册入口显式指定，不随进程启动时间或注册顺序变化。
        self._version = version
        # 构建期间使用普通字典，便于按 ID 检查重复和引用。
        self._entities: dict[str, EntityDefinition] = {}
        self._metrics: dict[str, MetricDefinition] = {}
        self._operators: dict[str, OperatorDefinition] = {}
        self._expert_roles: dict[str, ExpertRoleDefinition] = {}
        self._evidence: dict[str, EvidenceDefinition] = {}
        self._task_contracts: dict[str, TaskContractDefinition] = {}
        self._decision_types: dict[str, DecisionTypeDefinition] = {}
        # freeze 后禁止继续注册，防止已构建目录的语义发生漂移。
        self._frozen = False

    def register_entity(self, definition: EntityDefinition) -> None:
        """注册一个业务实体定义。"""
        self._register(self._entities, definition.entity_id, definition)

    def register_metric(self, definition: MetricDefinition) -> None:
        """注册一个业务指标定义。"""
        self._register(self._metrics, definition.metric_id, definition)

    def register_operator(self, definition: OperatorDefinition) -> None:
        """注册一个受控数据算子的静态元数据。"""
        self._register(self._operators, definition.operator_id, definition)

    def register_expert_role(self, definition: ExpertRoleDefinition) -> None:
        """注册一个专家角色的静态契约。"""
        self._register(self._expert_roles, definition.expert_role_id, definition)

    def register_evidence(self, definition: EvidenceDefinition) -> None:
        """注册一个 Evidence 类型定义。"""
        self._register(self._evidence, definition.evidence_id, definition)

    def register_task_contract(self, definition: TaskContractDefinition) -> None:
        """注册一个任务契约。"""
        self._register(self._task_contracts, definition.task_id, definition)

    def register_decision_type(self, definition: DecisionTypeDefinition) -> None:
        """注册一个决策类型及其任务蓝图。"""
        self._register(self._decision_types, definition.decision_type_id, definition)

    def freeze(self) -> FrozenCapabilityCatalog:
        """校验全部引用并生成独立的只读目录。"""
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
        """执行所有注册方法共享的生命周期和 ID 校验。"""
        # 冻结是单向操作，避免目录生成后又悄悄改变规划语义。
        if self._frozen:
            raise InvalidCapabilityCatalogError("Capability registry has already been frozen.")
        # 空 ID 无法作为稳定的目录引用，因此在构建期立即拒绝。
        if not identifier:
            raise InvalidCapabilityCatalogError("Capability IDs must not be empty.")
        # 后注册不能覆盖先注册，避免注册顺序改变最终目录含义。
        if identifier in target:
            raise DuplicateCapabilityError(f"Capability ID is already registered: {identifier}")
        target[identifier] = definition

    def _validate_references(self) -> None:
        """在冻结前验证目录内各类定义的引用完整性。"""
        # 决策类型必须能展开到已注册任务，并且只能允许已注册 Evidence。
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
            # 任务依赖必须指向本目录中的任务，编译器才能生成完整 DAG。
            for dependency_id in task.dependencies:
                if dependency_id not in self._task_contracts:
                    raise InvalidCapabilityCatalogError(
                        f"Task references an unknown dependency: {dependency_id}"
                    )
            # 任务声明的 Operator、专家角色和 Evidence 都必须有对应目录定义。
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
            # Evidence 只能关联已登记指标，避免形成无法解释的证据引用。
            for metric_id in evidence.metric_ids:
                if metric_id not in self._metrics:
                    raise InvalidCapabilityCatalogError(
                        f"Evidence references an unknown metric: {metric_id}"
                    )

        for expert in self._expert_roles.values():
            # 专家角色只能要求已登记 Evidence，执行阶段才有可验证输入。
            for evidence_id in expert.required_evidence_ids:
                if evidence_id not in self._evidence:
                    raise InvalidCapabilityCatalogError(
                        f"Expert role references unknown evidence: {evidence_id}"
                    )


def build_capability_catalog() -> FrozenCapabilityCatalog:
    """按固定顺序装配当前产品能力并返回冻结目录。"""
    # 每次显式构建独立 registry，避免模块导入时产生共享可变状态。
    registry = CapabilityRegistry(version="catalog-v1")

    # 先注册被其他定义引用的基础实体和指标。
    for definition in ENTITIES:
        registry.register_entity(definition)
    for definition in METRICS:
        registry.register_metric(definition)

    # 再注册任务会引用的 Operator、专家角色和 Evidence 元数据。
    registry.register_operator(PRICE_PERCENTILES)
    registry.register_operator(MARGIN_CALCULATION)
    registry.register_expert_role(PRICING_EXPERT)
    registry.register_evidence(MARKET_PRICE_BAND)
    registry.register_evidence(MARGIN_ASSESSMENT)
    registry.register_evidence(PROMOTION_RECOMMENDATION)

    # 最后注册任务契约和决策类型，最后一步统一检查全部跨引用。
    registry.register_task_contract(ASSESS_PRICE_BAND)
    registry.register_task_contract(ASSESS_MARGIN_BOUNDARY)
    registry.register_task_contract(RECOMMEND_PROMOTION_RESPONSE)
    registry.register_decision_type(PROMOTION_RESPONSE)

    # freeze 会复制索引并锁定 registry，返回 planning 可消费的只读目录。
    return registry.freeze()
