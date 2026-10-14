import json

import pytest

from v91.audit import HashChainAuditLogger


def test_hash_chain_logger_appends_and_verifies(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = HashChainAuditLogger(path)

    first = logger.log("LOGIN", "demo-user", {"source": "synthetic-test"})
    second = logger.log("REVIEW", "demo-user", {"accepted": True})

    assert first["seq"] == 0
    assert first["prev_hash"] == HashChainAuditLogger.ZERO_HASH
    assert second["seq"] == 1
    assert second["prev_hash"] == first["hash"]
    assert logger.verify_chain() == [first, second]


def test_hash_chain_detects_tampering_and_preserves_file(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = HashChainAuditLogger(path)
    logger.log("LOGIN", "demo-user", {"role": "user"})
    original = path.read_text(encoding="utf-8")

    record = json.loads(original)
    record["additional_info"]["role"] = "admin"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    tampered = path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        logger.verify_chain()
    with pytest.raises(ValueError, match="hash mismatch"):
        logger.log("SHOULD_NOT_APPEND", "demo-user")
    assert path.read_text(encoding="utf-8") == tampered


def test_hash_chain_rejects_sequence_gaps(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = HashChainAuditLogger(path)
    logger.log("ONE", "demo-user")
    logger.log("TWO", "demo-user")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[1]["seq"] = 7
    path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="sequence gap"):
        logger.verify_chain()


def test_legacy_json_array_is_not_overwritten_or_migrated(tmp_path):
    path = tmp_path / "legacy.json"
    original = '[{"legacy": true}]'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError):
        HashChainAuditLogger(path)
    assert path.read_text(encoding="utf-8") == original
