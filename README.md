# V91 Agathon

V91 Agathon currently provides small audit primitives and explicit learning-component placeholders. It is not a distributed control plane or a production ledger service.

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

The demonstration writes only to a temporary directory and uses explicitly synthetic demo data. It does not read hardware sensors, access the network, or modify a production ledger.

## Tests

```powershell
python -m pytest -q
```

GitHub Actions runs source compilation and the test suite on pushes and pull requests to `main`.

## Implemented behavior

- `HashChainAuditLogger`: append-only JSONL writes, sequence and previous-hash checks, canonical SHA-256 records, and fail-closed behavior when existing data is malformed or tampered with.
- `AuditDeep`: in-memory hash-chain verification and Ed25519 sign/verify helpers.
- `V91Runtime.process_data`: explicitly returns input unchanged; no hidden transformation is performed.
- `SemgrepIntegrator.available`: checks whether the optional Semgrep package is importable.

## Explicitly not implemented

- Semgrep scanning and policy generation.
- Remote/multi-node orchestration or lifecycle management.
- A persistent signing-key store, independent time witness, WORM storage, or production ledger service.
- Hardware telemetry, model training, or autonomous production actions.

These limitations raise explicit `NotImplementedError` where an operation is not implemented; the package does not claim those actions occurred.

## Evidence boundaries

A hash chain can make edits detectable when verified, but does not by itself guarantee immutability, authorship, event truth, or trustworthy timestamps. Ed25519 verifies a signature against the corresponding public key; it does not prove that the signed statement is true. The current `AuditDeep` key is generated in memory and is not persisted.
