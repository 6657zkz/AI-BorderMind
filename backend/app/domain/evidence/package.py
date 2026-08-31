from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from .entry import (
    EvidenceEntry,
    EvidenceSnapshotError,
    EvidenceStatus,
    EvidenceValidationError,
    _datetime_snapshot,
    _freeze_json_object,
    _identifier,
    _parse_datetime,
    _snapshot_data,
    _snapshot_mapping,
    _snapshot_string,
    _snapshot_string_list,
    _string_set,
    _thaw_json,
    _utc_datetime,
)


_SCHEMA_VERSION = "evidence-package-v1"


@dataclass(frozen=True)
class EvidencePackage:
    """保存一个专家角色本次可消费的 EvidenceEntry 引用集合。"""

    package_id: str
    tenant_id: str
    run_id: str
    scope_id: str
    catalog_version: str
    expert_role_id: str
    entry_ids: tuple[str, ...]
    allowed_evidence_type_ids: frozenset[str]
    required_evidence_type_ids: frozenset[str]
    authorized_at: datetime
    authorization_snapshot: Mapping[str, object]

    def __post_init__(self) -> None:
        for name in (
            "package_id",
            "tenant_id",
            "run_id",
            "scope_id",
            "catalog_version",
            "expert_role_id",
        ):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))

        entry_ids = tuple(self.entry_ids)
        if any(not isinstance(entry_id, str) or not entry_id.strip() for entry_id in entry_ids):
            raise EvidenceValidationError(
                "blank_identifier",
                "entry_ids",
                "entry IDs must be non-blank strings.",
            )
        if len(entry_ids) != len(set(entry_ids)):
            raise EvidenceValidationError(
                "duplicate_entry_id",
                "entry_ids",
                "entry IDs must be unique within a package.",
            )
        object.__setattr__(self, "entry_ids", entry_ids)

        allowed = _string_set(self.allowed_evidence_type_ids, "allowed_evidence_type_ids")
        required = _string_set(self.required_evidence_type_ids, "required_evidence_type_ids")
        if not required.issubset(allowed):
            raise EvidenceValidationError(
                "required_evidence_not_allowed",
                "required_evidence_type_ids",
                "required evidence types must be allowed evidence types.",
            )
        object.__setattr__(self, "allowed_evidence_type_ids", allowed)
        object.__setattr__(self, "required_evidence_type_ids", required)

        object.__setattr__(self, "authorized_at", _utc_datetime(self.authorized_at, "authorized_at"))
        object.__setattr__(
            self,
            "authorization_snapshot",
            _freeze_json_object(self.authorization_snapshot, "authorization_snapshot"),
        )

    def validate_entries(self, entries: Iterable[EvidenceEntry]) -> None:
        """验证 Package 引用的 Entry 是否完整且可供专家消费。"""
        indexed: dict[str, EvidenceEntry] = {}
        for index, entry in enumerate(entries):
            if not isinstance(entry, EvidenceEntry):
                raise EvidenceValidationError(
                    "invalid_type",
                    f"entries[{index}]",
                    "entries must contain EvidenceEntry objects.",
                )
            if entry.entry_id in indexed:
                raise EvidenceValidationError(
                    "duplicate_entry_id",
                    f"entries[{index}].entry_id",
                    "entry IDs must be unique in the validation input.",
                )
            indexed[entry.entry_id] = entry

        selected: list[EvidenceEntry] = []
        for entry_id in self.entry_ids:
            entry = indexed.get(entry_id)
            if entry is None:
                raise EvidenceValidationError(
                    "unknown_entry_reference",
                    f"entry_ids[{entry_id!r}]",
                    "package references an unknown EvidenceEntry.",
                )
            selected.append(entry)

        for entry in selected:
            if (
                entry.tenant_id != self.tenant_id
                or entry.run_id != self.run_id
                or entry.scope_id != self.scope_id
                or entry.catalog_version != self.catalog_version
            ):
                raise EvidenceValidationError(
                    "context_mismatch",
                    f"entry_ids[{entry.entry_id!r}]",
                    "entry context must match the package context.",
                )
            if entry.evidence_type_id not in self.allowed_evidence_type_ids:
                raise EvidenceValidationError(
                    "entry_not_allowed",
                    f"entry_ids[{entry.entry_id!r}]",
                    "entry evidence type is not allowed by the package.",
                )
            if entry.status is not EvidenceStatus.VERIFIED:
                raise EvidenceValidationError(
                    "entry_not_usable",
                    f"entry_ids[{entry.entry_id!r}]",
                    "only verified entries can be consumed by a package.",
                )
            if entry.recorded_at > self.authorized_at:
                raise EvidenceValidationError(
                    "entry_recorded_after_authorization",
                    f"entry_ids[{entry.entry_id!r}]",
                    "entry must be recorded no later than package authorization.",
                )
            if entry.expires_at is not None and entry.expires_at <= self.authorized_at:
                raise EvidenceValidationError(
                    "entry_expired_at_authorization",
                    f"entry_ids[{entry.entry_id!r}]",
                    "entry must not be expired when the package is authorized.",
                )

        available_types = {entry.evidence_type_id for entry in selected}
        missing_types = self.required_evidence_type_ids - available_types
        if missing_types:
            missing_type = sorted(missing_types)[0]
            raise EvidenceValidationError(
                "missing_required_evidence",
                "required_evidence_type_ids",
                f"required evidence type is missing: {missing_type}.",
            )

    def to_snapshot(self) -> dict[str, object]:
        """导出只含引用的独立 Package 快照。"""
        return {
            "schema_version": _SCHEMA_VERSION,
            "package_id": self.package_id,
            "tenant_id": self.tenant_id,
            "run_id": self.run_id,
            "scope_id": self.scope_id,
            "catalog_version": self.catalog_version,
            "expert_role_id": self.expert_role_id,
            "entry_ids": list(self.entry_ids),
            "allowed_evidence_type_ids": sorted(self.allowed_evidence_type_ids),
            "required_evidence_type_ids": sorted(self.required_evidence_type_ids),
            "authorized_at": _datetime_snapshot(self.authorized_at),
            "authorization_snapshot": _thaw_json(self.authorization_snapshot),
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> EvidencePackage:
        """从 Package 快照恢复自身授权和引用不变量。"""
        data = _snapshot_data(
            snapshot,
            _SCHEMA_VERSION,
            {
                "schema_version",
                "package_id",
                "tenant_id",
                "run_id",
                "scope_id",
                "catalog_version",
                "expert_role_id",
                "entry_ids",
                "allowed_evidence_type_ids",
                "required_evidence_type_ids",
                "authorized_at",
                "authorization_snapshot",
            },
            "package",
        )
        try:
            entry_ids = _snapshot_string_list(data["entry_ids"], "package.entry_ids")
            allowed_ids = _snapshot_string_list(
                data["allowed_evidence_type_ids"],
                "package.allowed_evidence_type_ids",
            )
            required_ids = _snapshot_string_list(
                data["required_evidence_type_ids"],
                "package.required_evidence_type_ids",
            )
            return cls(
                package_id=_snapshot_string(data["package_id"], "package.package_id"),
                tenant_id=_snapshot_string(data["tenant_id"], "package.tenant_id"),
                run_id=_snapshot_string(data["run_id"], "package.run_id"),
                scope_id=_snapshot_string(data["scope_id"], "package.scope_id"),
                catalog_version=_snapshot_string(data["catalog_version"], "package.catalog_version"),
                expert_role_id=_snapshot_string(data["expert_role_id"], "package.expert_role_id"),
                entry_ids=tuple(entry_ids),
                allowed_evidence_type_ids=frozenset(allowed_ids),
                required_evidence_type_ids=frozenset(required_ids),
                authorized_at=_parse_datetime(data["authorized_at"], "package.authorized_at"),
                authorization_snapshot=_snapshot_mapping(
                    data["authorization_snapshot"],
                    "package.authorization_snapshot",
                ),
            )
        except EvidenceSnapshotError:
            raise
        except EvidenceValidationError as error:
            raise EvidenceSnapshotError(error.code, error.path, error.message) from error


__all__ = ["EvidencePackage"]
