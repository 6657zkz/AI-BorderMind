from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from .entry import (
    EvidenceEntry,
    EvidenceSnapshotError,
    EvidenceValidationError,
    _freeze_json_object,
    _identifier,
    _snapshot_data,
    _snapshot_mapping,
    _snapshot_string,
    _thaw_json,
)
from .package import EvidencePackage


_SCHEMA_VERSION = "evidence-chain-v1"
_RELATION_SCHEMA_VERSION = "evidence-relation-v1"


class EvidenceRelationType(str, Enum):
    """EvidenceEntry 之间受控的来源关系类型。"""

    DERIVED_FROM = "derived_from"


@dataclass(frozen=True)
class EvidenceRelation:
    """表示一个 Entry 由另一个 Entry 派生。"""

    relation_type: EvidenceRelationType
    subject_entry_id: str
    object_entry_id: str

    def __post_init__(self) -> None:
        relation_type = self.relation_type
        if not isinstance(relation_type, EvidenceRelationType):
            try:
                relation_type = EvidenceRelationType(relation_type)
            except (TypeError, ValueError) as error:
                raise EvidenceValidationError(
                    "invalid_relation_type",
                    "relation_type",
                    "relation_type must be a supported EvidenceRelationType value.",
                ) from error
        object.__setattr__(self, "relation_type", relation_type)
        object.__setattr__(self, "subject_entry_id", _identifier(self.subject_entry_id, "subject_entry_id"))
        object.__setattr__(self, "object_entry_id", _identifier(self.object_entry_id, "object_entry_id"))
        if self.subject_entry_id == self.object_entry_id:
            raise EvidenceValidationError(
                "self_relation",
                "subject_entry_id",
                "an EvidenceRelation cannot point an entry to itself.",
            )

    def to_snapshot(self) -> dict[str, object]:
        """导出关系快照。"""
        return {
            "schema_version": _RELATION_SCHEMA_VERSION,
            "relation_type": self.relation_type.value,
            "subject_entry_id": self.subject_entry_id,
            "object_entry_id": self.object_entry_id,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> EvidenceRelation:
        """从关系快照恢复关系不变量。"""
        data = _snapshot_data(
            snapshot,
            _RELATION_SCHEMA_VERSION,
            {"schema_version", "relation_type", "subject_entry_id", "object_entry_id"},
            "relation",
        )
        try:
            return cls(
                relation_type=_snapshot_string(data["relation_type"], "relation.relation_type"),
                subject_entry_id=_snapshot_string(data["subject_entry_id"], "relation.subject_entry_id"),
                object_entry_id=_snapshot_string(data["object_entry_id"], "relation.object_entry_id"),
            )
        except EvidenceValidationError as error:
            raise EvidenceSnapshotError(error.code, error.path, error.message) from error


@dataclass(frozen=True)
class EvidenceChain:
    """保存一个 AnalysisRun 的 EvidenceEntry、专家 Package 和 lineage。"""

    chain_id: str
    tenant_id: str
    run_id: str
    scope_id: str
    catalog_version: str
    scope_snapshot: Mapping[str, object] = field(default_factory=dict)
    entries: tuple[EvidenceEntry, ...] = ()
    packages: tuple[EvidencePackage, ...] = ()
    relations: tuple[EvidenceRelation, ...] = ()

    def __post_init__(self) -> None:
        for name in ("chain_id", "tenant_id", "run_id", "scope_id", "catalog_version"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        object.__setattr__(self, "scope_snapshot", _freeze_json_object(self.scope_snapshot, "scope_snapshot"))

        entries = tuple(self.entries)
        packages = tuple(self.packages)
        relations = tuple(self.relations)
        self._validate_entries(entries)
        self._validate_packages(entries, packages)
        self._validate_relations(entries, relations)
        object.__setattr__(self, "entries", tuple(sorted(entries, key=lambda entry: entry.entry_id)))
        object.__setattr__(self, "packages", tuple(sorted(packages, key=lambda package: package.package_id)))
        object.__setattr__(
            self,
            "relations",
            tuple(sorted(relations, key=self._relation_key)),
        )

    def add_entry(self, entry: EvidenceEntry) -> EvidenceChain:
        """返回追加 Entry 后的新 Chain，不修改当前 Chain。"""
        if not isinstance(entry, EvidenceEntry):
            raise EvidenceValidationError("invalid_type", "entry", "entry must be an EvidenceEntry.")
        return self._copy_with(entries=self.entries + (entry,))

    def add_package(self, package: EvidencePackage) -> EvidenceChain:
        """返回追加 Package 后的新 Chain，不修改当前 Chain。"""
        if not isinstance(package, EvidencePackage):
            raise EvidenceValidationError("invalid_type", "package", "package must be an EvidencePackage.")
        return self._copy_with(packages=self.packages + (package,))

    def add_relation(self, relation: EvidenceRelation) -> EvidenceChain:
        """返回追加 lineage 关系后的新 Chain，不修改当前 Chain。"""
        if not isinstance(relation, EvidenceRelation):
            raise EvidenceValidationError(
                "invalid_type",
                "relation",
                "relation must be an EvidenceRelation.",
            )
        return self._copy_with(relations=self.relations + (relation,))

    def to_snapshot(self) -> dict[str, object]:
        """导出完整且稳定的 Chain 快照。"""
        return {
            "schema_version": _SCHEMA_VERSION,
            "chain_id": self.chain_id,
            "tenant_id": self.tenant_id,
            "run_id": self.run_id,
            "scope_id": self.scope_id,
            "catalog_version": self.catalog_version,
            "scope_snapshot": _thaw_json(self.scope_snapshot),
            "entries": [entry.to_snapshot() for entry in self.entries],
            "packages": [package.to_snapshot() for package in self.packages],
            "relations": [relation.to_snapshot() for relation in self.relations],
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> EvidenceChain:
        """从 Chain 快照恢复全部对象并重新校验聚合不变量。"""
        data = _snapshot_data(
            snapshot,
            _SCHEMA_VERSION,
            {
                "schema_version",
                "chain_id",
                "tenant_id",
                "run_id",
                "scope_id",
                "catalog_version",
                "scope_snapshot",
                "entries",
                "packages",
                "relations",
            },
            "chain",
        )
        try:
            entries_data = _snapshot_list(data["entries"], "chain.entries")
            packages_data = _snapshot_list(data["packages"], "chain.packages")
            relations_data = _snapshot_list(data["relations"], "chain.relations")
            entries = tuple(_restore_entry(item, index) for index, item in enumerate(entries_data))
            packages = tuple(_restore_package(item, index) for index, item in enumerate(packages_data))
            relations = tuple(_restore_relation(item, index) for index, item in enumerate(relations_data))
            return cls(
                chain_id=_snapshot_string(data["chain_id"], "chain.chain_id"),
                tenant_id=_snapshot_string(data["tenant_id"], "chain.tenant_id"),
                run_id=_snapshot_string(data["run_id"], "chain.run_id"),
                scope_id=_snapshot_string(data["scope_id"], "chain.scope_id"),
                catalog_version=_snapshot_string(data["catalog_version"], "chain.catalog_version"),
                scope_snapshot=_snapshot_mapping(data["scope_snapshot"], "chain.scope_snapshot"),
                entries=entries,
                packages=packages,
                relations=relations,
            )
        except EvidenceSnapshotError:
            raise
        except EvidenceValidationError as error:
            raise EvidenceSnapshotError(error.code, error.path, error.message) from error

    def _copy_with(
        self,
        *,
        entries: tuple[EvidenceEntry, ...] | None = None,
        packages: tuple[EvidencePackage, ...] | None = None,
        relations: tuple[EvidenceRelation, ...] | None = None,
    ) -> EvidenceChain:
        return EvidenceChain(
            chain_id=self.chain_id,
            tenant_id=self.tenant_id,
            run_id=self.run_id,
            scope_id=self.scope_id,
            catalog_version=self.catalog_version,
            scope_snapshot=self.scope_snapshot,
            entries=self.entries if entries is None else entries,
            packages=self.packages if packages is None else packages,
            relations=self.relations if relations is None else relations,
        )

    def _validate_entries(self, entries: tuple[EvidenceEntry, ...]) -> None:
        seen_ids: set[str] = set()
        for index, entry in enumerate(entries):
            if not isinstance(entry, EvidenceEntry):
                raise EvidenceValidationError(
                    "invalid_type",
                    f"entries[{index}]",
                    "entries must contain EvidenceEntry objects.",
                )
            if entry.entry_id in seen_ids:
                raise EvidenceValidationError(
                    "duplicate_entry_id",
                    f"entries[{index}].entry_id",
                    "entry IDs must be unique within a chain.",
                )
            seen_ids.add(entry.entry_id)
            self._validate_context(entry, f"entries[{index}]")

    def _validate_packages(
        self,
        entries: tuple[EvidenceEntry, ...],
        packages: tuple[EvidencePackage, ...],
    ) -> None:
        seen_package_ids: set[str] = set()
        seen_expert_roles: set[str] = set()
        for index, package in enumerate(packages):
            if not isinstance(package, EvidencePackage):
                raise EvidenceValidationError(
                    "invalid_type",
                    f"packages[{index}]",
                    "packages must contain EvidencePackage objects.",
                )
            if package.package_id in seen_package_ids:
                raise EvidenceValidationError(
                    "duplicate_package_id",
                    f"packages[{index}].package_id",
                    "package IDs must be unique within a chain.",
                )
            if package.expert_role_id in seen_expert_roles:
                raise EvidenceValidationError(
                    "duplicate_expert_role",
                    f"packages[{index}].expert_role_id",
                    "an expert role can have at most one package per chain.",
                )
            seen_package_ids.add(package.package_id)
            seen_expert_roles.add(package.expert_role_id)
            self._validate_context(package, f"packages[{index}]")
            try:
                package.validate_entries(entries)
            except EvidenceValidationError as error:
                raise EvidenceValidationError(
                    error.code,
                    f"packages[{index}].{error.path}",
                    error.message,
                ) from error

    def _validate_relations(
        self,
        entries: tuple[EvidenceEntry, ...],
        relations: tuple[EvidenceRelation, ...],
    ) -> None:
        entry_ids = {entry.entry_id for entry in entries}
        seen_relations: set[tuple[str, str, str]] = set()
        graph: dict[str, set[str]] = {entry_id: set() for entry_id in entry_ids}
        for index, relation in enumerate(relations):
            if not isinstance(relation, EvidenceRelation):
                raise EvidenceValidationError(
                    "invalid_type",
                    f"relations[{index}]",
                    "relations must contain EvidenceRelation objects.",
                )
            key = self._relation_key(relation)
            if key in seen_relations:
                raise EvidenceValidationError(
                    "duplicate_relation",
                    f"relations[{index}]",
                    "the same EvidenceRelation cannot be repeated.",
                )
            if relation.subject_entry_id not in entry_ids or relation.object_entry_id not in entry_ids:
                raise EvidenceValidationError(
                    "unknown_relation_endpoint",
                    f"relations[{index}]",
                    "relation endpoints must reference entries in the chain.",
                )
            seen_relations.add(key)
            graph[relation.subject_entry_id].add(relation.object_entry_id)

        if _has_cycle(graph):
            raise EvidenceValidationError(
                "lineage_cycle",
                "relations",
                "derived_from relations must form an acyclic lineage graph.",
            )

    def _validate_context(self, value: EvidenceEntry | EvidencePackage, path: str) -> None:
        for name in ("tenant_id", "run_id", "scope_id", "catalog_version"):
            if getattr(value, name) != getattr(self, name):
                raise EvidenceValidationError(
                    "context_mismatch",
                    f"{path}.{name}",
                    f"{name} must match the chain context.",
                )

    @staticmethod
    def _relation_key(relation: EvidenceRelation) -> tuple[str, str, str]:
        return (
            relation.relation_type.value,
            relation.subject_entry_id,
            relation.object_entry_id,
        )


def _has_cycle(graph: Mapping[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in graph[node]):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def _snapshot_list(value: object, path: str) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise EvidenceSnapshotError("invalid_type", path, "snapshot value must be a list.")
    return list(value)


def _restore_entry(value: object, index: int) -> EvidenceEntry:
    try:
        return EvidenceEntry.from_snapshot(_snapshot_mapping(value, "entry"))
    except EvidenceSnapshotError as error:
        raise EvidenceSnapshotError(
            error.code,
            _nested_snapshot_path(f"chain.entries[{index}]", "entry", error.path),
            error.message,
        ) from error


def _restore_package(value: object, index: int) -> EvidencePackage:
    try:
        return EvidencePackage.from_snapshot(_snapshot_mapping(value, "package"))
    except EvidenceSnapshotError as error:
        raise EvidenceSnapshotError(
            error.code,
            _nested_snapshot_path(f"chain.packages[{index}]", "package", error.path),
            error.message,
        ) from error


def _restore_relation(value: object, index: int) -> EvidenceRelation:
    try:
        return EvidenceRelation.from_snapshot(_snapshot_mapping(value, "relation"))
    except EvidenceSnapshotError as error:
        raise EvidenceSnapshotError(
            error.code,
            _nested_snapshot_path(f"chain.relations[{index}]", "relation", error.path),
            error.message,
        ) from error


def _nested_snapshot_path(container_path: str, object_name: str, detail_path: str) -> str:
    prefix = f"{object_name}."
    detail = detail_path[len(prefix) :] if detail_path.startswith(prefix) else detail_path
    return f"{container_path}.{detail}"


__all__ = ["EvidenceChain", "EvidenceRelation", "EvidenceRelationType"]
