from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class PlanningError(ValueError):
    pass


class NodeSource(StrEnum):
    USER = "user"
    SIGNAL = "signal"
    COMPILER = "compiler"


class DecisionNodeKind(StrEnum):
    GOAL = "goal"
    METRIC = "metric"
    ENTITY = "entity"
    CONSTRAINT = "constraint"
    CAPABILITY = "capability"


class RelationKind(StrEnum):
    REQUIRES = "requires"
    PRODUCES = "produces"
    FILTERS = "filters"
    COMPARES = "compares"
    CAUSED_BY = "caused_by"


class DecisionNode(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_:-]*$")
    kind: DecisionNodeKind
    ref: str
    source: NodeSource = NodeSource.USER
    confidence: float = Field(default=1, ge=0, le=1)
    explanation: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class DecisionRelation(BaseModel):
    source: str
    target: str
    kind: RelationKind
    explanation: str | None = None


class DecisionGraph(BaseModel):
    query: str = Field(min_length=1)
    nodes: list[DecisionNode] = Field(min_length=1)
    relations: list[DecisionRelation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "DecisionGraph":
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("DecisionGraph 存在重复节点 ID")
        known = set(ids)
        for relation in self.relations:
            if relation.source not in known or relation.target not in known:
                raise ValueError("DecisionGraph 关系引用了不存在的节点")
        return self

    def refs(self, kind: DecisionNodeKind) -> set[str]:
        return {node.ref for node in self.nodes if node.kind == kind}


class DataRequirement(BaseModel):
    metric_id: str
    min_sample_size: int | None = Field(default=None, ge=1)
    max_age_hours: int | None = Field(default=None, ge=1)


class ClarificationNeed(BaseModel):
    field_id: str
    question: str
    required_for: list[str]
    options: list[str] = Field(default_factory=list)


class PlanNode(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_:-]*$")
    capability_id: str
    analysis_task_id: str
    expert_role_id: str
    data_capability_ids: list[str] = Field(default_factory=list)
    output_contract: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    source: NodeSource = NodeSource.USER
    data_requirements: list[DataRequirement] = Field(default_factory=list)
    explanation: str | None = None


class ExecutionPlan(BaseModel):
    goals: list[str] = Field(default_factory=list)
    nodes: list[PlanNode] = Field(min_length=1)
    clarifications: list[ClarificationNeed] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "ExecutionPlan":
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("ExecutionPlan 存在重复节点 ID")
        known = set(ids)
        for node in self.nodes:
            unknown = set(node.depends_on) - known
            if unknown:
                raise ValueError(f"节点 {node.id} 依赖不存在的节点: {sorted(unknown)}")
            if node.id in node.depends_on:
                raise ValueError(f"节点 {node.id} 不能依赖自身")
        return self

    def topological_layers(self) -> list[list[PlanNode]]:
        pending = {node.id: node for node in self.nodes}
        completed: set[str] = set()
        layers: list[list[PlanNode]] = []
        while pending:
            ready = [node for node in pending.values() if set(node.depends_on) <= completed]
            if not ready:
                raise PlanningError("ExecutionPlan 存在循环依赖")
            layers.append(ready)
            for node in ready:
                completed.add(node.id)
                del pending[node.id]
        return layers
