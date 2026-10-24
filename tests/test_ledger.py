import json

import pytest

from v91.ledger import (
    LedgerError, ZERO_HASH, append_ledger_record, record_hash, verify_ledger,
)


def test_append_and_verify_two_records(tmp_path):
    path = tmp_path / "audit.jsonl"
    first = append_ledger_record(path, "TASK_STARTED", "worker-a", {"purpose": "hash file"})
    second = append_ledger_record(path, "TASK_COMPLETED", "worker-a", {"status": "COMPLETED"})
    assert first["sequence"] == 0
    assert first["previous_hash"] == ZERO_HASH
    assert second["sequence"] == 1
    assert second["previous_hash"] == first["hash"]
    assert verify_ledger(path) == {
        "status": "VALID", "records": 2, "last_hash": second["hash"]
    }


def test_missing_ledger_verification_does_not_create_file(tmp_path):
    path = tmp_path / "missing.jsonl"
    assert verify_ledger(path) == {
        "status": "VALID_EMPTY", "records": 0, "last_hash": ZERO_HASH
    }
    assert not path.exists()


def test_tampering_fails_closed_and_append_does_not_repair(tmp_path):
    path = tmp_path / "audit.jsonl"
    append_ledger_record(path, "TASK_STARTED", "worker-a", {"purpose": "check"})
    record = json.loads(path.read_text(encoding="utf-8"))
    record["data"]["purpose"] = "altered"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    damaged = path.read_bytes()
    with pytest.raises(LedgerError, match="Hash mismatch"):
        verify_ledger(path)
    with pytest.raises(LedgerError, match="Hash mismatch"):
        append_ledger_record(path, "TASK_COMPLETED", "worker-a", {"status": "done"})
    assert path.read_bytes() == damaged


def test_malformed_json_and_legacy_array_are_not_migrated(tmp_path):
    path = tmp_path / "audit.jsonl"
    original = '[{"legacy":true}]'
    path.write_text(original, encoding="utf-8")
    with pytest.raises(LedgerError, match="must be a JSON object"):
        verify_ledger(path)
    assert path.read_text(encoding="utf-8") == original


def test_sequence_gap_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    append_ledger_record(path, "ONE", "tester", {})
    append_ledger_record(path, "TWO", "tester", {})
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[1]["sequence"] = 9
    path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="Sequence mismatch"):
        verify_ledger(path)


def test_invalid_json_data_is_rejected_before_file_creation(tmp_path):
    path = tmp_path / "audit.jsonl"
    with pytest.raises(LedgerError, match="JSON-serializable"):
        append_ledger_record(path, "BAD", "tester", {"value": float("nan")})
    assert not path.exists()


def test_existing_lock_stops_append_without_modifying_ledger(tmp_path):
    path = tmp_path / "audit.jsonl"
    append_ledger_record(path, "ONE", "tester", {})
    before = path.read_bytes()
    path.with_name(path.name + ".lock").write_text("unknown owner\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="Ledger lock exists"):
        append_ledger_record(path, "TWO", "tester", {})
    assert path.read_bytes() == before


def test_symlink_ledger_is_rejected(tmp_path):
    target = tmp_path / "target.jsonl"
    target.write_text("", encoding="utf-8")
    link = tmp_path / "ledger.jsonl"
    link.symlink_to(target)
    with pytest.raises(LedgerError, match="symbolic link"):
        verify_ledger(link)


@pytest.mark.parametrize("bad_timestamp", [
    "not-a-timestampZ", "2026-13-45T99:99:99Z", "2026-10-15T00:00:00+00:00",
])
def test_invalid_timestamp_fails_even_when_hash_is_recomputed(tmp_path, bad_timestamp):
    path = tmp_path / "audit.jsonl"
    append_ledger_record(path, "TASK_STARTED", "worker-a", {"purpose": "timestamp check"})
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    record["timestamp_utc"] = bad_timestamp
    record["hash"] = record_hash(record)
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="Invalid UTC timestamp"):
        verify_ledger(path)
