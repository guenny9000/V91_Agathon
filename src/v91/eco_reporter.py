"""Evidence-safe weekly eco report built on the verified V91 JSONL ledger.

The index is an explicitly defined input metric in [0, 1]. Missing values
remain unknown; malformed or tampered ledger history stops report generation.
A hash chain detects changes but does not prove the truth of source telemetry.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ledger import LedgerError, append_ledger_record, verify_ledger


def generate_weekly_report(
    ledger_path: str | Path,
    *,
    persist: bool = True,
    actor: str = "v91-eco-reporter",
) -> dict[str, Any]:
    """Build a report from verified ledger records; optionally append the report.

    Records without data.eco_efficiency_index are counted as missing, not
    assigned a default score. Present values must be finite numbers in [0, 1].
    No rows are silently skipped.
    """
    path = Path(ledger_path)
    verification = verify_ledger(path)
    if verification["status"] not in {"VALID", "VALID_EMPTY"}:
        raise LedgerError("Ledger verification did not return a recognized valid state.")

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
        "report_timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
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
