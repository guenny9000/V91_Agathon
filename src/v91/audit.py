"""Append-only, hash-linked JSONL audit records with fail-closed verification.

This logger detects edits and broken sequence links. It does not provide WORM
storage, independent timestamps, or proof that an event is truthful.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ZERO_HASH = "0" * 64


class HashChainAuditLogger:
    ZERO_HASH = ZERO_HASH

    def __init__(self, log_file: str | os.PathLike[str]) -> None:
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.log_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            # Existing data is verified, never reset or migrated implicitly.
            self.verify_chain()
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.flush()
                os.fsync(stream.fileno())

    @staticmethod
    def _canonical(value: Any) -> bytes:
        try:
            return json.dumps(
                value, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("Audit data must be JSON-serializable without NaN or Infinity.") from exc

    @classmethod
    def _hash_record(cls, record: dict[str, Any]) -> str:
        payload = {key: value for key, value in record.items() if key != "hash"}
        return hashlib.sha256(cls._canonical(payload)).hexdigest()

    def verify_chain(self) -> list[dict[str, Any]]:
        if not self.log_file.exists():
            return []
        raw = self.log_file.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        records: list[dict[str, Any]] = []
        expected_prev = ZERO_HASH
        for expected_seq, line in enumerate(raw.splitlines()):
            if not line.strip():
                raise ValueError(f"Blank line in audit ledger at line {expected_seq + 1}.")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON at audit line {expected_seq + 1}.") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Audit line {expected_seq + 1} must be a JSON object.")
            if record.get("seq") != expected_seq:
                raise ValueError(f"sequence gap at audit line {expected_seq + 1}.")
            if record.get("prev_hash") != expected_prev:
                raise ValueError(f"previous hash mismatch at audit line {expected_seq + 1}.")
            actual_hash = record.get("hash")
            if not isinstance(actual_hash, str) or actual_hash != self._hash_record(record):
                raise ValueError(f"hash mismatch at audit line {expected_seq + 1}.")
            expected_prev = actual_hash
            records.append(record)
        return records

    def log(
        self, action: str, user: str, additional_info: Any = None,
    ) -> dict[str, Any]:
        if not isinstance(action, str) or not action.strip():
            raise ValueError("action must be a non-empty string.")
        if not isinstance(user, str) or not user.strip():
            raise ValueError("user must be a non-empty string.")
        lock_path = self.log_file.with_name(self.log_file.name + ".lock")
        try:
            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RuntimeError("Audit lock exists; inspect it and fail closed rather than deleting it blindly.") from exc
        try:
            os.write(lock_fd, f"pid={os.getpid()} token={uuid.uuid4().hex}\n".encode("ascii"))
            os.fsync(lock_fd)
            records = self.verify_chain()
            previous = records[-1]["hash"] if records else ZERO_HASH
            record: dict[str, Any] = {
                "seq": len(records),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "action": action.strip(),
                "user": user.strip(),
                "additional_info": additional_info,
                "prev_hash": previous,
            }
            record["hash"] = self._hash_record(record)
            encoded = self._canonical(record) + b"\n"
            fd = os.open(str(self.log_file), os.O_WRONLY | os.O_APPEND)
            try:
                with os.fdopen(fd, "ab") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
            except Exception:
                raise
            return record
        finally:
            os.close(lock_fd)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
