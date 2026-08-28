from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.domain.capabilities.contracts import CapabilityCatalog

Value = Any


@dataclass(frozen=True)
class TriggerContext:
    """保存本次规划由用户、人工操作或事件触发的上下文。

    Args:
        source: 触发来源类别，例如 ``user``、``event`` 或 ``manual``。
        reference_id: 来源系统中的消息、事件或操作记录 ID；没有关联记录时为 None。
        metadata: 来源特有的补充上下文；只保存值，不持有外部对象或连接。
    """

    source: str
    reference_id: str | None = None
    metadata: Mapping[str, Value] = field(default_factory=dict)

    def to_snapshot(self) -> dict[str, Value]:
        """导出独立的触发上下文快照。

        Returns:
            可持久化的字典副本；修改返回值不会影响当前对象。
        """
        return {
            "source": self.source,
            "reference_id": self.reference_id,
            "metadata": deepcopy(dict(self.metadata)),
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Value]) -> TriggerContext:
        """从持久化快照恢复触发上下文。

        Args:
            snapshot: 由 ``to_snapshot`` 生成的触发上下文字典。

        Returns:
            不与输入字典共享可变嵌套值的 TriggerContext。
        """
        return cls(
            source=str(snapshot["source"]),
            reference_id=snapshot.get("reference_id"),
            metadata=deepcopy(dict(snapshot.get("metadata", {}))),
        )


@dataclass(frozen=True)
class EvidenceRequirement:
    """描述决策图要求取得的一类证据及其关联指标。

    Args:
        evidence_id: 能力目录中注册的证据类型 ID。
        metric_id: 该证据要支持的指标 ID；不依赖特定指标时为 None。
    """

    evidence_id: str
    metric_id: str | None = None

    def to_snapshot(self) -> dict[str, Value]:
        """导出证据需求快照。

        Returns:
            仅含证据类型与关联指标 ID 的字典。
        """
        return {"evidence_id": self.evidence_id, "metric_id": self.metric_id}

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Value]) -> EvidenceRequirement:
        """从快照恢复证据需求。

        Args:
            snapshot: 包含 ``evidence_id`` 和可选 ``metric_id`` 的字典。

        Returns:
            恢复后的 EvidenceRequirement。
        """
        return cls(evidence_id=str(snapshot["evidence_id"]), metric_id=snapshot.get("metric_id"))


@dataclass(frozen=True)
class Comparison:
    """描述两个注册实体之间需要验证的业务比较关系。

    Args:
        kind: 能力目录允许的关系类型，例如 ``competitor_to_own``。
        left_entity_id: 比较左侧的注册实体 ID。
        right_entity_id: 比较右侧的注册实体 ID。
    """

    kind: str
    left_entity_id: str
    right_entity_id: str

    def to_snapshot(self) -> dict[str, Value]:
        """导出比较关系快照。

        Returns:
            包含关系类型和双方实体 ID 的字典。
        """
        return {
            "kind": self.kind,
            "left_entity_id": self.left_entity_id,
            "right_entity_id": self.right_entity_id,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Value]) -> Comparison:
        """从快照恢复比较关系。

        Args:
            snapshot: 包含 ``kind``、左右实体 ID 的字典。

        Returns:
            恢复后的 Comparison。
        """
        return cls(
            kind=str(snapshot["kind"]),
            left_entity_id=str(snapshot["left_entity_id"]),
            right_entity_id=str(snapshot["right_entity_id"]),
        )


@dataclass(frozen=True)
class DecisionGraph:
    """保存不可执行的业务语义，作为编译 ExecutionPlan 的唯一输入图。

    Args:
        graph_id: 本次业务理解图的稳定唯一 ID。
        catalog_version: 识别和校验该图时使用的能力目录版本。
        decision_type_id: 本次请求要解决的已注册决策类型 ID。
        trigger: 发起本次规划的用户、事件或人工操作上下文。
        scope: 业务分析范围，如市场、品类、SKU、竞品和时间窗。
        constraints: 影响决策的业务边界，如成本底线、目标毛利或响应限制。
        required_evidence: 作出决策前必须取得或验证的证据需求。
        comparisons: 本次决策需要成立的实体间比较关系。
        entity_references: 图中涉及的所有注册业务实体 ID，用于白名单校验。
        metric_references: 图中涉及的所有注册业务指标 ID，用于白名单校验。
        recognition_snapshot: 决策类型识别过程的结果快照，供历史回放。
        context_snapshot: 图外但影响本次规划的已提取上下文快照。
        trigger_policy_snapshot: 由监控策略触发时记录策略上下文；用户触发时为 None。
    """

    graph_id: str
    catalog_version: str
    decision_type_id: str
    trigger: TriggerContext
    scope: Mapping[str, Value] = field(default_factory=dict)
    constraints: Mapping[str, Value] = field(default_factory=dict)
    required_evidence: tuple[EvidenceRequirement, ...] = ()
    comparisons: tuple[Comparison, ...] = ()
    entity_references: frozenset[str] = frozenset()
    metric_references: frozenset[str] = frozenset()
    recognition_snapshot: Mapping[str, Value] = field(default_factory=dict)
    context_snapshot: Mapping[str, Value] = field(default_factory=dict)
    trigger_policy_snapshot: Mapping[str, Value] | None = None

    def validate(self, catalog: CapabilityCatalog):
        """根据能力目录校验图中的业务引用与允许范围。

        Args:
            catalog: 与 ``catalog_version`` 对应的只读能力目录。

        Returns:
            所有引用合法时返回 ValidDecisionGraph；否则返回包含问题列表的 Rejected。
        """
        from .validator import validate_decision_graph

        return validate_decision_graph(self, catalog)

    def to_snapshot(self) -> dict[str, Value]:
        """导出可持久化且不会共享可变引用的业务图快照。

        Returns:
            完整业务语义的深拷贝字典，适合由未来运行记录持久化。
        """
        return {
            "graph_id": self.graph_id,
            "catalog_version": self.catalog_version,
            "decision_type_id": self.decision_type_id,
            "trigger": self.trigger.to_snapshot(),
            "scope": deepcopy(dict(self.scope)),
            "constraints": deepcopy(dict(self.constraints)),
            "required_evidence": [item.to_snapshot() for item in self.required_evidence],
            "comparisons": [item.to_snapshot() for item in self.comparisons],
            "entity_references": sorted(self.entity_references),
            "metric_references": sorted(self.metric_references),
            "recognition_snapshot": deepcopy(dict(self.recognition_snapshot)),
            "context_snapshot": deepcopy(dict(self.context_snapshot)),
            "trigger_policy_snapshot": (
                deepcopy(dict(self.trigger_policy_snapshot)) if self.trigger_policy_snapshot is not None else None
            ),
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Value]) -> DecisionGraph:
        """从持久化快照恢复业务图。

        Args:
            snapshot: 由 ``to_snapshot`` 生成的完整业务图字典。

        Returns:
            不与输入快照共享可变嵌套值的 DecisionGraph。
        """
        policy_snapshot = snapshot.get("trigger_policy_snapshot")
        return cls(
            graph_id=str(snapshot["graph_id"]),
            catalog_version=str(snapshot["catalog_version"]),
            decision_type_id=str(snapshot["decision_type_id"]),
            trigger=TriggerContext.from_snapshot(snapshot["trigger"]),
            scope=deepcopy(dict(snapshot.get("scope", {}))),
            constraints=deepcopy(dict(snapshot.get("constraints", {}))),
            required_evidence=tuple(
                EvidenceRequirement.from_snapshot(item) for item in snapshot.get("required_evidence", [])
            ),
            comparisons=tuple(Comparison.from_snapshot(item) for item in snapshot.get("comparisons", [])),
            entity_references=frozenset(snapshot.get("entity_references", [])),
            metric_references=frozenset(snapshot.get("metric_references", [])),
            recognition_snapshot=deepcopy(dict(snapshot.get("recognition_snapshot", {}))),
            context_snapshot=deepcopy(dict(snapshot.get("context_snapshot", {}))),
            trigger_policy_snapshot=deepcopy(dict(policy_snapshot)) if policy_snapshot is not None else None,
        )
