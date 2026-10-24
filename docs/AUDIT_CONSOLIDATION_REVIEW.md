# V91 Audit Consolidation Review

Status: IMPLEMENTED ON REVIEW BRANCH; CI and merge are still pending.

## Compared implementations

### Existing Agathon API: `src/v91/audit.py`

- Persistent JSONL append log; sequence, previous hash and SHA-256 chain are verified.
- Uses a lock file and fails closed when a lock already exists.
- Existing record schema is `seq`, `user`, `additional_info`, `prev_hash` and remains unchanged for compatibility.
- Current verification does not validate a strict UTC timestamp format or reject a symlink path explicitly.

### Former standalone implementation: `v91_audit_ledger.py`

- Persistent JSONL append and read-only verification CLI.
- Rejects symlink ledger paths, blank lines and non-object records; validates UTC timestamp syntax and calendar values; checks sequence, previous hash and SHA-256 hash.
- Rejects non-JSON values such as NaN/Infinity before writing.
- Uses a distinct schema: `sequence`, `actor`, `data`, `previous_hash`.
- Verifying a missing file reports `VALID_EMPTY` without creating it; append is explicit.

### New additive Agathon implementation: `src/v91/ledger.py`

- Ported the stricter standalone behavior into Agathon without replacing the existing logger or changing its stored record schema.
- Added tests for append/verify, read-only missing-file verification, tampering, legacy data, sequence gaps, invalid JSON values, existing locks, symlink rejection and invalid timestamps.
- Exposes `LedgerError`, `append_ledger_record`, and `verify_ledger` from the package API.
- CLI entry point: `python -m v91.ledger --ledger <path> verify` or explicit `append`.
- Both formats must remain in separate files. No automatic migration or rewriting is performed.

### Agathon: `src/v91/audit_deep.py`

- Separate in-memory hash chain and Ed25519 signing/verification.
- A new key is generated at object creation and is not saved. It is not a persistent audit log.

## Safety and compatibility decisions

1. Preserve `HashChainAuditLogger` and its existing file format for callers already using it.
2. Add the stricter ledger as a separate module, avoiding a silent schema/API break.
3. Keep missing-file verification read-only; append is an explicit action.
4. Reject malformed or tampered history and never silently repair, reset, or migrate it.
5. Do not auto-delete lock files; inspect them before any manual recovery.
6. Keep `AuditDeep` separate until persistent key storage and a trust model are designed.
7. Neither local hash chain provides WORM immutability, independent trusted time, proof of event truth, or external identity assurance.

## Evidence status

- DOCUMENTED: source comparison and compatibility decision.
- IMPLEMENTED: additive `ledger` module, tests, public API exports and README on this review branch.
- PENDING: GitHub Actions results and review of any failures.
- NOT CLAIMED: production deployment, persistent signing keys, WORM storage, external trusted time or autonomous operation.

Claim != evidence. Do not retire the standalone repository until CI is green and the implementation has been reviewed. Retain its Git history as a migration reference.
