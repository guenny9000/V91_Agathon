import hashlib
import json
import os
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timezone

class AuditLogger:
    def __init__(self, log_file):
        self.log_file = log_file
        if not os.path.exists(log_file):
            with open(log_file, 'w') as f:
                f.write('[]')  # Initialize with an empty JSON array

    def log(self, action, user, additional_info=None):
        timestamp = datetime.utcnow().isoformat()
        entry = {
            'timestamp': timestamp,
            'action': action,
            'user': user,
            'additional_info': additional_info
        }
        entry_hash = self.calculate_hash(entry)
        log_entry = {**entry, 'hash': entry_hash}
        
        self.append_log(log_entry)

    def calculate_hash(self, entry):
        entry_json = json.dumps(entry, sort_keys=True)
        return hashlib.sha256(entry_json.encode('utf-8')).hexdigest()

    def append_log(self, log_entry):
        with open(self.log_file, 'r+') as f:
            logs = json.load(f)
            logs.append(log_entry)
            f.seek(0)
            json.dump(logs, f, indent=4)
            f.truncate()

# Usage example
# logger = AuditLogger('audit_log.json')
# logger.log('UserLogin', 'guenny9000', 'Logged in successfully')


class HashChainAuditLogger:
    """Single-writer SHA-256-linked JSONL audit log.

    A normal file is not WORM storage. The hash chain detects changes only when
    verified; it does not prove event truth, trusted time, or author identity.
    """

    ZERO_HASH = "0" * 64
    REQUIRED_KEYS = {"seq", "timestamp", "action", "user", "additional_info", "prev_hash", "hash"}

    def __init__(self, log_file):
        from pathlib import Path

        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        if self.log_file.exists():
            self.verify_chain()

    @staticmethod
    def _canonical_json(value):
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    @classmethod
    def _hash_core(cls, core):
        return hashlib.sha256(cls._canonical_json(core).encode("utf-8")).hexdigest()

    @contextmanager
    def _exclusive_lock(self):
        lock_path = self.log_file.with_name(self.log_file.name + ".lock")
        token = secrets.token_hex(24)
        payload = json.dumps({
            "pid": os.getpid(),
            "created_at_unix": time.time(),
            "token": token,
        }, sort_keys=True) + "\\n"
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        try:
            fd = os.open(str(lock_path), flags, 0o600)
        except FileExistsError as exc:
            raise ValueError("audit lock exists; verify its owner before retrying") from exc
        except OSError as exc:
            raise ValueError(f"cannot create audit lock: {exc}") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            try:
                data = json.loads(lock_path.read_text(encoding="utf-8"))
                if data.get("token") == token:
                    lock_path.unlink()
            except (OSError, ValueError, AttributeError):
                pass
            raise ValueError(f"cannot write audit lock: {exc}") from exc
        try:
            yield
        finally:
            try:
                data = json.loads(lock_path.read_text(encoding="utf-8"))
                if data.get("token") == token and data.get("pid") == os.getpid():
                    lock_path.unlink()
            except (OSError, ValueError, AttributeError):
                # Do not delete a lock when ownership can no longer be proven.
                pass

    def verify_chain(self):
        """Return parsed records or raise ValueError on corruption."""
        if not self.log_file.exists():
            return []
        raw = self.log_file.read_text(encoding="utf-8")
        if not raw:
            raise ValueError("audit file exists but is empty; refusing to treat it as a valid chain")

        records = []
        expected_previous = self.ZERO_HASH
        expected_seq = 0
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                raise ValueError(f"blank line at line {line_number}")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at line {line_number}") from exc

            if not isinstance(record, dict) or set(record) != self.REQUIRED_KEYS:
                raise ValueError(f"invalid record schema at line {line_number}")
            seq = record.get("seq")
            if isinstance(seq, bool) or not isinstance(seq, int) or seq != expected_seq:
                raise ValueError(f"sequence gap at line {line_number}")
            timestamp = record.get("timestamp")
            if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
                raise ValueError(f"invalid UTC timestamp at line {line_number}")
            try:
                datetime.fromisoformat(timestamp[:-1] + "+00:00")
            except ValueError as exc:
                raise ValueError(f"invalid UTC timestamp at line {line_number}") from exc
            for key in ("action", "user"):
                if not isinstance(record.get(key), str) or not record[key].strip():
                    raise ValueError(f"invalid {key} at line {line_number}")
            if record.get("prev_hash") != expected_previous:
                raise ValueError(f"previous-hash mismatch at line {line_number}")

            stored_hash = record.get("hash")
            if not isinstance(stored_hash, str) or len(stored_hash) != 64 or any(ch not in "0123456789abcdef" for ch in stored_hash):
                raise ValueError(f"invalid hash at line {line_number}")
            core = {key: value for key, value in record.items() if key != "hash"}
            try:
                calculated_hash = self._hash_core(core)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid JSON value at line {line_number}") from exc
            if calculated_hash != stored_hash:
                raise ValueError(f"hash mismatch at line {line_number}")

            records.append(record)
            expected_previous = stored_hash
            expected_seq += 1
        return records

    def log(self, action, user, additional_info=None):
        """Append one record after validating the chain under an exclusive lock."""
        if not isinstance(action, str) or not action.strip():
            raise ValueError("action must be a non-empty string")
        if not isinstance(user, str) or not user.strip():
            raise ValueError("user must be a non-empty string")
        # Validate the event before touching the ledger or creating a lock.
        self._canonical_json(additional_info)

        with self._exclusive_lock():
            records = self.verify_chain()
            previous_hash = records[-1]["hash"] if records else self.ZERO_HASH
            core = {
                "seq": len(records),
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "action": action.strip(),
                "user": user.strip(),
                "additional_info": additional_info,
                "prev_hash": previous_hash,
            }
            record = {**core, "hash": self._hash_core(core)}
            serialized = self._canonical_json(record) + "\\n"
            try:
                with self.log_file.open("a", encoding="utf-8", newline="\\n") as handle:
                    handle.write(serialized)
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as exc:
                # Partial writes are not repaired automatically; verification must precede retry.
                raise ValueError(f"audit append failed; verify chain before retry: {exc}") from exc
        return record
