"""Tests for the authorized control adapter (issue #24 stage 3, #592 criterion 2).

Run without pytest via a plain-function runner; the real
HashChainAuditLogger (src/v91/audit.py) is used as the audit journal so
the REUSE claim is tested, not asserted.
"""
from __future__ import annotations

import inspect
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import v91.control_adapter as ca
from v91.audit import HashChainAuditLogger
from v91.control_adapter import (
    ABGELEHNT_AUSFUEHRUNGSFEHLER,
    ABGELEHNT_KEINE_BERECHTIGUNG,
    ABGELEHNT_KEIN_GUELTIGER_UEBERGANG,
    ABGELEHNT_UNBEKANNTE_AKTION,
    ABGELEHNT_UNBEKANNTE_KOMPONENTE,
    ABGELEHNT_UNVOLLSTAENDIG,
    AUSGEFUEHRT,
    ISOLIERT,
    LAUFEND,
    PAUSIERT,
    AuthorizedControlAdapter,
    ComponentStateError,
    ControlAdapterError,
    ControlPolicy,
    ControlRequest,
    TestComponent,
)

NOW = datetime(2026, 11, 28, 14, 0, tzinfo=timezone.utc)


def _journal() -> tuple[HashChainAuditLogger, Path]:
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "control_audit.jsonl"
    return HashChainAuditLogger(path), path


def _adapter(policy_grants=None) -> tuple[AuthorizedControlAdapter, Path]:
    journal, path = _journal()
    policy = ControlPolicy(grants=policy_grants or {})
    adapter = AuthorizedControlAdapter(policy, journal, now_provider=lambda: NOW)
    return adapter, path


def _request(peer_id="node-a", component_id="comp-1", action="pause", **overrides):
    fields = {
        "peer_id": peer_id,
        "component_id": component_id,
        "action": action,
        "policy_version": "policy-2026-11-28",
        "ausloesekriterium": "Latenz > Schwelle, dokumentiert",
        "belege": ["messung-42"],
        "rollback_plan": "restore mit Snapshot, keine Datenloeschung",
        "wirkungsradius": "eine lokale Testkomponente",
    }
    fields.update(overrides)
    return ControlRequest(**fields)


def _granted_adapter(**extra_grants) -> tuple[AuthorizedControlAdapter, TestComponent, TestComponent, Path]:
    grants = {("node-a", "comp-1"): frozenset({"pause", "resume", "isolate", "restore"})}
    grants.update(extra_grants)
    adapter, path = _adapter(grants)
    comp1 = TestComponent("comp-1", payload={"auftraege": 3})
    comp2 = TestComponent("comp-2", payload={"auftraege": 7})
    adapter.register_component(comp1)
    adapter.register_component(comp2)
    return adapter, comp1, comp2, path


def test_authorized_full_cycle_with_state_preservation():
    adapter, comp, _, _ = _granted_adapter()
    assert comp.state == LAUFEND
    pause = adapter.request(_request(action="pause"))
    assert pause.status == AUSGEFUEHRT and pause.ausgefuehrt
    assert pause.von_zustand == LAUFEND and pause.nach_zustand == PAUSIERT
    isolate = adapter.request(_request(action="isolate"))
    assert isolate.status == AUSGEFUEHRT and comp.state == ISOLIERT
    comp.payload["auftraege"] = -1  # stray mutation while isolated
    restore = adapter.request(_request(action="restore"))
    assert restore.status == AUSGEFUEHRT
    assert comp.state == LAUFEND
    # Restore is a real rollback to the last control checkpoint (pause/isolate
    # snapshot): the stray mutation did not survive, nothing was destroyed.
    assert comp.payload["auftraege"] == 3, "ISOLATE_NOT_DESTROY: Snapshot muss erhalten sein"


def test_resume_from_paused_and_invalid_transitions_rejected():
    adapter, comp, _, _ = _granted_adapter()
    assert adapter.request(_request(action="pause")).status == AUSGEFUEHRT
    assert adapter.request(_request(action="resume")).status == AUSGEFUEHRT
    # resume again from LAUFEND is not a valid transition
    again = adapter.request(_request(action="resume"))
    assert again.status == ABGELEHNT_KEIN_GUELTIGER_UEBERGANG
    # restore only from PAUSIERT/ISOLIERT, not from LAUFEND
    restore = adapter.request(_request(action="restore"))
    assert restore.status == ABGELEHNT_KEIN_GUELTIGER_UEBERGANG
    assert comp.state == LAUFEND


def test_unknown_component_and_action_rejected():
    adapter, comp, _, _ = _granted_adapter()
    unknown_component = adapter.request(_request(component_id="comp-ghost"))
    assert unknown_component.status == ABGELEHNT_UNBEKANNTE_KOMPONENTE
    unknown_action = adapter.request(_request(action="shutdown"))
    assert unknown_action.status == ABGELEHNT_UNBEKANNTE_AKTION
    assert comp.state == LAUFEND  # nothing was executed


def test_empty_policy_and_missing_grant_fail_closed():
    adapter, _ = _adapter()  # empty policy: grants nothing
    component = TestComponent("comp-1")
    adapter.register_component(component)
    verdict = adapter.request(_request())
    assert verdict.status == ABGELEHNT_KEINE_BERECHTIGUNG
    assert component.state == LAUFEND
    # Grant for one component must not transfer to another component.
    adapter2, comp1, comp2, _ = _granted_adapter()
    cross = adapter2.request(_request(component_id="comp-2"))
    assert cross.status == ABGELEHNT_KEINE_BERECHTIGUNG
    assert comp2.state == LAUFEND
    # Grant for one peer must not transfer to another peer.
    other_peer = adapter2.request(_request(peer_id="node-b"))
    assert other_peer.status == ABGELEHNT_KEINE_BERECHTIGUNG


def test_incomplete_requests_rejected_with_named_problems():
    adapter, comp, _, _ = _granted_adapter()
    cases = [
        _request(policy_version=""),
        _request(ausloesekriterium=" "),
        _request(belege=[]),
        _request(rollback_plan=""),
        _request(wirkungsradius=""),  # present but empty
        "not-a-request",
    ]
    for case in cases:
        verdict = adapter.request(case)
        assert verdict.status == ABGELEHNT_UNVOLLSTAENDIG, verdict
    assert comp.state == LAUFEND


def test_policy_construction_rejects_wildcards_and_unknown_actions():
    for bad in (
        {("*", "comp-1"): frozenset({"pause"})},
        {("node-a", "*"): frozenset({"pause"})},
        {("node-a", "comp-1"): frozenset({"destroy"})},
        {("node-a", "comp-1"): frozenset()},
    ):
        try:
            ControlPolicy(grants=bad)
            raised = False
        except ControlAdapterError:
            raised = True
        assert raised, f"policy {bad!r} must be rejected"
    # Unknown actions never enter STEUERAKTIONEN; no destructive action exists.
    assert "destroy" not in ca.STEUERAKTIONEN
    assert "shutdown" not in ca.STEUERAKTIONEN


def test_every_decision_is_audited_in_a_verifiable_hash_chain():
    adapter, comp, _, path = _granted_adapter()
    executed = adapter.request(_request(action="pause"))
    rejected = adapter.request(_request(peer_id="node-b"))
    assert executed.status == AUSGEFUEHRT
    assert rejected.status == ABGELEHNT_KEINE_BERECHTIGUNG
    journal = HashChainAuditLogger(path)
    records = journal.verify_chain()  # raises if the chain is broken
    actions = [r["action"] for r in records]
    # Two-phase audit: authorization BEFORE execution, outcome afterwards,
    # plus one rejection entry.
    assert actions == [
        "control:autorisiert:pause",
        "control:ausgefuehrt:pause",
        "control:abgelehnt",
    ]
    assert len(records) == 3
    auth_info = records[0]["additional_info"]
    assert auth_info["ergebnis"] == "AUTORISIERT"
    assert auth_info["policy_version"] == "policy-2026-11-28"
    assert auth_info["belege"] == ["messung-42"]
    exec_info = records[1]["additional_info"]
    assert exec_info["ergebnis"] == AUSGEFUEHRT and exec_info["nach"] == PAUSIERT


def test_broken_audit_journal_fails_closed_without_execution():
    class BrokenJournal:
        def log(self, action, user, additional_info=None):
            raise RuntimeError("journal unavailable")

    policy = ControlPolicy(grants={("node-a", "comp-1"): frozenset({"pause"})})
    adapter = AuthorizedControlAdapter(policy, BrokenJournal(), now_provider=lambda: NOW)
    comp = TestComponent("comp-1")
    adapter.register_component(comp)
    try:
        adapter.request(_request())
        raised = False
    except RuntimeError:
        raised = True
    assert raised, "broken journal must fail closed (raise), never execute silently"
    assert comp.state == LAUFEND


def test_component_failure_is_isolated():
    grants = {
        ("node-a", "comp-1"): frozenset({"pause"}),
        ("node-a", "comp-2"): frozenset({"pause"}),
    }
    adapter, _ = _adapter(grants)
    comp1 = TestComponent("comp-1", payload={})
    comp2 = TestComponent("comp-2", payload={})
    adapter.register_component(comp1)
    adapter.register_component(comp2)
    comp1.fail_on = "pause"
    verdict = adapter.request(_request(action="pause"))
    assert verdict.status == ABGELEHNT_AUSFUEHRUNGSFEHLER
    assert comp1.state == LAUFEND  # failed action left state unchanged
    # Local work continues: other components stay controllable.
    ok = adapter.request(_request(component_id="comp-2", action="pause"))
    assert ok.status == AUSGEFUEHRT and comp2.state == PAUSIERT


def test_duplicate_registration_and_bad_component_rejected():
    adapter, comp, _, _ = _granted_adapter()
    try:
        adapter.register_component(TestComponent("comp-1"))
        raised = False
    except ControlAdapterError:
        raised = True
    assert raised
    try:
        adapter.register_component("not-a-component")
        raised = False
    except ControlAdapterError:
        raised = True
    assert raised


def test_component_state_guards_directly():
    comp = TestComponent("comp-x")
    try:
        comp._execute("resume")  # LAUFEND -> resume invalid
        raised = False
    except ComponentStateError:
        raised = True
    assert raised
    comp._execute("pause")
    assert comp.state == PAUSIERT
    comp._execute("isolate")
    assert comp.state == ISOLIERT
    comp._execute("restore")
    assert comp.state == LAUFEND
    assert comp.events == [("pause", PAUSIERT), ("isolate", ISOLIERT), ("restore", LAUFEND)]


def test_component_state_query_is_honest_for_unknown_ids():
    adapter, _, _, _ = _granted_adapter()
    assert adapter.component_state("comp-1") == LAUFEND
    assert adapter.component_state("comp-ghost") == "UNBEKANNT"


def test_module_contains_no_network_or_code_execution_primitives():
    source = inspect.getsource(ca)
    for forbidden in (
        "import socket",
        "import subprocess",
        "urllib",
        "requests",
        "eval(",
        "exec(",
        "__import__",
        "os.system",
    ):
        assert forbidden not in source, f"forbidden primitive in module: {forbidden}"


def test_request_evidence_fields_serialize_json():
    request = _request()
    encoded = json.dumps(request.belege)
    assert encoded == '["messung-42"]'
    assert request.action in ca.STEUERAKTIONEN
