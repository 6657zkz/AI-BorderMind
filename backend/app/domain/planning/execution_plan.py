from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

Value = Any


@dataclass(frozen=True)
class InputBinding:
    """声明计划节点的输入来自 Graph、项目画像或上游节点输出。

    Args:
        input_key: 当前节点要接收的任务输入字段名。
        source_kind: 来源类别，如 ``graph_scope``、``project_profile`` 或 ``upstream_output``。
        source_key: 来源对象内读取值或输出字段的键名。
        source_node_id: 来源为上游输出时的直接依赖节点 ID；其他来源为 None。
    """

    input_key: str
    source_kind: str
    source_key: str
    source_node_id: str | None = None

    def to_snapshot(self) -> dict[str, Value]:
        """导出输入绑定快照。

        Returns:
            包含目标输入、来源类别、来源键和可选上游节点 ID 的字典。
        """
        return {
            "input_key": self.input_key,
            "source_kind": self.source_kind,
            "source_key": self.source_key,
            "source_node_id": self.source_node_id,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Value]) -> InputBinding:
        """从快照恢复输入绑定。

        Args:
            snapshot: 由 ``to_snapshot`` 生成的绑定字典。

        Returns:
            恢复后的 InputBinding。
        """
        return cls(
            input_key=str(snapshot["input_key"]),
            source_kind=str(snapshot["source_kind"]),
            source_key=str(snapshot["source_key"]),
            source_node_id=snapshot.get("source_node_id"),
        )


@dataclass(frozen=True)
class PlanNode:
    """定义 DAG 中一个可独立调度、审计和恢复的任务节点。

    Args:
        node_id: 本计划内唯一的节点 ID，当前与任务契约 ID 相同。
        task_contract_id: 生成节点的能力目录任务契约 ID。
        purpose: 节点承担的业务目的。
        depends_on: 节点运行前必须完成的显式上游节点 ID。
        allowed_operator_ids: 节点允许运行时调用的受控数据能力白名单。
        allowed_expert_role_ids: 节点允许运行时调用的专家角色白名单。
        input_bindings: 每个任务输入的受控来源绑定。
        quality_requirements: 节点结果必须满足的质量条件声明。
        failure_policy: 节点失败后的处理策略标识。
        skip_policy: 节点跳过时的处理策略标识。
        clarification_policy: 节点输入不足时的澄清策略标识。
        retry_policy: 节点执行失败后的重试策略标识。
        output_fields: 三元组 ``(字段名, 语义类型, 是否必需)`` 形式的结构化输出声明。
        evidence_requirements: 节点需要产出或引用的证据类型 ID。
    """

    node_id: str
    task_contract_id: str
    purpose: str
    depends_on: tuple[str, ...]
    allowed_operator_ids: frozenset[str]
    allowed_expert_role_ids: frozenset[str]
    input_bindings: tuple[InputBinding, ...]
    quality_requirements: tuple[str, ...]
    failure_policy: str
    skip_policy: str
    clarification_policy: str
    retry_policy: str
    output_fields: tuple[tuple[str, str, bool], ...]
    evidence_requirements: tuple[str, ...]

    def to_snapshot(self) -> dict[str, Value]:
        """导出节点执行定义快照。

        Returns:
            仅包含可序列化值的节点字典；集合会转为稳定排序列表。
        """
        return {
            "node_id": self.node_id,
            "task_contract_id": self.task_contract_id,
            "purpose": self.purpose,
            "depends_on": list(self.depends_on),
            "allowed_operator_ids": sorted(self.allowed_operator_ids),
            "allowed_expert_role_ids": sorted(self.allowed_expert_role_ids),
            "input_bindings": [binding.to_snapshot() for binding in self.input_bindings],
            "quality_requirements": list(self.quality_requirements),
            "failure_policy": self.failure_policy,
            "skip_policy": self.skip_policy,
            "clarification_policy": self.clarification_policy,
            "retry_policy": self.retry_policy,
            "output_fields": [list(field) for field in self.output_fields],
            "evidence_requirements": list(self.evidence_requirements),
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Value]) -> PlanNode:
        """从快照恢复任务节点定义。

        Args:
            snapshot: 由 ``to_snapshot`` 生成的节点字典。

        Returns:
            恢复后的 PlanNode。
        """
        return cls(
            node_id=str(snapshot["node_id"]),
            task_contract_id=str(snapshot["task_contract_id"]),
            purpose=str(snapshot["purpose"]),
            depends_on=tuple(snapshot["depends_on"]),
            allowed_operator_ids=frozenset(snapshot["allowed_operator_ids"]),
            allowed_expert_role_ids=frozenset(snapshot["allowed_expert_role_ids"]),
            input_bindings=tuple(InputBinding.from_snapshot(binding) for binding in snapshot["input_bindings"]),
            quality_requirements=tuple(snapshot["quality_requirements"]),
            failure_policy=str(snapshot["failure_policy"]),
            skip_policy=str(snapshot["skip_policy"]),
            clarification_policy=str(snapshot["clarification_policy"]),
            retry_policy=str(snapshot["retry_policy"]),
            output_fields=tuple(tuple(field) for field in snapshot["output_fields"]),
            evidence_requirements=tuple(snapshot["evidence_requirements"]),
        )


@dataclass(frozen=True)
class ExecutionPlan:
    """保存唯一允许运行的任务 DAG 及其回放所需快照。

    Args:
        plan_id: 本次编译生成的稳定计划 ID。
        source_graph_id: 生成该计划的 DecisionGraph ID，建立业务语义与执行定义的追溯关系。
        catalog_version: 编译时使用的能力目录版本。
        project_profile_snapshot: 编译输入的项目画像副本，防止后续画像变更影响历史计划。
        nodes: 本计划的全部可执行节点定义。
        topological_node_ids: 满足依赖关系的稳定节点顺序；无依赖节点可被运行器并行调度。
        plan_metadata: 预留给未来计划级说明和审计数据的附加不可变元数据。
    """

    plan_id: str
    source_graph_id: str
    catalog_version: str
    project_profile_snapshot: Mapping[str, Value]
    nodes: tuple[PlanNode, ...]
    topological_node_ids: tuple[str, ...]
    plan_metadata: Mapping[str, Value] = field(default_factory=dict)

    def to_snapshot(self) -> dict[str, Value]:
        """导出完整执行计划快照。

        Returns:
            可持久化的计划字典，项目画像和元数据均为深拷贝。
        """
        return {
            "plan_id": self.plan_id,
            "source_graph_id": self.source_graph_id,
            "catalog_version": self.catalog_version,
            "project_profile_snapshot": deepcopy(dict(self.project_profile_snapshot)),
            "nodes": [node.to_snapshot() for node in self.nodes],
            "topological_node_ids": list(self.topological_node_ids),
            "plan_metadata": deepcopy(dict(self.plan_metadata)),
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Value]) -> ExecutionPlan:
        """从持久化快照恢复执行计划。

        Args:
            snapshot: 由 ``to_snapshot`` 生成的完整计划字典。

        Returns:
            不与输入快照共享可变嵌套值的 ExecutionPlan。
        """
        return cls(
            plan_id=str(snapshot["plan_id"]),
            source_graph_id=str(snapshot["source_graph_id"]),
            catalog_version=str(snapshot["catalog_version"]),
            project_profile_snapshot=deepcopy(dict(snapshot["project_profile_snapshot"])),
            nodes=tuple(PlanNode.from_snapshot(node) for node in snapshot["nodes"]),
            topological_node_ids=tuple(snapshot["topological_node_ids"]),
            plan_metadata=deepcopy(dict(snapshot.get("plan_metadata", {}))),
        )
