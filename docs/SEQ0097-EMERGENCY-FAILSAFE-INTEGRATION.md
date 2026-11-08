# SEQ:0097 — Agathon integration contract

**Status: DESIGN / NOT DEPLOYED.** This document defines how Agathon's local audit primitives may support V91 emergency fail-safe workflows. It does not claim that network isolation, XDP/eBPF, WORM retention or production signing is implemented.

## Required boundaries

- Keep the existing `HashChainAuditLogger` schema and the stricter `v91.ledger` schema separate. Never auto-migrate, rewrite or merge their files.
- Preserve read-only verification. Appending is an explicit operation.
- Detection, anomaly scores and model outputs are evidence inputs only; none grants execution authority.
- Emergency actions must be delegated to a separately permissioned, host-local adapter. Agathon's audit package must not silently gain kernel/network privileges.
- Record intent, authorization, scope, policy digest, adapter result, rollback identifier and independent post-check as separate fields/events.
- If the audit sink fails, do not fabricate a successful audit record. The enforcement adapter must follow its configured safe failure policy and report the missing evidence.
- A hash chain is tamper-evident, not WORM; Ed25519 validates signed bytes against a public key, not event truth. Persistent key storage, rotation, revocation and external time trust remain separate capabilities.

## State and evidence contract

Use the states `ALERT`, `ARMED`, `ISOLATION_PENDING`, `ISOLATED`, `RECOVERY_PENDING`, `RESTORED` and `REVIEW_REQUIRED`. A state transition is not proof that a host action happened. Record `UNKNOWN` when the adapter cannot independently query effective state.

## Test requirements

Add tests for duplicate/replayed event IDs, sequence gaps, tampered records, invalid timestamps, unavailable audit storage, authorization expiry, concurrent transitions and rollback-result recording. Adapter integration tests belong in disposable network namespaces or equivalent isolated fixtures; no live host firewall or production network is modified.

## Cross-repository contract

The normative architecture and acceptance matrix live in `v91-core-system/docs/V91-EMERGENCY-FAILSAFE-IMPLEMENTATION-PLAN.md`. Agathon supplies auditable local records only. No <0.1 ms, active, WORM or production claim is permitted without exact revision and reproducible evidence.
