"""Evidence-safe weekly eco report built on the verified V91 JSONL ledger.

The index is an explicitly defined input metric in [0, 1]. Missing values
remain unknown; malformed or tampered ledger history stops report generation.
A hash chain detects changes but does not prove the truth of source telemetry.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .ledger import LedgerError, append_ledger_record, verify_ledger


def _parse_utc(value: str, field: str) -> datetime:
    """Parse an explicit UTC timestamp; reject naive or non-UTC timestamps."""
    if not isinstance(value, str):
        raise LedgerError(f"{field} must be an ISO-8601 UTC timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LedgerError(f"{field} must be an ISO-8601 UTC timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise LedgerError(f"{field} must include a UTC timezone.")
    return parsed.astimezone(timezone.utc)


def generate_weekly_report(
    ledger_path: str | Path,
    *,
    persist: bool = True,
    actor: str = "v91-eco-reporter",
    period_start_utc: str | None = None,
    period_end_utc: str | None = None,
) -> dict[str, Any]:
    """Build a report from verified source records within a UTC time window.

    By default, the report covers the preceding seven days. The window is
    [period_start_utc, period_end_utc): its start is inclusive and its end
    exclusive. Report records are never treated as fresh measurements.
    Records without data.eco_efficiency_index remain missing; values must be
    finite numbers in [0, 1]. Invalid ledger history fails closed.
    """
    path = Path(ledger_path)
    verification = verify_ledger(path)
    if verification["status"] not in {"VALID", "VALID_EMPTY"}:
        raise LedgerError("Ledger verification did not return a recognized valid state.")

    now = datetime.now(timezone.utc)
    end = _parse_utc(period_end_utc, "period_end_utc") if period_end_utc else now
    start = (
        _parse_utc(period_start_utc, "period_start_utc")
        if period_start_utc
        else end - timedelta(days=7)
    )
    if start >= end:
        raise LedgerError("The report period start must be earlier than its end.")

    now = datetime.now(timezone.utc)
    end = _parse_utc(period_end_utc, "period_end_utc") if period_end_utc else now
    start = _parse_utc(period_start_utc, "period_start_utc") if period_start_utc else end - timedelta(days=7)
    if start >= end:
        raise LedgerError("The report period start must be earlier than its end.")

    records: list[dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LedgerError(f"Malformed JSON at line {line_number}.") from exc
                if not isinstance(record, dict):
                    raise LedgerError(f"Ledger line {line_number} must be a JSON object.")
                # Persisted reports are audit outputs, not new source observations.
                if record.get("action") == "ECO_WEEKLY_REPORT":
                    continue
                timestamp = _parse_utc(record.get("timestamp_utc"), f"line {line_number} timestamp_utc")
                if start <= timestamp < end:
                    if record.get("action") == "ECO_WEEKLY_REPORT":
                    continue
                timestamp = _parse_utc(record.get("timestamp_utc"), f"line {line_number} timestamp_utc")
                if start <= timestamp < end:
                    records.append(record)

    values: list[float] = []
    missing_count = 0
    for record in records:
        data = record.get("data")
        if not isinstance(data, dict) or "eco_efficiency_index" not in data:
            missing_count += 1
            continue
        value = data["eco_efficiency_index"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise LedgerError("eco_efficiency_index must be a finite number in [0, 1].")
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise LedgerError("eco_efficiency_index must be a finite number in [0, 1].")
        values.append(float(value))

    report: dict[str, Any] = {
        "report_timestamp_utc": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "period_start_utc": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "period_end_utc": end.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "period_semantics": "START_INCLUSIVE_END_EXCLUSIVE",
        "source_ledger_status": verification["status"],
        "source_records": len(records),
        "records_with_metric": len(values),
        "records_missing_metric": missing_count,
        "average_eco_efficiency_index": (sum(values) / len(values)) if values else None,
        "metric_status": "MEASURED" if values else "UNKNOWN",
        "integrity_status": "VERIFIED" if verification["status"] == "VALID" else "VALID_EMPTY",
        "source_last_hash": verification["last_hash"],
        "persisted": False,
    }

    if persist:
        appended = append_ledger_record(
            path,
            action="ECO_WEEKLY_REPORT",
            actor=actor,
            data=report,
        )
        report["persisted"] = True
        report["report_ledger_sequence"] = appended["sequence"]
        report["report_ledger_hash"] = appended["hash"]
    return report
