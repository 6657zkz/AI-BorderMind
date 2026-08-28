from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InputRequirement:
    """声明任务需要的一个输入，以及缺失时能否向用户澄清。

    Args:
        key: 输入字段名；规划器据此从业务图、项目画像或上游节点输出中绑定值。
        clarifiable: 为 True 时，缺失该字段会产生澄清请求；否则会拒绝规划。
        accepted_value_shape: 供 API/前端展示的值形状提示，如 ``percentage``。
    """

    key: str
    clarifiable: bool = True
    accepted_value_shape: str | None = None


@dataclass(frozen=True)
class OutputField:
    """声明任务结构化输出中的一个字段。

    Args:
        key: 下游任务绑定该输出时使用的字段名。
        semantic_type: 领域语义类型，不等同于 Python 类型，例如 ``price_distribution``。
        required: 为 True 时，任务成功输出必须包含该字段。
    """

    key: str
    semantic_type: str
    required: bool = True


@dataclass(frozen=True)
class TaskContractDefinition:
    """描述规划器生成一个任务节点所需的静态契约。

    Args:
        task_id: 能力目录内唯一的任务标识，同时成为计划节点默认 ID。
        purpose: 任务要完成的业务目的，供运行记录和展示层说明使用。
        input_requirements: 任务的必需输入声明。
        dependencies: 必须先成功或按策略完成的上游任务 ID。
        allowed_operator_ids: 此任务可调用的受控数据能力白名单。
        allowed_expert_role_ids: 此任务可调用的专家角色白名单。
        output_fields: 任务可供下游绑定的结构化输出字段。
        evidence_requirements: 任务必须产出或引用的证据类型 ID。
        quality_requirements: 数据时效、样本量等质量条件的领域声明。
        failure_policy: 节点失败后的处理策略标识，由未来运行模块解释。
        skip_policy: 节点可跳过时的处理策略标识。
        clarification_policy: 输入不足时的处理策略标识。
        retry_policy: 节点失败后的重试策略标识。
    """

    task_id: str
    purpose: str
    input_requirements: tuple[InputRequirement, ...]
    dependencies: tuple[str, ...] = ()
    allowed_operator_ids: frozenset[str] = frozenset()
    allowed_expert_role_ids: frozenset[str] = frozenset()
    output_fields: tuple[OutputField, ...] = ()
    evidence_requirements: tuple[str, ...] = ()
    quality_requirements: tuple[str, ...] = ()
    failure_policy: str = "fail"
    skip_policy: str = "skip_when_unavailable"
    clarification_policy: str = "request_required_input"
    retry_policy: str = "no_retry"


@dataclass(frozen=True)
class DecisionTypeDefinition:
    """声明一种决策可使用的上下文、证据、比较关系和任务蓝图。

    Args:
        decision_type_id: 能力目录内唯一的决策类型标识。
        enabled: 是否允许规划器将该决策类型编译为执行计划。
        task_contract_ids: 构成该决策类型蓝图的任务契约 ID。
        required_context_keys: 图中允许且业务上必需的范围/上下文字段名。
        optional_context_keys: 图中允许但不是必需的范围/上下文字段名。
        allowed_constraint_keys: 图中允许携带的业务约束字段名。
        allowed_evidence_ids: 图中可请求的证据类型白名单。
        allowed_comparison_kinds: 图中可声明的实体比较关系类型白名单。
    """

    decision_type_id: str
    enabled: bool
    task_contract_ids: tuple[str, ...]
    required_context_keys: frozenset[str] = frozenset()
    optional_context_keys: frozenset[str] = frozenset()
    allowed_constraint_keys: frozenset[str] = frozenset()
    allowed_evidence_ids: frozenset[str] = frozenset()
    allowed_comparison_kinds: frozenset[str] = frozenset()


class CapabilityCatalog(Protocol):
    """定义 planning 读取能力目录元数据的只读接口。"""

    @property
    def version(self) -> str:
        """返回目录版本，用于确保 Graph 和计划可回放。"""
        ...

    def get_decision_type(self, decision_type_id: str) -> DecisionTypeDefinition | None:
        """按 ``decision_type_id`` 查找决策类型定义；未注册时返回 None。"""
        ...

    def get_task_contract(self, task_id: str) -> TaskContractDefinition | None:
        """按 ``task_id`` 查找任务契约定义；未注册时返回 None。"""
        ...

    def has_entity(self, entity_id: str) -> bool:
        """判断 ``entity_id`` 是否为已注册的业务实体。"""
        ...

    def has_metric(self, metric_id: str) -> bool:
        """判断 ``metric_id`` 是否为已注册的业务指标。"""
        ...

    def has_operator(self, operator_id: str) -> bool:
        """判断 ``operator_id`` 是否为已注册的受控数据能力。"""
        ...

    def has_expert_role(self, expert_role_id: str) -> bool:
        """判断 ``expert_role_id`` 是否为已注册的专家角色。"""
        ...

    def has_evidence(self, evidence_id: str) -> bool:
        """判断 ``evidence_id`` 是否为已注册的证据类型。"""
        ...
