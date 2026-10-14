# V91-Agathon

V91-Agathon contains small, testable governance helpers. The current package branch provides a local demonstration; it is not a production control plane.

## Installation

From the repository root:

```bash
python -m pip install -e .
python -m pip install pytest
```

The legacy `requirements.txt` contains Flask, requests, and SQLAlchemy, but the small `v91` package and demo do not require external services.

## Run the offline demo

```bash
python examples/simple_pipeline.py
```

The example uses synthetic fixture data and records an in-memory assessment and resource allocation. It does not read hardware metrics, contact a network service, write an audit ledger, train a model, or perform external actions. Its output is a demonstration, not proof of live V91 operation.

## Tests

```bash
python -m pytest -q
```

The GitHub Actions workflow checks the package and tests on the configured Python versions.


## Audit components and current limits

- `HashChainAuditLogger` writes SHA-256-linked JSONL records and validates existing records before appending. It is a single-writer helper; the JSONL file is **not WORM** and can still be modified or deleted outside the program.
- The legacy `AuditLogger` writes a JSON array by rewriting the file; it is not an append-only hash chain. Do not treat it as immutable evidence.
- `AuditDeep` provides an in-memory previous-hash chain and Ed25519 signing using the declared `cryptography` dependency. Its chain is not persistent and its public key must be bound to a trusted identity out of band.
- Semgrep policy generation and multi-node lifecycle management are explicit placeholders. Calling those methods raises `NotImplementedError`; no scan, policy generation, network connection, or remote action is claimed.

These limitations are intentional and visible rather than silent no-op behavior.
