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
