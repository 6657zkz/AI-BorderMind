from datetime import datetime, timedelta, timezone
import hashlib

import pytest

from app.domain.evidence import (
    EvidenceEntry,
    EvidenceSnapshotError,
    EvidenceSource,
    EvidenceStatus,
    EvidenceValidationError,
)


UTC = timezone.utc


def make_source(**overrides):
    values = {
        "operator_id": "price-percentiles",
        "invocation_id": "invocation-1",
        "operator_contract_version": "operator-v1",
        "input_digest": hashlib.sha256(b"market-input").hexdigest(),
    }
    values.update(overrides)
    return EvidenceSource(**values)


def make_entry(**overrides):
    values = {
        "entry_id": "entry-1",
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "scope_id": "scope-1",
        "catalog_version": "catalog-v1",
        "evidence_type_id": "market-price-band",
        "source": make_source(),
        "payload": {"prices": [{"p50": 42.5}], "market": "US"},
        "status": EvidenceStatus.VERIFIED,
        "observed_at": datetime(2026, 8, 31, 10, tzinfo=UTC),
        "recorded_at": datetime(2026, 8, 31, 11, tzinfo=UTC),
        "expires_at": datetime(2026, 9, 1, 11, tzinfo=UTC),
        "quality_flags": frozenset({"sample-size-ok"}),
    }
    values.update(overrides)
    return EvidenceEntry(**values)


def test_entry_freezes_payload_and_calculates_stable_digest():
    payload = {"facts": [{"price": 42.5}], "market": "US"}
    entry = make_entry(payload=payload)
    expected = hashlib.sha256(b'{"facts":[{"price":42.5}],"market":"US"}').hexdigest()

    payload["facts"][0]["price"] = 99

    assert entry.payload["facts"][0]["price"] == 42.5
    assert entry.payload_digest == expected
    with pytest.raises(TypeError):
        entry.payload["new"] = True
    with pytest.raises(TypeError):
        entry.payload["facts"][0]["price"] = 99


def test_entry_normalizes_timestamps_to_utc():
    entry = make_entry(
        observed_at=datetime(2026, 8, 31, 18, tzinfo=timezone(timedelta(hours=8))),
        recorded_at=datetime(2026, 8, 31, 19, tzinfo=timezone(timedelta(hours=8))),
    )

    assert entry.observed_at == datetime(2026, 8, 31, 10, tzinfo=UTC)
    assert entry.recorded_at == datetime(2026, 8, 31, 11, tzinfo=UTC)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        "not-an-object",
        {1: "non-string-key"},
        {"value": {"bad": {1, 2}}},
        {"value": float("nan")},
        {"value": float("inf")},
    ],
)
def test_entry_rejects_invalid_json_payload(payload):
    with pytest.raises(EvidenceValidationError) as raised:
        make_entry(payload=payload)

    assert raised.value.code in {"invalid_json_object", "invalid_json_value", "non_finite_number"}


def test_entry_rejects_invalid_time_and_blank_identifiers():
    with pytest.raises(EvidenceValidationError) as raised:
        make_entry(entry_id=" ")
    assert raised.value.code == "blank_identifier"

    with pytest.raises(EvidenceValidationError) as raised:
        make_entry(
            observed_at=datetime(2026, 8, 31, 12, tzinfo=UTC),
            recorded_at=datetime(2026, 8, 31, 11, tzinfo=UTC),
        )
    assert raised.value.code == "invalid_timestamp_order"

    with pytest.raises(EvidenceValidationError) as raised:
        make_entry(observed_at=datetime(2026, 8, 31, 10))
    assert raised.value.code == "timezone_required"


def test_entry_snapshot_round_trip_is_independent_and_stable():
    entry = make_entry()
    snapshot = entry.to_snapshot()
    restored = EvidenceEntry.from_snapshot(snapshot)

    snapshot["payload"]["prices"][0]["p50"] = 100
    snapshot["source"]["operator_id"] = "other-operator"

    assert restored == entry
    assert entry.to_snapshot()["payload"]["prices"][0]["p50"] == 42.5
    assert entry.to_snapshot() == restored.to_snapshot()
    assert entry.to_snapshot()["observed_at"].endswith("Z")


def test_entry_snapshot_rejects_wrong_digest_and_schema():
    snapshot = make_entry().to_snapshot()
    snapshot["payload_digest"] = "0" * 64

    with pytest.raises(EvidenceSnapshotError) as raised:
        EvidenceEntry.from_snapshot(snapshot)
    assert raised.value.code == "payload_digest_mismatch"

    snapshot = make_entry().to_snapshot()
    snapshot["schema_version"] = "evidence-entry-v2"

    with pytest.raises(EvidenceSnapshotError) as raised:
        EvidenceEntry.from_snapshot(snapshot)
    assert raised.value.code == "unsupported_snapshot_version"


def test_entry_source_snapshot_round_trip():
    source = make_source()

    assert EvidenceSource.from_snapshot(source.to_snapshot()) == source

    with pytest.raises(EvidenceSnapshotError) as raised:
        EvidenceSource.from_snapshot({"schema_version": "evidence-source-v1"})
    assert raised.value.code == "missing_field"
