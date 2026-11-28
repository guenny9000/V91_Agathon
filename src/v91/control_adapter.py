"""Authorized control adapter for local test components (issue #24 stage 3).

Runtime-side building block for the MAX-BEST cross-block work cycle
(v91-core-system issue #592, acceptance criterion 2): an authorized
control adapter can pause, isolate and restore a component through a
defined rollback; unauthorized actions are rejected fail-closed.

Honest limits (binding):
- ENTSCHEIDUNG != VOLLZUG: this adapter acts on explicitly registered,
  in-process TEST components only. Controlling real external systems
  needs real adapters, an operator-approved allowlist per action and
  per target (V91 rule: FREIGABE != BERECHTigung, jede reale Aktion
  einzeln), and stays outside this module.
- ABSCHALTEN == ISOLIEREN: there is no destroy action. Isolate freezes
  a component with its state preserved (ISOLATE_NOT_DESTROY); restore
  is the explicit rollback path.
- The policy here is the runtime-side grant mirror; the core contract
  (controller/verbund_arbeitszyklus.py, pruefe_steueraktion) remains
  the authoritative cross-block decision layer (ROLLEN != CODE,
  AGATHON-Adapter dupliziert NICHT die Core-Pruefung, sondern setzt
  sie lokal um).
- No network, no remote code, no automatic privilege escalation.
  Every executed or rejected request produces an audit entry; without
  a working audit journal no action is executed (fail-closed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

STEUERAKTIONEN = frozenset({"pause", "resume", "isolate", "restore"})

AUSGEFUEHRT = "AUSGEFUEHRT"
ABGELEHNT_UNVOLLSTAENDIG = "ABGELEHNT_UNVOLLSTAENDIG"
ABGELEHNT_UNBEKANNTE_KOMPONENTE = "ABGELEHNT_UNBEKANNTE_KOMPONENTE"
ABGELEHNT_UNBEKANNTE_AKTION = "ABGELEHNT_UNBEKANNTE_AKTION"
ABGELEHNT_KEINE_BERECHTIGUNG = "ABGELEHNT_KEINE_BERECHTIGUNG"
ABGELEHNT_KEIN_GUELTIGER_UEBERGANG = "ABGELEHNT_KEIN_GUELTIGER_UEBERGANG"
ABGELEHNT_AUSFUEHRUNGSFEHLER = "ABGELEHNT_AUSFUEHRUNGSFEHLER"

LAUFEND = "LAUFEND"
PAUSIERT = "PAUSIERT"
ISOLIERT = "ISOLIERT"

GUELTIGE_UEBERGAENGE = {
    "pause": {LAUFEND},
    "resume": {PAUSIERT},
    "isolate": {LAUFEND, PAUSIERT},
    "restore": {PAUSIERT, ISOLIERT},
}


class ControlAdapterError(RuntimeError):
    """Invalid adapter input or construction; fail-closed."""


class ComponentStateError(RuntimeError):
    """A component transition was invalid; state is unchanged."""


class AuditJournal(Protocol):
    """Append-only journal contract (e.g. audit.HashChainAuditLogger)."""

    def log(self, action: str, user: str, additional_info: Any = None) -> dict: ...


class TestComponent:
    """Explicitly local, in-process test target. NOT a real system.

    Holds a small mutable payload so tests can prove that pause and
    isolate preserve state (ISOLATE_NOT_DESTROY) and that restore is
    a real rollback.
    """

    def __init__(self, component_id: str, payload: dict | None = None) -> None:
        if not isinstance(component_id, str) or not component_id.strip():
            raise ControlAdapterError("component_id must be a non-empty string")
        self.component_id = component_id
        self.state = LAUFEND
        self.payload: dict[str, Any] = dict(payload or {})
        self.events: list[tuple[str, str]] = []
        self._snapshot: dict[str, Any] | None = None
        self.fail_on: str | None = None  # test hook: action name that raises

    def _execute(self, action: str) -> None:
        if self.fail_on == action:
            raise ComponentStateError(f"component {self.component_id} fails on {action}")
        if action not in GUELTIGE_UEBERGAENGE:
            raise ComponentStateError(f"unknown action: {action}")
        if self.state not in GUELTIGE_UEBERGAENGE[action]:
            raise ComponentStateError(
                f"{action} not allowed from state {self.state}"
            )
        if action == "pause":
            self._snapshot = dict(self.payload)
            self.state = PAUSIERT
        elif action == "resume":
            self.state = LAUFEND
        elif action == "isolate":
            self._snapshot = dict(self.payload)
            self.state = ISOLIERT
        elif action == "restore":
            if self._snapshot is not None:
                self.payload = dict(self._snapshot)
            self.state = LAUFEND
        self.events.append((action, self.state))

    def status(self) -> dict[str, Any]:
        return {"component_id": self.component_id, "state": self.state}


@dataclass(frozen=True)
class ControlPolicy:
    """Explicit per-(peer, component) action grants. No wildcards.

    Construction fails closed on unknown actions or wildcard entries;
    an empty policy grants nothing.
    """

    grants: dict[tuple[str, str], frozenset[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for (peer_id, component_id), actions in self.grants.items():
            if not isinstance(peer_id, str) or not peer_id.strip():
                raise ControlAdapterError("peer_id must be a non-empty string")
            if not isinstance(component_id, str) or not component_id.strip():
                raise ControlAdapterError("component_id must be a non-empty string")
            if "*" in (peer_id, component_id):
                raise ControlAdapterError("wildcard grants are not allowed")
            if not isinstance(actions, (frozenset, set)) or not actions:
                raise ControlAdapterError("grant must be a non-empty action set")
            unknown = set(actions) - STEUERAKTIONEN
            if unknown:
                raise ControlAdapterError(f"unknown actions in grant: {sorted(unknown)}")

    def allows(self, peer_id: str, component_id: str, action: str) -> bool:
        granted = self.grants.get((peer_id, component_id), frozenset())
        return action in granted


@dataclass
class ControlRequest:
    """One control request; every field is mandatory evidence."""

    peer_id: str
    component_id: str
    action: str
    policy_version: str
    ausloesekriterium: str
    belege: list[str]
    rollback_plan: str
    wirkungsradius: str


@dataclass(frozen=True)
class ControlDecision:
    """Outcome of one request, honestly reported in both directions."""

    status: str
    reason: str
    peer_id: str
    component_id: str
    action: str
    von_zustand: str
    nach_zustand: str

    @property
    def ausgefuehrt(self) -> bool:
        return self.status == AUSGEFUEHRT


def _request_problems(request: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(request, ControlRequest):
        return ["request must be a ControlRequest"]
    for name in ("peer_id", "component_id", "action", "policy_version",
                "ausloesekriterium", "rollback_plan", "wirkungsradius"):
        value = getattr(request, name)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{name} must be a non-empty string")
    if not isinstance(request.belege, list) or not request.belege:
        problems.append("belege must be a non-empty list")
    elif any(not isinstance(item, str) or not item.strip() for item in request.belege):
        problems.append("belege entries must be non-empty strings")
    return problems


class AuthorizedControlAdapter:
    """Execute policy-authorized control actions on registered test components.

    Every request produces an audit entry (executed or rejected). If
    the audit journal fails, nothing is executed (fail-closed). A
    failing component affects only itself; other components stay
    controllable (failure isolation).
    """

    def __init__(
        self,
        policy: ControlPolicy,
        audit_journal: AuditJournal,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(policy, ControlPolicy):
            raise ControlAdapterError("policy must be a ControlPolicy")
        self._policy = policy
        self._journal = audit_journal
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._components: dict[str, TestComponent] = {}

    def register_component(self, component: TestComponent) -> None:
        if not isinstance(component, TestComponent):
            raise ControlAdapterError("component must be a TestComponent")
        if component.component_id in self._components:
            raise ControlAdapterError(
                f"component already registered: {component.component_id}"
            )
        self._components[component.component_id] = component

    def request(self, request: Any) -> ControlDecision:
        """Verify and (if authorized) execute one request; never raises
        for request content. Only a failing audit journal raises."""
        problems = _request_problems(request)
        if problems:
            return self._rejected(request, ABGELEHNT_UNVOLLSTAENDIG, "; ".join(problems))
        assert isinstance(request, ControlRequest)
        component = self._components.get(request.component_id)
        if component is None:
            return self._rejected(request, ABGELEHNT_UNBEKANNTE_KOMPONENTE,
                                  "component not registered")
        if request.action not in STEUERAKTIONEN:
            return self._rejected(request, ABGELEHNT_UNBEKANNTE_AKTION,
                                  "action not in STEUERAKTIONEN")
        if not self._policy.allows(request.peer_id, request.component_id, request.action):
            return self._rejected(request, ABGELEHNT_KEINE_BERECHTIGUNG,
                                  "no explicit grant for (peer, component, action)")
        if component.state not in GUELTIGE_UEBERGAENGE[request.action]:
            return self._rejected(request, ABGELEHNT_KEIN_GUELTIGER_UEBERGANG,
                                  f"{request.action} not allowed from {component.state}")
        von = component.state
        # Phase 1: journal the authorization BEFORE executing. A broken
        # journal raises here, so nothing is ever executed without an
        # audit trail (fail-closed).
        self._journal.log(
            action=f"control:autorisiert:{request.action}",
            user=request.peer_id,
            additional_info={
                "ergebnis": "AUTORISIERT",
                "von": von,
                "policy_version": request.policy_version,
                "ausloesekriterium": request.ausloesekriterium,
                "belege": list(request.belege),
                "rollback_plan": request.rollback_plan,
                "wirkungsradius": request.wirkungsradius,
                "zeitpunkt_utc": self._now_provider().isoformat(),
            },
        )
        try:
            component._execute(request.action)  # noqa: SLF001 - same package boundary
        except ComponentStateError as exc:
            decision = self._rejected(request, ABGELEHNT_AUSFUEHRUNGSFEHLER, str(exc))
            return decision
        # Phase 2: journal the completed execution. If this write fails the
        # action has already run; the authorization entry above remains and
        # the failure is loud (Teiljournal ist ehrlich dokumentiert).
        self._journal.log(
            action=f"control:ausgefuehrt:{request.action}",
            user=request.peer_id,
            additional_info={
                "ergebnis": AUSGEFUEHRT,
                "von": von,
                "nach": component.state,
                "zeitpunkt_utc": self._now_provider().isoformat(),
            },
        )
        return ControlDecision(AUSGEFUEHRT, "", request.peer_id,
                               request.component_id, request.action, von, component.state)

    def _rejected(self, request: Any, status: str, reason: str) -> ControlDecision:
        peer_id = getattr(request, "peer_id", "") if not isinstance(request, str) else ""
        component_id = getattr(request, "component_id", "") if not isinstance(request, str) else ""
        action = getattr(request, "action", "") if not isinstance(request, str) else ""
        # Honest journal label when the requester is unknown or malformed:
        # a label, not an identity claim (BEZEICHNUNG != IDENTITAET).
        audit_user = peer_id.strip() or "UNBEKANNTER_PEER"
        self._journal.log(
            action="control:abgelehnt",
            user=audit_user,
            additional_info={
                "ergebnis": status,
                "grund": reason,
                "peer_id": peer_id,
                "component_id": component_id,
                "aktion": action,
                "zeitpunkt_utc": self._now_provider().isoformat(),
            },
        )
        return ControlDecision(status, reason, peer_id, component_id, action, "", "")

    def _audit(self, action: str, request: ControlRequest, info: dict[str, Any]) -> None:
        """Journal write; a broken journal fails closed (raises)."""
        self._journal.log(action=action, user=request.peer_id, additional_info=info)

    def component_state(self, component_id: str) -> str:
        component = self._components.get(component_id)
        return component.state if component is not None else "UNBEKANNT"


__all__ = [
    "ABGELEHNT_AUSFUEHRUNGSFEHLER",
    "ABGELEHNT_KEINE_BERECHTIGUNG",
    "ABGELEHNT_KEIN_GUELTIGER_UEBERGANG",
    "ABGELEHNT_UNBEKANNTE_AKTION",
    "ABGELEHNT_UNBEKANNTE_KOMPONENTE",
    "ABGELEHNT_UNVOLLSTAENDIG",
    "AUSGEFUEHRT",
    "AuditJournal",
    "AuthorizedControlAdapter",
    "ComponentStateError",
    "ControlAdapterError",
    "ControlDecision",
    "ControlPolicy",
    "ControlRequest",
    "GUELTIGE_UEBERGAENGE",
    "ISOLIERT",
    "LAUFEND",
    "PAUSIERT",
    "STEUERAKTIONEN",
    "TestComponent",
]
