from datetime import datetime, timedelta, timezone

import pytest

from app.domain.evidence import (
    EvidenceEntry,
    EvidencePackage,
    EvidenceStatus,
    EvidenceValidationError,
)
from .test_entry import make_entry


UTC = timezone.utc
AUTHORIZED_AT = datetime(2026, 8, 31, 12, tzinfo=UTC)


def make_package(**overrides):
    values = {
        "package_id": "package-1",
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "scope_id": "scope-1",
        "catalog_version": "catalog-v1",
        "expert_role_id": "pricing-expert",
        "entry_ids": ("entry-1",),
        "allowed_evidence_type_ids": frozenset({"market-price-band", "margin-assessment"}),
        "required_evidence_type_ids": frozenset({"market-price-band"}),
        "authorized_at": AUTHORIZED_AT,
        "authorization_snapshot": {"policy": "pricing-v1", "limits": {"max_entries": 4}},
    }
    values.update(overrides)
    return EvidencePackage(**values)


def test_package_only_snapshots_entry_references():
    package = make_package()
    snapshot = package.to_snapshot()

    assert snapshot["entry_ids"] == ["entry-1"]
    assert "payload" not in snapshot
    assert "entries" not in snapshot
    assert EvidencePackage.from_snapshot(snapshot) == package

    snapshot["authorization_snapshot"]["limits"]["max_entries"] = 99
    assert package.authorization_snapshot["limits"]["max_entries"] == 4


def test_package_rejects_duplicate_entries_and_invalid_required_types():
    with pytest.raises(EvidenceValidationError) as raised:
        make_package(entry_ids=("entry-1", "entry-1"))
    assert raised.value.code == "duplicate_entry_id"

    with pytest.raises(EvidenceValidationError) as raised:
        make_package(
            allowed_evidence_type_ids=frozenset({"market-price-band"}),
            required_evidence_type_ids=frozenset({"margin-assessment"}),
        )
    assert raised.value.code == "required_evidence_not_allowed"


def test_package_validates_only_referenced_verified_entries():
    entry = make_entry(recorded_at=datetime(2026, 8, 31, 11, tzinfo=UTC))
    unrelated = make_entry(
        entry_id="unrelated",
        evidence_type_id="margin-assessment",
        payload={"margin": 0.3},
    )

    make_package().validate_entries((entry, unrelated))


def test_package_rejects_missing_or_mismatched_entries():
    package = make_package()
    with pytest.raises(EvidenceValidationError) as raised:
        package.validate_entries(())
    assert raised.value.code == "unknown_entry_reference"

    for field, value in (
        ("tenant_id", "other-tenant"),
        ("run_id", "other-run"),
        ("scope_id", "other-scope"),
        ("catalog_version", "catalog-v2"),
    ):
        with pytest.raises(EvidenceValidationError) as raised:
            package.validate_entries((make_entry(**{field: value}),))
        assert raised.value.code == "context_mismatch"


def test_package_rejects_unusable_or_incomplete_evidence():
    for status in (EvidenceStatus.PRODUCED, EvidenceStatus.REJECTED):
        with pytest.raises(EvidenceValidationError) as raised:
            make_package().validate_entries((make_entry(status=status),))
        assert raised.value.code == "entry_not_usable"

    with pytest.raises(EvidenceValidationError) as raised:
        make_package(
            entry_ids=("entry-1", "margin-1"),
            required_evidence_type_ids=frozenset({"market-price-band", "margin-assessment"}),
        ).validate_entries(
            (
                make_entry(),
                make_entry(
                    entry_id="margin-1",
                    evidence_type_id="margin-assessment",
                    payload={"margin": 0.3},
                    status=EvidenceStatus.PRODUCED,
                ),
            )
        )
    assert raised.value.code == "entry_not_usable"

    with pytest.raises(EvidenceValidationError) as raised:
        make_package(
            entry_ids=("entry-1",),
            required_evidence_type_ids=frozenset({"market-price-band", "margin-assessment"}),
        ).validate_entries((make_entry(),))
    assert raised.value.code == "missing_required_evidence"

    with pytest.raises(EvidenceValidationError) as raised:
        make_package().validate_entries(
            (make_entry(recorded_at=datetime(2026, 8, 31, 13, tzinfo=UTC)),)
        )
    assert raised.value.code == "entry_recorded_after_authorization"

    with pytest.raises(EvidenceValidationError) as raised:
        make_package().validate_entries(
            (
                make_entry(
                    expires_at=datetime(2026, 8, 31, 12, tzinfo=UTC),
                ),
            )
        )
    assert raised.value.code == "entry_expired_at_authorization"


def test_package_rejects_disallowed_type_and_accepts_required_type():
    with pytest.raises(EvidenceValidationError) as raised:
        make_package(
            allowed_evidence_type_ids=frozenset({"margin-assessment"}),
            required_evidence_type_ids=frozenset(),
        ).validate_entries((make_entry(),))
    assert raised.value.code == "entry_not_allowed"

    margin_entry = make_entry(
        entry_id="margin-1",
        evidence_type_id="margin-assessment",
        payload={"margin": 0.3},
    )
    package = make_package(
        entry_ids=("entry-1", "margin-1"),
        required_evidence_type_ids=frozenset({"market-price-band", "margin-assessment"}),
    )
    package.validate_entries((make_entry(), margin_entry))
