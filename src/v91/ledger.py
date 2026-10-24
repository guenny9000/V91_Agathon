"""Strict local JSONL ledger with fail-closed hash-chain verification.

A hash chain detects edits when verified; it does not prove event truth,
authorship, trusted time, or WORM immutability. No damaged history is repaired.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ZERO_HASH = "0" * 64
UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")


class LedgerError(ValueError):
    """Ledger input or integrity validation failed."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LedgerError("Data must be JSON-serializable without NaN or Infinity.") from exc


def record_hash(record: dict[str, Any]) -> str:
    return hashlib.sha256(
        canonical_bytes({key: value for key, value in record.items() if key != "hash"})
    ).hexdigest()


def verify_ledger(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Read and verify a ledger without creating or modifying it."""
    ledger = Path(path)
    if ledger.is_symlink():
        raise LedgerError("Ledger path must not be a symbolic link.")
    if not ledger.exists():
        return {"status": "VALID_EMPTY", "records": 0, "last_hash": ZERO_HASH}
    if not ledger.is_file():
        raise LedgerError("Ledger path is not a regular file.")
    raw = ledger.read_text(encoding="utf-8")
    if not raw:
        return {"status": "VALID_EMPTY", "records": 0, "last_hash": ZERO_HASH}

    previous = ZERO_HASH
    count = 0
    for index, line in enumerate(raw.splitlines()):
        if not line.strip():
            raise LedgerError(f"Blank ledger line at line {index + 1}.")
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LedgerError(f"Malformed JSON at line {index + 1}.") from exc
        if not isinstance(item, dict):
            raise LedgerError(f"Ledger line {index + 1} must be a JSON object.")
        timestamp = item.get("timestamp_utc")
        if not isinstance(timestamp, str) or not UTC_TIMESTAMP_RE.fullmatch(timestamp):
            raise LedgerError(f"Invalid UTC timestamp at line {index + 1}.")
        try:
            parsed = datetime.fromisoformat(timestamp[:-1] + "+00:00")
            if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
                raise ValueError("timestamp is not UTC")
        except ValueError as exc:
            raise LedgerError(f"Invalid UTC timestamp at line {index + 1}.") from exc
        if item.get("sequence") != index:
            raise LedgerError(f"Sequence mismatch at line {index + 1}.")
        if item.get("previous_hash") != previous:
            raise LedgerError(f"Previous-hash mismatch at line {index + 1}.")
        actual = item.get("hash")
        if not isinstance(actual, str) or actual != record_hash(item):
            raise LedgerError(f"Hash mismatch at line {index + 1}.")
        previous = actual
        count += 1
    return {"status": "VALID", "records": count, "last_hash": previous}


def append_ledger_record(
    path: str | os.PathLike[str], action: str, actor: str, data: dict[str, Any],
) -> dict[str, Any]:
    """Append one record only after validating the existing ledger."""
    if not isinstance(action, str) or not action.strip():
        raise LedgerError("action must be a non-empty string.")
    if not isinstance(actor, str) or not actor.strip():
        raise LedgerError("actor must be a non-empty string.")
    if not isinstance(data, dict):
        raise LedgerError("data must be a JSON object.")
    canonical_bytes(data)  # Reject invalid JSON values before filesystem changes.

    ledger = Path(path)
    if ledger.is_symlink():
        raise LedgerError("Ledger path must not be a symbolic link.")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    lock = ledger.with_name(ledger.name + ".lock")
    try:
        lock_fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise LedgerError("Ledger lock exists; inspect it and fail closed rather than deleting it blindly.") from exc

    try:
        os.write(lock_fd, f"pid={os.getpid()} token={uuid.uuid4().hex}\n".encode("ascii"))
        os.fsync(lock_fd)
        if ledger.is_symlink():
            raise LedgerError("Ledger path must not be a symbolic link.")
        if not ledger.exists():
            fd = os.open(str(ledger), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.flush()
                os.fsync(stream.fileno())

        verified = verify_ledger(ledger)
        item: dict[str, Any] = {
            "sequence": verified["records"],
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "action": action.strip(),
            "actor": actor.strip(),
            "data": data,
            "previous_hash": verified["last_hash"],
        }
        item["hash"] = record_hash(item)
        encoded = canonical_bytes(item) + b"\n"
        fd = os.open(str(ledger), os.O_WRONLY | os.O_APPEND)
        with os.fdopen(fd, "ab") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        return item
    finally:
        os.close(lock_fd)
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, help="Path to the JSONL ledger.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify", help="Verify existing records without changing the ledger.")
    append = sub.add_parser("append", help="Append one explicitly supplied JSON object.")
    append.add_argument("--action", required=True)
    append.add_argument("--actor", required=True)
    append.add_argument("--data-json", required=True, help="JSON object; do not include secrets.")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify_ledger(args.ledger)
        else:
            data = json.loads(args.data_json)
            result = append_ledger_record(args.ledger, args.action, args.actor, data)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (LedgerError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "PENDING_WITNESS",
            "error_type": type(exc).__name__,
            "detail": str(exc),
            "changed": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
