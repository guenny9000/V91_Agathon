"""Small local-only demonstration; uses a temporary directory and synthetic demo records."""
from __future__ import annotations

import tempfile
from pathlib import Path

from v91.audit import HashChainAuditLogger
from v91.audit_deep import AuditDeep


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v91-agathon-demo-") as temporary:
        path = Path(temporary) / "audit.jsonl"
        logger = HashChainAuditLogger(path)
        logger.log("DEMO_RECORD", "local-demo", {"kind": "SYNTHETIC_EXAMPLE"})
        verified = logger.verify_chain()
        audit = AuditDeep()
        digest = audit.update_chain({"kind": "SYNTHETIC_EXAMPLE", "purpose": "demo"})
        signature = audit.sign_data({"digest": digest})
        ok = audit.verify_chain() and audit.verify_signature({"digest": digest}, signature)
        if len(verified) != 1 or not ok:
            raise SystemExit("DEMO_FAILED")
        print("DEMO_ONLY: local hash chain verified; Ed25519 signature verified.")
        print("No hardware, network, external service, or production ledger was accessed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
