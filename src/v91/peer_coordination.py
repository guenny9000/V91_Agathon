"""Voluntary, transport-neutral peer coordination with signed identity.

Implements Agathon issue #24 stage 2: explicit peer registration, signed
messages, message expiry, revocation, replay protection, minimal scopes,
and per-peer failure isolation. The local registry never opens a socket,
never discovers peers, and never executes code from a message.

Honest limits (binding):
- SIGNATURE != TRUTH: a valid signature proves key possession, not that
  the signed content is true.
- VERIFICATION != AUTHORIZATION: an accepted message is authentic and
  current; it grants no rights beyond the scopes fixed at registration
  (no automatic privilege escalation).
- ACCEPTED != EXECUTED: verifying a message performs no action; acting on
  a task_offer or task_result remains a separate, explicitly authorized
  decision by the caller.
- No real multi-node operation is claimed here; a network transport
  adapter and real peers are stage-3 work and remain NICHT_GEPRUEFT
  (unknown) until measured on real hardware.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from .ledger import LedgerError, canonical_bytes

MESSAGE_SCHEMA = "v91.agathon.peer_message.v1"
MESSAGE_TYPES = frozenset(
    {"hello", "heartbeat", "status_report", "task_offer", "task_result",
     "control_request"}
)
ALLOWED_SCOPES = frozenset(MESSAGE_TYPES)
MAX_BODY_CHARS = 2048

ACCEPTED = "ACCEPTED"
REJECTED_MALFORMED = "REJECTED_MALFORMED"
REJECTED_SCHEMA = "REJECTED_SCHEMA"
REJECTED_UNKNOWN_PEER = "REJECTED_UNKNOWN_PEER"
REJECTED_REVOKED = "REJECTED_REVOKED"
REJECTED_ISOLATED = "REJECTED_ISOLATED"
REJECTED_EXPIRED = "REJECTED_EXPIRED"
REJECTED_SCOPE_ESCALATION = "REJECTED_SCOPE_ESCALATION"
REJECTED_INVALID_SIGNATURE = "REJECTED_INVALID_SIGNATURE"
REJECTED_REPLAY = "REJECTED_REPLAY"

_PEER_ACTIVE = "ACTIVE"
_PEER_STALE = "STALE"
_PEER_ISOLATED = "ISOLATED"
_PEER_REVOKED = "REVOKED"
_PEER_EXPIRED = "EXPIRED"
_PEER_UNKNOWN = "UNKNOWN"

STATES = frozenset(
    {
        _PEER_ACTIVE,
        _PEER_STALE,
        _PEER_ISOLATED,
        _PEER_REVOKED,
        _PEER_EXPIRED,
        _PEER_UNKNOWN,
    }
)


class PeerCoordinationError(RuntimeError):
    """Registration input or key material is invalid; fail-closed."""


@dataclass(frozen=True)
class Verdict:
    """Outcome of one envelope verification. Rejections carry a reason."""

    status: str
    peer_id: str
    seq: int | None
    reason: str

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED


def _parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise PeerCoordinationError(f"{field} must be an ISO-8601 string.")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise PeerCoordinationError(f"{field} is not ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise PeerCoordinationError(f"{field} must carry a UTC offset.")
    return parsed.astimezone(timezone.utc)


def _validate_envelope_fields(envelope: dict[str, Any]) -> None:
    """Raise PeerCoordinationError for structurally invalid envelopes."""
    required = (
        "schema",
        "type",
        "peer_id",
        "seq",
        "issued_at",
        "expires_at",
        "scopes",
        "body",
        "signature",
    )
    for key in required:
        if key not in envelope:
            raise PeerCoordinationError(f"missing field: {key}")
    if envelope["type"] not in MESSAGE_TYPES:
        raise PeerCoordinationError("unknown message type")
    if not isinstance(envelope["peer_id"], str) or not envelope["peer_id"].strip():
        raise PeerCoordinationError("peer_id must be a non-empty string")
    seq = envelope["seq"]
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        raise PeerCoordinationError("seq must be an integer >= 1")
    scopes = envelope["scopes"]
    if (
        not isinstance(scopes, list)
        or not scopes
        or any(not isinstance(scope, str) for scope in scopes)
        or not set(scopes).issubset(ALLOWED_SCOPES)
    ):
        raise PeerCoordinationError("scopes must be a non-empty subset of ALLOWED_SCOPES")
    body = envelope["body"]
    if not isinstance(body, str) or len(body) > MAX_BODY_CHARS:
        raise PeerCoordinationError(f"body must be a string of at most {MAX_BODY_CHARS} chars")
    if not isinstance(envelope["signature"], str):
        raise PeerCoordinationError("signature must be a string")
    _parse_utc(envelope["issued_at"], "issued_at")
    _parse_utc(envelope["expires_at"], "expires_at")


def build_envelope(
    *,
    type: str,
    peer_id: str,
    seq: int,
    issued_at: str,
    expires_at: str,
    scopes: list[str],
    body: str,
) -> dict[str, Any]:
    """Build an unsigned envelope. The caller adds envelope["signature"]."""
    envelope: dict[str, Any] = {
        "schema": MESSAGE_SCHEMA,
        "type": type,
        "peer_id": peer_id,
        "seq": seq,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "scopes": sorted(scopes),
        "body": body,
        "signature": "",
    }
    _validate_envelope_fields(envelope)
    return envelope


def canonical_payload(envelope: dict[str, Any]) -> bytes:
    """Deterministic signing bytes: the envelope minus its signature field."""
    payload = {key: value for key, value in envelope.items() if key != "signature"}
    try:
        return canonical_bytes(payload)
    except LedgerError as exc:
        raise PeerCoordinationError("envelope is not JSON-serializable") from exc


def sign_envelope(envelope: dict[str, Any], signer: Callable[[bytes], str]) -> dict[str, Any]:
    """Return a copy of the envelope with the signer's signature attached."""
    if envelope.get("signature"):
        raise PeerCoordinationError("envelope is already signed")
    signed = dict(envelope)
    signed["signature"] = signer(canonical_payload(envelope))
    if not signed["signature"]:
        raise PeerCoordinationError("signer produced an empty signature")
    return signed


class PeerKeyPair:
    """Ed25519 identity material for one peer. Fail-closed without cryptography.

    The private key never leaves this object; only the raw 32-byte public
    key (base64) is exported for registration.
    """

    def __init__(self, private_key: Any) -> None:
        self._private_key = private_key

    @classmethod
    def generate(cls) -> "PeerKeyPair":
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
        except ImportError as exc:
            raise PeerCoordinationError(
                "cryptography package unavailable; Ed25519 key generation is fail-closed"
            ) from exc
        return cls(Ed25519PrivateKey.generate())

    @property
    def public_key_b64(self) -> str:
        from cryptography.hazmat.primitives import serialization

        raw = self._private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return base64.b64encode(raw).decode("ascii")

    def sign(self, payload: bytes) -> str:
        signature = self._private_key.sign(payload)
        return base64.b64encode(signature).decode("ascii")


class Ed25519Verifier:
    """Verify Ed25519 signatures against a registered public key (base64).

    Returns False for any malformed input or mismatch; raises
    PeerCoordinationError only when the cryptography package itself is
    unavailable (fail-closed, never fail-open).
    """

    def verify(self, public_key_b64: str, payload: bytes, signature_b64: str) -> bool:
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )
            from cryptography.exceptions import InvalidSignature
        except ImportError as exc:
            raise PeerCoordinationError(
                "cryptography package unavailable; signature verification is fail-closed"
            ) from exc
        try:
            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64, validate=True))
            signature = base64.b64decode(signature_b64, validate=True)
        except (ValueError, TypeError):
            return False
        try:
            public_key.verify(signature, payload)
        except InvalidSignature:
            return False
        return True


class SignatureVerifier(Protocol):
    """Transport- and algorithm-neutral verifier contract.

    Any adapter must return True only for a signature it verified itself;
    absence of a capability must fail closed (reject), never accept.
    """

    def verify(self, public_key_b64: str, payload: bytes, signature_b64: str) -> bool: ...


class PeerTransport(Protocol):
    """Adapter contract for exchanging envelopes. The core opens no network.

    An adapter must deliver and return envelopes unchanged, must not
    execute code from a message, and must not add scopes or rights.
    """

    def deliver(self, envelope: dict[str, Any]) -> str: ...

    def receive(self) -> dict[str, Any]: ...


class InMemoryTransport:
    """Queue-backed demo adapter for tests and local runs. NOT a network.

    No socket is opened; using this class in production would mean the
    peers share one process, which is not multi-node operation.
    """

    def __init__(self) -> None:
        self._queue: list[dict[str, Any]] = []
        self._counter = 0

    def deliver(self, envelope: dict[str, Any]) -> str:
        if not isinstance(envelope, dict):
            raise PeerCoordinationError("envelope must be a dict")
        self._queue.append(json.loads(json.dumps(envelope)))
        self._counter += 1
        return f"inmemory-{self._counter:08d}"

    def receive(self) -> dict[str, Any]:
        if not self._queue:
            raise PeerCoordinationError("no envelope available")
        return self._queue.pop(0)


@dataclass
class _PeerRecord:
    public_key_b64: str
    scopes: frozenset[str]
    state: str = _PEER_ACTIVE
    last_seq: int = 0
    last_seen: str = ""
    failures: list[tuple[str, str]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.failures is None:
            self.failures = []


class PeerRegistry:
    """Explicit registry of voluntary peers with fail-closed verification.

    Peers are registered by the operator or caller (no discovery). Each
    registration fixes the public key and the minimal scope set; messages
    are accepted only when signature, expiry, revocation, replay and scope
    checks all pass. Peer failures are recorded per peer and never block
    verification of other peers (failure isolation).
    """

    def __init__(
        self,
        verifier: SignatureVerifier,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._verifier = verifier
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._peers: dict[str, _PeerRecord] = {}

    def register(self, peer_id: str, public_key_b64: str, scopes: list[str]) -> None:
        if not isinstance(peer_id, str) or not peer_id.strip():
            raise PeerCoordinationError("peer_id must be a non-empty string")
        if not isinstance(public_key_b64, str) or not public_key_b64:
            raise PeerCoordinationError("public_key_b64 must be a non-empty string")
        if peer_id in self._peers:
            raise PeerCoordinationError(f"peer already registered: {peer_id}")
        if (
            not isinstance(scopes, list)
            or not scopes
            or any(not isinstance(scope, str) for scope in scopes)
            or not set(scopes).issubset(ALLOWED_SCOPES)
        ):
            raise PeerCoordinationError("scopes must be a non-empty subset of ALLOWED_SCOPES")
        self._peers[peer_id] = _PeerRecord(
            public_key_b64=public_key_b64, scopes=frozenset(scopes)
        )

    def unregister(self, peer_id: str) -> None:
        """Explicit removal (recovery path for isolated or expired peers)."""
        if peer_id not in self._peers:
            raise PeerCoordinationError(f"unknown peer: {peer_id}")
        del self._peers[peer_id]

    def revoke(self, peer_id: str, reason: str = "") -> None:
        """Widerruf: the peer's key material stays known, so replay
        protection and revocation survive re-registration attempts."""
        record = self._peers.get(peer_id)
        if record is None:
            raise PeerCoordinationError(f"unknown peer: {peer_id}")
        record.state = _PEER_REVOKED
        record.failures.append(("revocation", reason))

    def mark_expired(self, peer_id: str) -> None:
        """Identity-level Ablaufzeit, set by the operator or caller."""
        record = self._peers.get(peer_id)
        if record is None:
            raise PeerCoordinationError(f"unknown peer: {peer_id}")
        record.state = _PEER_EXPIRED

    def verify(self, envelope: Any) -> Verdict:
        """Verify one envelope end to end. Never raises for bad content."""
        if not isinstance(envelope, dict):
            return Verdict(REJECTED_MALFORMED, "", None, "envelope must be a dict")
        try:
            _validate_envelope_fields(envelope)
        except PeerCoordinationError as exc:
            return Verdict(REJECTED_MALFORMED, "", None, str(exc))
        if not envelope["signature"]:
            return Verdict(REJECTED_MALFORMED, envelope["peer_id"], envelope["seq"], "empty signature")
        if envelope["schema"] != MESSAGE_SCHEMA:
            return Verdict(REJECTED_SCHEMA, envelope["peer_id"], envelope["seq"], "schema mismatch")
        record = self._peers.get(envelope["peer_id"])
        if record is None:
            return Verdict(
                REJECTED_UNKNOWN_PEER, envelope["peer_id"], envelope["seq"], "peer not registered"
            )
        if record.state == _PEER_REVOKED:
            return Verdict(REJECTED_REVOKED, envelope["peer_id"], envelope["seq"], "peer revoked")
        if record.state == _PEER_ISOLATED:
            return Verdict(REJECTED_ISOLATED, envelope["peer_id"], envelope["seq"], "peer isolated")
        if record.state == _PEER_EXPIRED:
            return Verdict(REJECTED_EXPIRED, envelope["peer_id"], envelope["seq"], "identity expired")
        claimed = set(envelope["scopes"])
        if envelope["type"] not in record.scopes or not claimed.issubset(record.scopes):
            return Verdict(
                REJECTED_SCOPE_ESCALATION,
                envelope["peer_id"],
                envelope["seq"],
                "message type or scopes exceed registration",
            )
        now = self._now_provider()
        expires_at = _parse_utc(envelope["expires_at"], "expires_at")
        if now >= expires_at:
            return Verdict(REJECTED_EXPIRED, envelope["peer_id"], envelope["seq"], "message expired")
        try:
            signature_ok = self._verifier.verify(
                record.public_key_b64, canonical_payload(envelope), envelope["signature"]
            )
        except PeerCoordinationError as exc:
            return Verdict(
                REJECTED_INVALID_SIGNATURE, envelope["peer_id"], envelope["seq"], f"verifier fail-closed: {exc}"
            )
        except Exception as exc:  # a broken adapter must not widen rights
            return Verdict(
                REJECTED_INVALID_SIGNATURE,
                envelope["peer_id"],
                envelope["seq"],
                f"verifier error: {type(exc).__name__}: {exc}",
            )
        if not signature_ok:
            return Verdict(
                REJECTED_INVALID_SIGNATURE, envelope["peer_id"], envelope["seq"], "signature mismatch"
            )
        if envelope["seq"] <= record.last_seq:
            return Verdict(
                REJECTED_REPLAY, envelope["peer_id"], envelope["seq"], "seq not above last_seq"
            )
        record.last_seq = envelope["seq"]
        record.last_seen = now.isoformat()
        if record.state == _PEER_STALE:
            record.state = _PEER_ACTIVE  # recovery only by fresh, valid evidence
        return Verdict(ACCEPTED, envelope["peer_id"], envelope["seq"], "")

    def record_peer_failure(self, peer_id: str, kind: str, isolate_after: int = 3) -> str:
        """Record a peer failure without raising; other peers stay unaffected.

        UNKNOWN peers are reported as UNKNOWN and not invented. After
        isolate_after recorded failures the peer state becomes ISOLATED.
        """
        record = self._peers.get(peer_id)
        if record is None:
            return _PEER_UNKNOWN
        if not isinstance(kind, str) or not kind:
            kind = "unspecified"
        record.failures.append((kind, self._now_provider().isoformat()))
        if len(record.failures) >= isolate_after:
            record.state = _PEER_ISOLATED
        elif record.state == _PEER_ACTIVE:
            record.state = _PEER_STALE
        return record.state

    def peer_status(self, peer_id: str) -> str:
        record = self._peers.get(peer_id)
        return record.state if record is not None else _PEER_UNKNOWN

    def failure_log(self, peer_id: str) -> tuple[tuple[str, str], ...]:
        record = self._peers.get(peer_id)
        return tuple(record.failures) if record is not None else ()

    def last_seq(self, peer_id: str) -> int | None:
        record = self._peers.get(peer_id)
        return record.last_seq if record is not None else None


__all__ = [
    "ACCEPTED",
    "ALLOWED_SCOPES",
    "Ed25519Verifier",
    "InMemoryTransport",
    "MAX_BODY_CHARS",
    "MESSAGE_SCHEMA",
    "MESSAGE_TYPES",
    "PeerCoordinationError",
    "PeerKeyPair",
    "PeerRegistry",
    "PeerTransport",
    "REJECTED_EXPIRED",
    "REJECTED_INVALID_SIGNATURE",
    "REJECTED_ISOLATED",
    "REJECTED_MALFORMED",
    "REJECTED_REPLAY",
    "REJECTED_REVOKED",
    "REJECTED_SCHEMA",
    "REJECTED_SCOPE_ESCALATION",
    "REJECTED_UNKNOWN_PEER",
    "SignatureVerifier",
    "STATES",
    "Verdict",
    "build_envelope",
    "canonical_payload",
    "sign_envelope",
]
