from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any


_SCHEMA_VERSION = "evidence-entry-v1"
_SOURCE_SCHEMA_VERSION = "evidence-source-v1"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class EvidenceIssue:
    """描述一个 Evidence 领域校验问题。"""

    code: str
    path: str
    message: str


class EvidenceValidationError(ValueError):
    """表示 Evidence 领域对象不满足自身不变量。"""

    def __init__(
        self,
        code: str,
        path: str,
        message: str,
    ) -> None:
        self.issues = (EvidenceIssue(code=code, path=path, message=message),)
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


class EvidenceSnapshotError(EvidenceValidationError):
    """表示 Evidence 快照结构、版本或完整性校验失败。"""


class EvidenceStatus(str, Enum):
    """EvidenceEntry 的受控状态。"""

    PRODUCED = "produced"
    VERIFIED = "verified"
    REJECTED = "rejected"


@dataclass(frozen=True)
class EvidenceSource:
    """记录生成 EvidenceEntry 的一次 Operator 调用来源。"""

    operator_id: str
    invocation_id: str
    operator_contract_version: str
    input_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "operator_id", _identifier(self.operator_id, "operator_id"))
        object.__setattr__(self, "invocation_id", _identifier(self.invocation_id, "invocation_id"))
        object.__setattr__(
            self,
            "operator_contract_version",
            _identifier(self.operator_contract_version, "operator_contract_version"),
        )
        object.__setattr__(self, "input_digest", _digest(self.input_digest, "input_digest"))

    def to_snapshot(self) -> dict[str, object]:
        """导出独立的来源快照。"""
        return {
            "schema_version": _SOURCE_SCHEMA_VERSION,
            "operator_id": self.operator_id,
            "invocation_id": self.invocation_id,
            "operator_contract_version": self.operator_contract_version,
            "input_digest": self.input_digest,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> EvidenceSource:
        """从来源快照恢复 EvidenceSource。"""
        data = _snapshot_data(
            snapshot,
            _SOURCE_SCHEMA_VERSION,
            {
                "schema_version",
                "operator_id",
                "invocation_id",
                "operator_contract_version",
                "input_digest",
            },
            "source",
        )
        try:
            return cls(
                operator_id=_snapshot_string(data["operator_id"], "source.operator_id"),
                invocation_id=_snapshot_string(data["invocation_id"], "source.invocation_id"),
                operator_contract_version=_snapshot_string(
                    data["operator_contract_version"],
                    "source.operator_contract_version",
                ),
                input_digest=_snapshot_string(data["input_digest"], "source.input_digest"),
            )
        except EvidenceValidationError as error:
            raise _snapshot_error(error) from error


@dataclass(frozen=True)
class EvidenceEntry:
    """保存一次 Operator 结果对应的不可变运行时证据。"""

    entry_id: str
    tenant_id: str
    run_id: str
    scope_id: str
    catalog_version: str
    evidence_type_id: str
    source: EvidenceSource
    payload: Mapping[str, object]
    status: EvidenceStatus
    observed_at: datetime
    recorded_at: datetime
    expires_at: datetime | None = None
    quality_flags: frozenset[str] = frozenset()
    payload_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "entry_id",
            "tenant_id",
            "run_id",
            "scope_id",
            "catalog_version",
            "evidence_type_id",
        ):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))

        if not isinstance(self.source, EvidenceSource):
            raise EvidenceValidationError("invalid_type", "source", "source must be EvidenceSource.")

        frozen_payload = _freeze_json_object(self.payload, "payload")
        object.__setattr__(self, "payload", frozen_payload)

        status = self.status
        if not isinstance(status, EvidenceStatus):
            try:
                status = EvidenceStatus(status)
            except (TypeError, ValueError) as error:
                raise EvidenceValidationError(
                    "invalid_status",
                    "status",
                    "status must be a supported EvidenceStatus value.",
                ) from error
        object.__setattr__(self, "status", status)

        observed_at = _utc_datetime(self.observed_at, "observed_at")
        recorded_at = _utc_datetime(self.recorded_at, "recorded_at")
        expires_at = (
            _utc_datetime(self.expires_at, "expires_at") if self.expires_at is not None else None
        )
        if observed_at > recorded_at:
            raise EvidenceValidationError(
                "invalid_timestamp_order",
                "observed_at",
                "observed_at must not be later than recorded_at.",
            )
        if expires_at is not None and expires_at <= observed_at:
            raise EvidenceValidationError(
                "invalid_timestamp_order",
                "expires_at",
                "expires_at must be later than observed_at.",
            )
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "recorded_at", recorded_at)
        object.__setattr__(self, "expires_at", expires_at)

        object.__setattr__(self, "quality_flags", _string_set(self.quality_flags, "quality_flags"))
        object.__setattr__(self, "payload_digest", _payload_digest(frozen_payload))

    def to_snapshot(self) -> dict[str, object]:
        """导出不共享可变嵌套值的 Entry 快照。"""
        return {
            "schema_version": _SCHEMA_VERSION,
            "entry_id": self.entry_id,
            "tenant_id": self.tenant_id,
            "run_id": self.run_id,
            "scope_id": self.scope_id,
            "catalog_version": self.catalog_version,
            "evidence_type_id": self.evidence_type_id,
            "source": self.source.to_snapshot(),
            "payload": _thaw_json(self.payload),
            "status": self.status.value,
            "observed_at": _datetime_snapshot(self.observed_at),
            "recorded_at": _datetime_snapshot(self.recorded_at),
            "expires_at": _datetime_snapshot(self.expires_at) if self.expires_at is not None else None,
            "quality_flags": sorted(self.quality_flags),
            "payload_digest": self.payload_digest,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> EvidenceEntry:
        """从 Entry 快照恢复并重新验证 payload digest。"""
        data = _snapshot_data(
            snapshot,
            _SCHEMA_VERSION,
            {
                "schema_version",
                "entry_id",
                "tenant_id",
                "run_id",
                "scope_id",
                "catalog_version",
                "evidence_type_id",
                "source",
                "payload",
                "status",
                "observed_at",
                "recorded_at",
                "expires_at",
                "quality_flags",
                "payload_digest",
            },
            "entry",
        )
        try:
            source_snapshot = _snapshot_mapping(data["source"], "entry.source")
            payload = _snapshot_mapping(data["payload"], "entry.payload")
            status = _snapshot_string(data["status"], "entry.status")
            quality_flags = _snapshot_string_list(data["quality_flags"], "entry.quality_flags")
            recorded_digest = _snapshot_string(data["payload_digest"], "entry.payload_digest")
            entry = cls(
                entry_id=_snapshot_string(data["entry_id"], "entry.entry_id"),
                tenant_id=_snapshot_string(data["tenant_id"], "entry.tenant_id"),
                run_id=_snapshot_string(data["run_id"], "entry.run_id"),
                scope_id=_snapshot_string(data["scope_id"], "entry.scope_id"),
                catalog_version=_snapshot_string(data["catalog_version"], "entry.catalog_version"),
                evidence_type_id=_snapshot_string(data["evidence_type_id"], "entry.evidence_type_id"),
                source=EvidenceSource.from_snapshot(source_snapshot),
                payload=payload,
                status=status,
                observed_at=_parse_datetime(data["observed_at"], "entry.observed_at"),
                recorded_at=_parse_datetime(data["recorded_at"], "entry.recorded_at"),
                expires_at=(
                    _parse_datetime(data["expires_at"], "entry.expires_at")
                    if data["expires_at"] is not None
                    else None
                ),
                quality_flags=frozenset(quality_flags),
            )
            if recorded_digest != entry.payload_digest:
                raise EvidenceSnapshotError(
                    "payload_digest_mismatch",
                    "entry.payload_digest",
                    "payload_digest does not match payload.",
                )
            return entry
        except EvidenceSnapshotError:
            raise
        except EvidenceValidationError as error:
            raise _snapshot_error(error) from error


def _identifier(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceValidationError("blank_identifier", path, "identifier must be a non-blank string.")
    return value


def _digest(value: object, path: str) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise EvidenceValidationError(
            "invalid_digest",
            path,
            "digest must be a lowercase SHA-256 hexadecimal string.",
        )
    return value


def _string_set(value: object, path: str) -> frozenset[str]:
    if isinstance(value, (str, bytes)):
        raise EvidenceValidationError("invalid_type", path, "value must be a set of strings.")
    try:
        values = frozenset(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise EvidenceValidationError("invalid_type", path, "value must be a set of strings.") from error
    for index, item in enumerate(values):
        if not isinstance(item, str) or not item.strip():
            raise EvidenceValidationError(
                "blank_identifier",
                f"{path}[{index}]",
                "set members must be non-blank strings.",
            )
    return values


def _freeze_json_object(value: object, path: str) -> Mapping[str, object]:
    frozen = _freeze_json(value, path, set())
    if not isinstance(frozen, MappingProxyType):
        raise EvidenceValidationError("invalid_json_object", path, "value must be a JSON object.")
    return frozen


def _freeze_json(value: object, path: str, active_containers: set[int]) -> object:
    if isinstance(value, Mapping):
        marker = id(value)
        if marker in active_containers:
            raise EvidenceValidationError("invalid_json_value", path, "cyclic JSON values are not allowed.")
        active_containers.add(marker)
        try:
            frozen: dict[str, object] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise EvidenceValidationError(
                        "invalid_json_value",
                        f"{path}.{key!r}",
                        "JSON object keys must be strings.",
                    )
                frozen[key] = _freeze_json(item, f"{path}.{key}", active_containers)
            return MappingProxyType(frozen)
        finally:
            active_containers.remove(marker)

    if isinstance(value, (list, tuple)):
        marker = id(value)
        if marker in active_containers:
            raise EvidenceValidationError("invalid_json_value", path, "cyclic JSON values are not allowed.")
        active_containers.add(marker)
        try:
            return tuple(_freeze_json(item, f"{path}[{index}]", active_containers) for index, item in enumerate(value))
        finally:
            active_containers.remove(marker)

    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvidenceValidationError(
                "non_finite_number",
                path,
                "JSON numbers must be finite.",
            )
        return value

    raise EvidenceValidationError("invalid_json_value", path, "value is not a supported JSON value.")


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _payload_digest(payload: Mapping[str, object]) -> str:
    serialized = json.dumps(
        _thaw_json(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _utc_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime):
        raise EvidenceValidationError("invalid_type", path, "value must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise EvidenceValidationError("timezone_required", path, "datetime must include a timezone.")
    return value.astimezone(timezone.utc)


def _datetime_snapshot(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise EvidenceSnapshotError("invalid_type", path, "timestamp must be an ISO-8601 string.")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise EvidenceSnapshotError("invalid_timestamp", path, "timestamp is not valid ISO-8601.") from error
    try:
        return _utc_datetime(parsed, path)
    except EvidenceValidationError as error:
        raise _snapshot_error(error) from error


def _snapshot_data(
    snapshot: object,
    expected_schema: str,
    expected_keys: set[str],
    path: str,
) -> dict[str, object]:
    data = _snapshot_mapping(snapshot, path)
    actual_keys = set(data)
    missing = expected_keys - actual_keys
    if missing:
        missing_key = sorted(missing)[0]
        raise EvidenceSnapshotError("missing_field", f"{path}.{missing_key}", "snapshot field is required.")
    unexpected = actual_keys - expected_keys
    if unexpected:
        unexpected_key = sorted(unexpected)[0]
        raise EvidenceSnapshotError(
            "unexpected_field",
            f"{path}.{unexpected_key}",
            "snapshot field is not supported.",
        )
    if data["schema_version"] != expected_schema:
        raise EvidenceSnapshotError(
            "unsupported_snapshot_version",
            f"{path}.schema_version",
            f"schema version must be {expected_schema!r}.",
        )
    return data


def _snapshot_mapping(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise EvidenceSnapshotError("invalid_type", path, "snapshot value must be an object.")
    return dict(value)


def _snapshot_string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise EvidenceSnapshotError("invalid_type", path, "snapshot value must be a string.")
    return value


def _snapshot_string_list(value: object, path: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise EvidenceSnapshotError("invalid_type", path, "snapshot value must be a list of strings.")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise EvidenceSnapshotError("invalid_type", f"{path}[{index}]", "list member must be a string.")
        result.append(item)
    return result


def _snapshot_error(error: EvidenceValidationError) -> EvidenceSnapshotError:
    return EvidenceSnapshotError(error.code, error.path, error.message)


__all__ = [
    "EvidenceEntry",
    "EvidenceIssue",
    "EvidenceSnapshotError",
    "EvidenceSource",
    "EvidenceStatus",
    "EvidenceValidationError",
    "_datetime_snapshot",
    "_freeze_json_object",
    "_identifier",
    "_parse_datetime",
    "_snapshot_data",
    "_snapshot_mapping",
    "_snapshot_string",
    "_snapshot_string_list",
    "_string_set",
    "_thaw_json",
    "_utc_datetime",
]
