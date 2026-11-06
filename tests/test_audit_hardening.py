"""Audit hardening regression tests (ported from superseded PR #1)."""
import json

import pytest

from v91.audit import HashChainAuditLogger


def test_empty_existing_file_fails_closed(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        HashChainAuditLogger(path)


def test_unknown_record_key_is_rejected(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = HashChainAuditLogger(path)
    logger.log("LOGIN", "demo-user")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[0]["extra_field"] = "injected"
    path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        logger.verify_chain()


def test_missing_record_key_is_rejected(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = HashChainAuditLogger(path)
    logger.log("LOGIN", "demo-user")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    del records[0]["additional_info"]
    path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        logger.verify_chain()


def test_non_utc_timestamp_is_rejected(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = HashChainAuditLogger(path)
    logger.log("LOGIN", "demo-user")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[0]["timestamp_utc"] = "2026-11-06T10:00:00+01:00"
    path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="UTC"):
        logger.verify_chain()


def test_malformed_timestamp_is_rejected(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = HashChainAuditLogger(path)
    logger.log("LOGIN", "demo-user")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[0]["timestamp_utc"] = "not-a-dateZ"
    path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ISO-8601"):
        logger.verify_chain()


def test_valid_chain_still_passes_after_hardening(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = HashChainAuditLogger(path)
    first = logger.log("LOGIN", "demo-user", {"source": "synthetic-test"})
    second = logger.log("REVIEW", "demo-user", {"accepted": True})
    records = logger.verify_chain()
    assert records == [first, second]
    assert second["prev_hash"] == first["hash"]
