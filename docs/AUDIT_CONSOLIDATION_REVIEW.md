# V91 Audit Consolidation Review

Status: DOCUMENTED review; implementation consolidation is not yet complete.

## Compared implementations

### Agathon: `src/v91/audit.py`

- Persistent JSONL append log; sequence, previous hash and SHA-256 chain are verified.
- Uses a lock file and fails closed when a lock already exists.
- Creates a missing log file during logger initialization.
- Records use the schema `seq`, `user`, `additional_info`, `prev_hash`.
- Verification currently checks sequence, previous hash and record hash, but does not validate a strict UTC timestamp format or reject a symlink path explicitly.
- Existing data is not silently reset or migrated.

### V91 Audit Ledger: `v91_audit_ledger.py`

- Persistent JSONL append and read-only verification CLI.
- Uses a lock file, rejects symlink ledger paths, rejects blank lines and non-object records, validates UTC timestamp syntax and calendar values, checks sequence, previous hash and SHA-256 hash.
- Rejects non-JSON values such as NaN/Infinity before writing.
- Records use the different schema `sequence`, `actor`, `data`, `previous_hash`.
- Verification of a missing file reports `VALID_EMPTY` without creating it; append is an explicit separate operation.
- The ledger warns that a hash chain is not WORM storage and does not prove authorship, event truth or trusted time.

### Agathon: `src/v91/audit_deep.py`

- Separate in-memory hash chain and Ed25519 signing/verification.
- Not persistent; a new key is generated at object creation and is not saved.
- Must not be presented as a replacement for a persistent audit log. A valid signature proves verification against a public key, not that the signed event is true.

## Important differences / potential gaps

1. The two persistent loggers overlap in purpose but are not drop-in compatible: their record field names and verification return types differ.
2. The standalone ledger has stricter timestamp and path validation. These checks should be preserved in any consolidation.
3. Agathon's logger exposes an existing Python API used by its tests. Replacing it outright risks breaking callers.
4. The standalone ledger offers an explicit verify/append CLI; Agathon currently exposes a Python logger API. Preserve both use cases if consolidated.
5. Both rely on local files and hash chains. Neither alone provides WORM immutability, independent time witnessing, external identity assurance, or proof of event truth.
6. Lock files intentionally fail closed. Stale-lock recovery must remain a manual, evidence-based operation; do not auto-delete locks.

## Recommended sustainable target

- Keep Agathon as the maintained home for V91 audit code.
- Add the stricter standalone ledger capability inside Agathon as a separately named module first, with its tests and CLI behavior preserved.
- Add compatibility tests before deciding whether to deprecate `HashChainAuditLogger`; do not silently change its record schema or return values.
- Run CI and review the resulting behavior before merging.
- Only after successful verification, mark `v91-audit-ledger` as superseded and retain its history/readme as a migration reference. Do not delete or archive it before equivalence is demonstrated.
- Keep `AuditDeep` separate until durable key storage and a clear trust model exist; do not claim persistent signing or production-grade evidence.

## V91 evidence status

- DOCUMENTED: comparison above, based on the current default-branch source and tests.
- NOT YET IMPLEMENTED: code consolidation or migration.
- NOT YET VERIFIED: full cross-implementation compatibility, CI result for this proposed consolidation, production/WORM behavior, external trusted time, persistent signing-key handling.

Claim != evidence. No production or autonomous operation is asserted by this review.
