from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.domain.evidence import (
    EvidenceChain,
    EvidenceEntry,
    EvidencePackage,
    EvidenceRelation,
    EvidenceRelationType,
    EvidenceSnapshotError,
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
        "authorization_snapshot": {"policy": "pricing-v1"},
    }
    values.update(overrides)
    return EvidencePackage(**values)


def make_chain(**overrides):
    values = {
        "chain_id": "chain-1",
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "scope_id": "scope-1",
        "catalog_version": "catalog-v1",
        "scope_snapshot": {"market": "US", "category": "audio"},
    }
    values.update(overrides)
    return EvidenceChain(**values)


def test_empty_chain_can_be_created_and_entries_are_immutable():
    chain = make_chain()
    entry = make_entry()
    updated = chain.add_entry(entry)

    assert chain.entries == ()
    assert updated.entries == (entry,)
    assert updated is not chain
    with pytest.raises(FrozenInstanceError):
        updated.entries += (entry,)


def test_chain_rejects_duplicate_and_cross_boundary_entries():
    entry = make_entry()
    with pytest.raises(EvidenceValidationError) as raised:
        make_chain(entries=(entry, entry))
    assert raised.value.code == "duplicate_entry_id"

    for field, value in (
        ("tenant_id", "other-tenant"),
        ("run_id", "other-run"),
        ("scope_id", "other-scope"),
        ("catalog_version", "catalog-v2"),
    ):
        with pytest.raises(EvidenceValidationError) as raised:
            make_chain(entries=(make_entry(**{field: value}),))
        assert raised.value.code == "context_mismatch"


def test_chain_requires_packages_to_reference_existing_complete_entries():
    entry = make_entry()
    chain = make_chain(entries=(entry,))
    package = make_package()
    assert chain.add_package(package).packages == (package,)

    with pytest.raises(EvidenceValidationError) as raised:
        make_chain(entries=(entry,), packages=(make_package(entry_ids=("missing",)),))
    assert raised.value.code == "unknown_entry_reference"

    with pytest.raises(EvidenceValidationError) as raised:
        make_chain(entries=(entry,), packages=(make_package(tenant_id="other-tenant"),))
    assert raised.value.code == "context_mismatch"


def test_chain_allows_only_one_package_per_package_id_and_expert_role():
    entry = make_entry()
    first = make_package()
    second_id = make_package(package_id="package-2", expert_role_id="other-expert")
    chain = make_chain(entries=(entry,), packages=(first,))

    with pytest.raises(EvidenceValidationError) as raised:
        chain.add_package(first)
    assert raised.value.code == "duplicate_package_id"

    with pytest.raises(EvidenceValidationError) as raised:
        chain.add_package(make_package(package_id="package-2"))
    assert raised.value.code == "duplicate_expert_role"

    assert chain.add_package(second_id).packages == (first, second_id)


def test_chain_rejects_invalid_lineage_and_accepts_parallel_aggregation():
    entries = (
        make_entry(entry_id="entry-1"),
        make_entry(entry_id="entry-2", payload={"price_band": "low"}),
        make_entry(entry_id="entry-3", payload={"price_band": "high"}),
        make_entry(entry_id="entry-4", payload={"recommendation": "observe"}),
    )
    chain = make_chain(entries=entries)
    first = EvidenceRelation(EvidenceRelationType.DERIVED_FROM, "entry-2", "entry-1")
    second = EvidenceRelation(EvidenceRelationType.DERIVED_FROM, "entry-3", "entry-1")
    aggregate = EvidenceRelation(EvidenceRelationType.DERIVED_FROM, "entry-4", "entry-2")

    chain = chain.add_relation(first).add_relation(second).add_relation(aggregate)
    assert chain.relations == (first, second, aggregate)

    with pytest.raises(EvidenceValidationError) as raised:
        chain.add_relation(first)
    assert raised.value.code == "duplicate_relation"

    with pytest.raises(EvidenceValidationError) as raised:
        chain.add_relation(EvidenceRelation(EvidenceRelationType.DERIVED_FROM, "entry-1", "missing"))
    assert raised.value.code == "unknown_relation_endpoint"

    with pytest.raises(EvidenceValidationError) as raised:
        chain.add_relation(EvidenceRelation(EvidenceRelationType.DERIVED_FROM, "entry-1", "entry-4"))
    assert raised.value.code == "lineage_cycle"


def test_chain_snapshot_is_stable_and_does_not_duplicate_package_payload():
    entry_one = make_entry(entry_id="entry-1")
    entry_two = make_entry(entry_id="entry-2", payload={"margin": 0.3}, evidence_type_id="margin-assessment")
    package = make_package(
        entry_ids=("entry-1", "entry-2"),
        required_evidence_type_ids=frozenset({"market-price-band", "margin-assessment"}),
    )
    relation = EvidenceRelation(EvidenceRelationType.DERIVED_FROM, "entry-2", "entry-1")
    chain = make_chain(
        entries=(entry_two, entry_one),
        packages=(package,),
        relations=(relation,),
    )
    snapshot = chain.to_snapshot()
    restored = EvidenceChain.from_snapshot(snapshot)

    assert restored == chain
    assert [item["entry_id"] for item in snapshot["entries"]] == ["entry-1", "entry-2"]
    assert snapshot["packages"][0]["entry_ids"] == ["entry-1", "entry-2"]
    assert "payload" not in snapshot["packages"][0]
    snapshot["scope_snapshot"]["market"] = "EU"
    snapshot["entries"][0]["payload"]["prices"][0]["p50"] = 100
    assert chain.scope_snapshot["market"] == "US"
    assert chain.entries[0].payload["prices"][0]["p50"] == 42.5


def test_chain_snapshot_rejects_invalid_relation_snapshot():
    snapshot = make_chain().to_snapshot()
    snapshot["relations"] = [
        {
            "schema_version": "evidence-relation-v1",
            "relation_type": "derived_from",
            "subject_entry_id": "entry-1",
        }
    ]

    with pytest.raises(EvidenceSnapshotError) as raised:
        EvidenceChain.from_snapshot(snapshot)
    assert raised.value.code == "missing_field"
