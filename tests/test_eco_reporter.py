import json

import pytest

from v91.eco_reporter import generate_weekly_report
from v91.ledger import LedgerError, append_ledger_record, verify_ledger


def test_report_averages_only_measured_values_and_counts_missing(tmp_path):
    ledger = tmp_path / "audit.jsonl"
    append_ledger_record(ledger, "METRIC", "test", {"eco_efficiency_index": 0.8})
    append_ledger_record(ledger, "NO_METRIC", "test", {"note": "no telemetry"})

    report = generate_weekly_report(ledger, persist=False)

    assert report["source_records"] == 2
    assert report["records_with_metric"] == 1
    assert report["records_missing_metric"] == 1
    assert report["average_eco_efficiency_index"] == pytest.approx(0.8)
    assert report["metric_status"] == "MEASURED"
    assert report["persisted"] is False
    assert verify_ledger(ledger)["records"] == 2


def test_no_metric_is_unknown_not_a_fabricated_default(tmp_path):
    ledger = tmp_path / "audit.jsonl"
    append_ledger_record(ledger, "NO_METRIC", "test", {"note": "missing"})

    report = generate_weekly_report(ledger, persist=False)

    assert report["average_eco_efficiency_index"] is None
    assert report["metric_status"] == "UNKNOWN"
    assert report["records_missing_metric"] == 1


def test_report_is_appended_to_verified_ledger(tmp_path):
    ledger = tmp_path / "audit.jsonl"
    append_ledger_record(ledger, "METRIC", "test", {"eco_efficiency_index": 0.6})

    report = generate_weekly_report(ledger, persist=True)

    verification = verify_ledger(ledger)
    assert report["persisted"] is True
    assert report["report_ledger_sequence"] == 1
    assert verification["status"] == "VALID"
    assert verification["records"] == 2
    saved_report = json.loads(ledger.read_text(encoding="utf-8").splitlines()[1])
    assert saved_report["action"] == "ECO_WEEKLY_REPORT"
    assert saved_report["data"]["average_eco_efficiency_index"] == pytest.approx(0.6)


@pytest.mark.parametrize("bad_value", [True, "0.9", float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_metric_fails_closed(tmp_path, bad_value):
    ledger = tmp_path / "audit.jsonl"
    # The ledger permits JSON-compatible metric payloads, but the reporter
    # rejects semantically invalid scores rather than coercing them.
    if isinstance(bad_value, float) and (bad_value != bad_value or bad_value in (float("inf"), float("-inf"))):
        # NaN/Infinity cannot be written to the canonical ledger at all.
        with pytest.raises(LedgerError):
            append_ledger_record(ledger, "METRIC", "test", {"eco_efficiency_index": bad_value})
        return
    append_ledger_record(ledger, "METRIC", "test", {"eco_efficiency_index": bad_value})
    with pytest.raises(LedgerError, match="finite number"):
        generate_weekly_report(ledger, persist=False)


def test_tampered_ledger_blocks_report_and_does_not_repair(tmp_path):
    ledger = tmp_path / "audit.jsonl"
    append_ledger_record(ledger, "METRIC", "test", {"eco_efficiency_index": 0.5})
    record = json.loads(ledger.read_text(encoding="utf-8"))
    record["data"]["eco_efficiency_index"] = 0.9
    ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")
    damaged = ledger.read_bytes()

    with pytest.raises(LedgerError, match="Hash mismatch"):
        generate_weekly_report(ledger, persist=True)
    assert ledger.read_bytes() == damaged
