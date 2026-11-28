"""Federated control gate: stage-2 identity -> stage-3 execution (issue #24).

End-to-end integration of the two existing building blocks:

- Stage 2 (src/v91/peer_coordination.py, PR #28): explicit peer
  registration, signed envelopes, expiry, revocation, replay
  protection, minimal scopes, failure isolation.
- Stage 3 (src/v91/control_adapter.py, PR #29): policy-authorized
  control actions on registered test components with two-phase audit.

This module adds ONLY the glue between them: a gate that accepts a
signed "control_request" envelope, verifies it through the PeerRegistry
(SIGNATURE != TRUTH, ACCEPTED != EXECUTED), binds the payload to the
verified envelope identity (IDENTITAETSBINDUNG: body.peer_id must equal
envelope.peer_id, so no peer can steer for another), and then delegates
to the AuthorizedControlAdapter. VERIFICATION != AUTHORIZATION: an
accepted envelope still needs an explicit policy grant; without a grant
nothing executes (fail-closed, no defaults).

Honest limits (binding):
- No network, no sockets, no discovery, no remote code. The envelope
  arrives via the caller's transport (transport-neutral).
- The gate controls only in-process TEST components through the stage-3
  adapter; real systems need per-action operator allowlists
  (FREIGABE != BERECHTIGUNG, jede reale Aktion einzeln).
- Every federation-layer rejection produces an audit entry; a broken
  journal fails loudly (fail-closed, ISOLATE_NOT_DESTROY: nothing is
  executed without an audit trail).
- SIGNATUR != WAHRHEIT: a verified envelope proves key possession and
  currency, not that the payload's evidence claims are true.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from .control_adapter import (
    ABGELEHNT_UNVOLLSTAENDIG,
    AUSGEFUEHRT,
    AuditJournal,
    AuthorizedControlAdapter,
    ControlAdapterError,
    ControlDecision,
    ControlRequest,
)
from .peer_coordination import PeerRegistry, build_envelope

CONTROL_REQUEST_TYPE = "control_request"

ABGELEHNT_NICHT_VERIFIZIERT = "ABGELEHNT_NICHT_VERIFIZIERT"
ABGELEHNT_FALSCHER_TYP = "ABGELEHNT_FALSCHER_TYP"
ABGELEHNT_MALFORMED = "ABGELEHNT_MALFORMED"
ABGELEHNT_IDENTITAETSMISMATCH = "ABGELEHNT_IDENTITAETSMISMATCH"

REQUIRED_PAYLOAD_FIELDS = (
    "peer_id",
    "component_id",
    "action",
    "policy_version",
    "ausloesekriterium",
    "belege",
    "rollback_plan",
    "wirkungsradius",
)


class ControlFederationError(RuntimeError):
    """Invalid gate construction or non-delegatable input; fail-closed."""


def _audit_user(envelope: Any) -> str:
    """Honest journal label for the requesting identity (BEZEICHNUNG != IDENTITAET)."""
    peer_id = ""
    if isinstance(envelope, dict):
        candidate = envelope.get("peer_id")
        if isinstance(candidate, str):
            peer_id = candidate.strip()
    return peer_id or "UNBEKANNTER_PEER"


def build_control_envelope(
    *,
    peer_id: str,
    seq: int,
    issued_at: str,
    expires_at: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build an unsigned control_request envelope from a payload dict.

    The payload is embedded as canonical JSON in the body. The caller
    signs the result with peer_coordination.sign_envelope. Payloads that
    do not serialize to at most the peer-protocol body limit raise here
    (fail-closed instead of truncation or silent change).
    """
    if not isinstance(payload, dict):
        raise ControlFederationError("payload must be a dict")
    try:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ControlFederationError(f"payload is not JSON-serializable: {exc}") from exc
    from .peer_coordination import MAX_BODY_CHARS

    if len(body) > MAX_BODY_CHARS:
        raise ControlFederationError(
            f"payload body exceeds {MAX_BODY_CHARS} chars"
        )
    return build_envelope(
        type=CONTROL_REQUEST_TYPE,
        peer_id=peer_id,
        seq=seq,
        issued_at=issued_at,
        expires_at=expires_at,
        scopes=[CONTROL_REQUEST_TYPE],
        body=body,
    )


class FederatedControlGate:
    """Verify signed control envelopes, then delegate to the local adapter.

    Order of checks (fail-closed, each rejection journaled):
    1. envelope verification via the stage-2 registry (signature,
       expiry, revocation, replay, scopes, peer state);
    2. message type must be control_request;
    3. body must be a JSON object with all mandatory evidence fields;
    4. body.peer_id must equal envelope.peer_id (IDENTITAETSBINDUNG);
    5. the stage-3 adapter decides and executes under its own policy
       and two-phase audit (executed AND policy-rejected control
       attempts are journaled there).
    """

    def __init__(
        self,
        registry: PeerRegistry,
        adapter: AuthorizedControlAdapter,
        audit_journal: AuditJournal,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(registry, PeerRegistry):
            raise ControlFederationError("registry must be a PeerRegistry")
        if not isinstance(adapter, AuthorizedControlAdapter):
            raise ControlFederationError("adapter must be an AuthorizedControlAdapter")
        self._registry = registry
        self._adapter = adapter
        self._journal = audit_journal
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def submit(self, envelope: Any) -> ControlDecision:
        """One signed envelope -> one decision; never raises for content.

        Only a broken audit journal raises (loud fail, nothing executed).
        """
        verdict = self._registry.verify(envelope)
        if not verdict.accepted:
            return self._rejected(
                envelope,
                ABGELEHNT_NICHT_VERIFIZIERT,
                f"{verdict.status}: {verdict.reason}",
            )
        assert isinstance(envelope, dict)
        if envelope.get("type") != CONTROL_REQUEST_TYPE:
            return self._rejected(
                envelope,
                ABGELEHNT_FALSCHER_TYP,
                f"expected {CONTROL_REQUEST_TYPE}, got {envelope.get('type')!r}",
            )
        try:
            payload = json.loads(envelope.get("body", ""))
        except (json.JSONDecodeError, TypeError) as exc:
            return self._rejected(
                envelope, ABGELEHNT_MALFORMED, f"body is not valid JSON: {exc}"
            )
        if not isinstance(payload, dict):
            return self._rejected(
                envelope, ABGELEHNT_MALFORMED, "body must encode a JSON object"
            )
        missing = [f for f in REQUIRED_PAYLOAD_FIELDS if f not in payload]
        if missing:
            return self._rejected(
                envelope,
                ABGELEHNT_MALFORMED,
                f"payload fields missing: {missing}",
            )
        if payload.get("peer_id") != verdict.peer_id:
            return self._rejected(
                envelope,
                ABGELEHNT_IDENTITAETSMISMATCH,
                "payload peer_id does not match the verified envelope identity",
            )
        try:
            request = ControlRequest(
                peer_id=payload["peer_id"],
                component_id=payload["component_id"],
                action=payload["action"],
                policy_version=payload["policy_version"],
                ausloesekriterium=payload["ausloesekriterium"],
                belege=list(payload["belege"]),
                rollback_plan=payload["rollback_plan"],
                wirkungsradius=payload["wirkungsradius"],
            )
        except TypeError as exc:
            return self._rejected(
                envelope, ABGELEHNT_MALFORMED, f"payload is not a request: {exc}"
            )
        # Phase 1 federation journal entry BEFORE delegation: a broken
        # journal raises here, so the adapter is never reached without an
        # audit trail (fail-closed).
        self._journal.log(
            action="control:federation:verifiziert",
            user=verdict.peer_id,
            additional_info={
                "ergebnis": "VERIFIZIERT",
                "seq": verdict.seq,
                "aktion": payload["action"],
                "component_id": payload["component_id"],
                "zeitpunkt_utc": self._now_provider().isoformat(),
            },
        )
        # Delegation: VERIFICATION != AUTHORIZATION. The adapter applies
        # the stage-3 policy and its own two-phase audit; its decision is
        # the gate's decision (KEINE zweite Wahrheit).
        return self._adapter.request(request)

    def _rejected(self, envelope: Any, status: str, reason: str) -> ControlDecision:
        user = _audit_user(envelope)
        self._journal.log(
            action="control:federation:abgelehnt",
            user=user,
            additional_info={
                "ergebnis": status,
                "grund": reason,
                "zeitpunkt_utc": self._now_provider().isoformat(),
            },
        )
        component_id = ""
        action = ""
        if isinstance(envelope, dict):
            body = envelope.get("body")
            if isinstance(body, str) and body:
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("component_id"), str):
                        component_id = parsed["component_id"]
                    if isinstance(parsed.get("action"), str):
                        action = parsed["action"]
        return ControlDecision(
            status=status,
            reason=reason,
            peer_id=user if user != "UNBEKANNTER_PEER" else "",
            component_id=component_id,
            action=action,
            von_zustand="",
            nach_zustand="",
        )


__all__ = [
    "ABGELEHNT_FALSCHER_TYP",
    "ABGELEHNT_IDENTITAETSMISMATCH",
    "ABGELEHNT_MALFORMED",
    "ABGELEHNT_NICHT_VERIFIZIERT",
    "AUSGEFUEHRT",
    "CONTROL_REQUEST_TYPE",
    "ABGELEHNT_UNVOLLSTAENDIG",
    "ControlFederationError",
    "FederatedControlGate",
    "build_control_envelope",
]
