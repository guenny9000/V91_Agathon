"""Tests for voluntary peer coordination (issue #24 stage 2).

The registry logic runs with a deterministic HMAC stub verifier so it is
verifiable without the cryptography package; the real Ed25519 path is
additionally exercised whenever cryptography is installed (CI always
installs it as a declared dependency).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import inspect
from datetime import datetime, timezone

import v91.peer_coordination as pc
from v91.peer_coordination import (
    ACCEPTED,
    ALLOWED_SCOPES,
    REJECTED_EXPIRED,
    REJECTED_INVALID_SIGNATURE,
    REJECTED_ISOLATED,
    REJECTED_MALFORMED,
    REJECTED_REPLAY,
    REJECTED_REVOKED,
    REJECTED_SCHEMA,
    REJECTED_SCOPE_ESCALATION,
    REJECTED_UNKNOWN_PEER,
    InMemoryTransport,
    PeerCoordinationError,
    PeerRegistry,
    build_envelope,
    canonical_payload,
    sign_envelope,
)

NOW = datetime(2026, 11, 28, 7, 0, tzinfo=timezone.utc)
ISSUED = "2026-11-28T06:00:00+00:00"
EXPIRES = "2026-11-28T09:00:00+00:00"


class StaticVerifier:
    """Deterministic stand-in so registry logic is testable without crypto.

    pub maps a peer's registered key string to a shared secret; a message
    signature is HMAC-SHA256 over the canonical payload. NOT a production
    verifier: a shared secret cannot prove a single signer.
    """

    def __init__(self) -> None:
        self.secrets: dict[str, bytes] = {}

    def register(self, peer_id: str, secret: bytes) -> str:
        public = base64.b64encode(f"pub:{peer_id}".encode("utf-8")).decode("ascii")
        self.secrets[public] = secret
        return public

    def verify(self, public_key_b64: str, payload: bytes, signature_b64: str) -> bool:
        secret = self.secrets.get(public_key_b64)
        if secret is None:
            return False
        expected = base64.b64encode(hmac.new(secret, payload, hashlib.sha256).digest()).decode("ascii")
        return hmac.compare_digest(expected, signature_b64)


def _make_registry() -> tuple[PeerRegistry, StaticVerifier]:
    verifier = StaticVerifier()
    registry = PeerRegistry(verifier, now_provider=lambda: NOW)
    return registry, verifier


def _envelope(peer_id: str, secret: bytes, seq: int, *, type: str = "heartbeat",
             scopes: list[str] | None = None, body: str = "ping",
             expires_at: str = EXPIRES) -> dict:
    envelope = build_envelope(
        type=type,
        peer_id=peer_id,
        seq=seq,
        issued_at=ISSUED,
        expires_at=expires_at,
        scopes=scopes or [type],
        body=body,
    )
    signer = lambda payload: base64.b64encode(
        hmac.new(secret, payload, hashlib.sha256).digest()
    ).decode("ascii")
    return sign_envelope(envelope, signer)


def _register_peer(registry: PeerRegistry, verifier: StaticVerifier, peer_id: str,
                   scopes: list[str]) -> None:
    public = verifier.register(peer_id, b"secret-" + peer_id.encode("utf-8"))
    registry.register(peer_id, public, scopes)


def test_registration_is_explicit_and_scope_bounded():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat", "status_report"])
    assert registry.peer_status("node-a") == "ACTIVE"
    # Unknown or empty scopes are rejected; no wildcard scope exists.
    for bad in ([], ["heartbeat", "root"], ["*"], "heartbeat"):
        try:
            registry.register("node-b", verifier.register("node-b", b"x"), bad)
            raised = False
        except PeerCoordinationError:
            raised = True
        assert raised, f"scopes {bad!r} must be rejected"
    # Duplicate registration is rejected (no silent key replacement).
    try:
        registry.register("node-a", "another-key", ["heartbeat"])
        raised = False
    except PeerCoordinationError:
        raised = True
    assert raised


def test_accepted_roundtrip_and_monotonic_sequence():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    secret = b"secret-node-a"
    first = registry.verify(_envelope("node-a", secret, 1))
    assert first.status == ACCEPTED and first.accepted
    assert registry.last_seq("node-a") == 1
    second = registry.verify(_envelope("node-a", secret, 2))
    assert second.status == ACCEPTED
    assert registry.last_seq("node-a") == 2


def test_replay_and_regression_are_rejected():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    secret = b"secret-node-a"
    assert registry.verify(_envelope("node-a", secret, 5)).status == ACCEPTED
    same_again = registry.verify(_envelope("node-a", secret, 5))
    assert same_again.status == REJECTED_REPLAY
    lower = registry.verify(_envelope("node-a", secret, 4))
    assert lower.status == REJECTED_REPLAY
    assert registry.last_seq("node-a") == 5  # rejection did not move the counter


def test_tampered_payload_is_rejected_as_invalid_signature():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    envelope = _envelope("node-a", b"secret-node-a", 1)
    envelope["body"] = "tampered"  # breaks the signature binding
    verdict = registry.verify(envelope)
    assert verdict.status == REJECTED_INVALID_SIGNATURE
    assert registry.last_seq("node-a") == 0


def test_unknown_peer_and_schema_mismatch_are_rejected():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    unknown = registry.verify(_envelope("node-x", b"secret-node-x", 1))
    assert unknown.status == REJECTED_UNKNOWN_PEER
    wrong_schema = _envelope("node-a", b"secret-node-a", 1)
    wrong_schema["schema"] = "some.other.schema.v1"
    assert registry.verify(wrong_schema).status == REJECTED_SCHEMA
    # Signature was never consulted, so the counter must not move.
    assert registry.last_seq("node-a") == 0


def test_expired_message_is_rejected():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    expired = _envelope(
        "node-a", b"secret-node-a", 1, expires_at="2026-11-28T06:30:00+00:00"
    )
    verdict = registry.verify(expired)
    assert verdict.status == REJECTED_EXPIRED
    assert registry.last_seq("node-a") == 0


def test_revocation_survives_and_blocks_new_messages():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    assert registry.verify(_envelope("node-a", b"secret-node-a", 1)).status == ACCEPTED
    registry.revoke("node-a", reason="operator decision")
    assert registry.peer_status("node-a") == "REVOKED"
    verdict = registry.verify(_envelope("node-a", b"secret-node-a", 2))
    assert verdict.status == REJECTED_REVOKED
    # Re-registration under the same identity is refused.
    try:
        registry.register("node-a", "new-key", ["heartbeat"])
        raised = False
    except PeerCoordinationError:
        raised = True
    assert raised


def test_scope_escalation_is_rejected():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    secret = b"secret-node-a"
    unregistered_type = registry.verify(_envelope("node-a", secret, 1, type="task_offer"))
    assert unregistered_type.status == REJECTED_SCOPE_ESCALATION
    claimed_scopes = registry.verify(
        _envelope("node-a", secret, 1, scopes=["heartbeat", "status_report"])
    )
    assert claimed_scopes.status == REJECTED_SCOPE_ESCALATION
    assert registry.last_seq("node-a") == 0


def test_malformed_envelopes_are_rejected_without_raising():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    good = _envelope("node-a", b"secret-node-a", 1)

    def mutated(**changes):
        envelope = dict(good)
        for key, value in changes.items():
            if value is None:
                envelope.pop(key, None)
            else:
                envelope[key] = value
        return envelope

    cases = [
        "not-a-dict",
        mutated(seq=None),
        mutated(seq=True),  # bool is an int subclass; must still be rejected
        mutated(seq=0),
        mutated(seq="2"),
        mutated(peer_id=""),
        mutated(scopes=None),
        mutated(scopes=[]),
        mutated(scopes=["heartbeat", "not-a-scope"]),
        mutated(type="not-a-type"),
        mutated(body="x" * (pc.MAX_BODY_CHARS + 1)),
        mutated(body=42),
        mutated(issued_at="2026-11-28 06:00"),  # naive timestamp, no UTC offset
        mutated(expires_at="2026-11-28T06:00:00"),  # naive, no UTC offset
        mutated(signature=""),
        mutated(schema=None),
    ]
    for case in cases:
        verdict = registry.verify(case)
        assert verdict.status == REJECTED_MALFORMED, f"case {case!r} -> {verdict.status}"
    assert registry.last_seq("node-a") == 0


def test_broken_verifier_adapter_fails_closed():
    class ExplodingVerifier:
        def verify(self, public_key_b64, payload, signature_b64):
            raise RuntimeError("adapter bug")

    registry = PeerRegistry(ExplodingVerifier(), now_provider=lambda: NOW)
    registry.register("node-a", "pub", ["heartbeat"])
    verdict = registry.verify(_envelope("node-a", b"secret-node-a", 1))
    assert verdict.status == REJECTED_INVALID_SIGNATURE
    assert "adapter bug" in verdict.reason
    assert registry.last_seq("node-a") == 0


def test_peer_failure_isolation_does_not_block_other_peers():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    _register_peer(registry, verifier, "node-b", ["heartbeat"])
    assert registry.record_peer_failure("node-a", "heartbeat_timeout") == "STALE"
    assert registry.record_peer_failure("node-a", "heartbeat_timeout") == "STALE"
    assert registry.record_peer_failure("node-a", "heartbeat_timeout") == "ISOLATED"
    assert registry.peer_status("node-a") == "ISOLATED"
    isolated = registry.verify(_envelope("node-a", b"secret-node-a", 1))
    assert isolated.status == REJECTED_ISOLATED
    # Local work continues: the healthy peer is unaffected.
    healthy = registry.verify(_envelope("node-b", b"secret-node-b", 1))
    assert healthy.status == ACCEPTED
    # Unknown peers are reported honestly, never invented.
    assert registry.record_peer_failure("node-ghost", "x") == "UNKNOWN"
    assert registry.peer_status("node-ghost") == "UNKNOWN"
    assert registry.failure_log("node-a")[-1][0] == "heartbeat_timeout"


def test_stale_peer_recovers_only_with_fresh_valid_evidence():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    registry.record_peer_failure("node-a", "heartbeat_timeout")
    assert registry.peer_status("node-a") == "STALE"
    verdict = registry.verify(_envelope("node-a", b"secret-node-a", 1))
    assert verdict.status == ACCEPTED
    assert registry.peer_status("node-a") == "ACTIVE"
    # A revoked peer does NOT recover through messages.
    registry.revoke("node-a")
    assert registry.verify(_envelope("node-a", b"secret-node-a", 2)).status == REJECTED_REVOKED


def test_identity_expiry_blocks_messages_until_explicit_reregistration():
    registry, verifier = _make_registry()
    _register_peer(registry, verifier, "node-a", ["heartbeat"])
    registry.mark_expired("node-a")
    assert registry.peer_status("node-a") == "EXPIRED"
    verdict = registry.verify(_envelope("node-a", b"secret-node-a", 1))
    assert verdict.status == REJECTED_EXPIRED
    registry.unregister("node-a")
    public = verifier.register("node-a", b"secret-node-a")
    registry.register("node-a", public, ["heartbeat"])
    assert registry.verify(_envelope("node-a", b"secret-node-a", 1)).status == ACCEPTED


def test_canonical_payload_is_deterministic_and_signature_free():
    envelope = build_envelope(
        type="heartbeat", peer_id="node-a", seq=1, issued_at=ISSUED,
        expires_at=EXPIRES, scopes=["heartbeat"], body="ping",
    )
    envelope["signature"] = "ignored-for-payload"
    reordered = dict(reversed(list(envelope.items())))
    assert canonical_payload(envelope) == canonical_payload(reordered)
    serialized = canonical_payload(envelope).decode("ascii")
    assert "signature" not in serialized
    assert serialized.index("body") < serialized.index("expires_at")  # sorted keys


def test_in_memory_transport_preserves_envelopes_and_is_not_a_network():
    transport = InMemoryTransport()
    try:
        transport.receive()
        raised = False
    except PeerCoordinationError:
        raised = True
    assert raised
    envelope = _envelope("node-a", b"secret-node-a", 1)
    receipt = transport.deliver(envelope)
    assert receipt.startswith("inmemory-")
    received = transport.receive()
    assert received == envelope
    envelope["body"] = "mutated-after-delivery"
    assert received["body"] == "ping"  # deep copy, no aliasing


def test_module_contains_no_network_or_code_execution_primitives():
    source = inspect.getsource(pc)
    for forbidden in (
        "import socket",
        "import subprocess",
        "urllib",
        "requests",
        "eval(",
        "exec(",
        "__import__",
    ):
        assert forbidden not in source, f"forbidden primitive in module: {forbidden}"


def test_allowed_scopes_stay_minimal():
    assert ALLOWED_SCOPES == frozenset(
        {"hello", "heartbeat", "status_report", "task_offer", "task_result"}
    )
    assert "root" not in ALLOWED_SCOPES and "*" not in ALLOWED_SCOPES


def test_real_ed25519_path_when_cryptography_is_available():
    try:
        import cryptography  # noqa: F401  (skip locally, CI installs it)
        from v91.peer_coordination import Ed25519Verifier, PeerKeyPair
    except Exception:
        print("NOTE: real Ed25519 test skipped locally; CI installs cryptography")
        return
    keypair = PeerKeyPair.generate()
    public = keypair.public_key_b64
    registry = PeerRegistry(Ed25519Verifier(), now_provider=lambda: NOW)
    registry.register("node-a", public, ["heartbeat"])
    envelope = build_envelope(
        type="heartbeat", peer_id="node-a", seq=1, issued_at=ISSUED,
        expires_at=EXPIRES, scopes=["heartbeat"], body="real-ed25519",
    )
    signed = sign_envelope(envelope, keypair.sign)
    verdict = registry.verify(signed)
    assert verdict.status == ACCEPTED, verdict
    tampered = dict(signed)
    tampered["body"] = "forged"
    assert registry.verify(tampered).status == REJECTED_INVALID_SIGNATURE
    other_key = PeerKeyPair.generate()
    wrong_key = sign_envelope(envelope, other_key.sign)
    # Signature by a different key over the same payload must fail.
    assert registry.verify(wrong_key).status == REJECTED_INVALID_SIGNATURE
