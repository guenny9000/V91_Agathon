# V91 Agathon

V91 Agathon provides local audit primitives and explicitly bounded learning-component placeholders. It is not a distributed control plane or a production ledger service.

## Install

Python 3.10 or newer is required.

```powershell
python -m pip install -e .
python -m pip install pytest
```

The package uses the `src/v91` layout. The declared `cryptography` dependency supplies Ed25519 signing.

## Run the local demonstration

```powershell
python examples/simple_pipeline.py
```

The demonstration writes only to a temporary directory and uses synthetic demo data. It does not read hardware sensors, access the network, or modify a production ledger.

## Tests

```powershell
python -m pytest -q
```

GitHub Actions runs source compilation and the test suite on pushes and pull requests to `main`.

## Implemented behavior

- `HashChainAuditLogger`: existing append-only JSONL API with sequence and previous-hash checks, canonical SHA-256 records, and fail-closed behavior. Its existing record schema is preserved.
- `ledger` module: stricter local JSONL ledger with UTC timestamp validation, symlink rejection, sequence/hash checks, explicit append and read-only verification. Run `python -m v91.ledger --ledger .\\runtime\\audit.jsonl verify` to verify without changing the file. Append is explicit: `python -m v91.ledger --ledger .\\runtime\\audit.jsonl append --action TASK_STARTED --actor local-worker --data-json '{\"purpose\":\"verify input file\"}'`.
- `AuditDeep`: in-memory hash-chain verification and Ed25519 sign/verify helpers; signing keys are not persisted.
- `V91Runtime.process_data`: returns the input unchanged; no hidden transformation is performed.
- `SemgrepIntegrator.available`: checks whether the optional Semgrep package is importable.

The new `ledger` module is additive: it does not silently change or migrate records written by `HashChainAuditLogger`. The two log formats are distinct and must not be mixed in one file.

## Explicitly not implemented

- Semgrep scanning and policy generation.
- Remote/multi-node orchestration or lifecycle management.
- Persistent signing-key management, independent time witness, WORM storage, or production ledger service.
- Hardware telemetry, model training, or autonomous production actions.

These limitations raise explicit `NotImplementedError` where an operation is not implemented; the package does not claim those actions occurred.

## Evidence boundaries

A hash chain can make edits detectable when verified, but does not by itself guarantee immutability, authorship, event truth, or trustworthy timestamps. Ed25519 verifies a signature against the corresponding public key; it does not prove that the signed statement is true. No production or autonomous operation is implied by these local primitives.
