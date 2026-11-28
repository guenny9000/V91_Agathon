# V91 Agathon: Freiwillige Peer-Koordination, Stufe 2 (28.11.2026)

Issue: V91_Agathon #24, Zielstufe 2 ("Freiwillige Peer-Koordination mit
signierter Identitaet, Ablaufzeit, Widerruf, Replay-Schutz und minimalen
Rechten") sowie die Punkte 2, 4 und 5 des Umsetzungsziels
(transportneutraler Austausch, Fehler-Isolierung, keine Remote-Code-
Ausfuehrung).

## Umfang (gebaut und getestet)

`src/v91/peer_coordination.py`:

- Explizite Peer-Registrierung durch Aufrufer/Betreiber (kein Discovery,
  keine Netzverbindung). Registrierung legt Identitaet (peer_id),
  Ed25519-Public-Key und die minimale Rechte-Menge (scopes) fest.
- Signierte Nachrichten: Envelopes (Schema v91.agathon.peer_message.v1)
  werden ueber deterministische Kanonisierung (REUSE: canonical_bytes aus
  ledger.py, KEINE zweite Kanonisierung) mit Ed25519 signiert.
- Ablaufzeit: je Nachricht issued_at/expires_at mit UTC-Zwang; abgelaufen
  wird fail-closed abgelehnt. Identitaets-Ablauf via mark_expired().
- Widerruf: revoke() sperrt die Identitaet dauerhaft; Neuregistrierung
  unter gleichem Namen wird verweigert (kein stiller Schluesseltausch).
- Replay-Schutz: strenge monoton steigende seq je Peer; gleiche oder
  niedrigere Folgeelemente werden abgelehnt, ohne den Zaehler zu bewegen.
- Minimale Rechte: scopes sind eine feste Teilmenge von ALLOWED_SCOPES
  (hello, heartbeat, status_report, task_offer, task_result); jeder
  Uebergriff (Typ oder Anspruch ausserhalb der Registrierung) wird als
  REJECTED_SCOPE_ESCALATION abgelehnt. Es gibt keinen Wildcard-Scope.
- Fehler-Isolierung: record_peer_failure() zeichnet Fehler je Peer auf
  (STALE, ab Schwelle ISOLATED) und blockiert niemals andere Peers oder
  den lokalen Betrieb; unbekannte Peers werden als UNKNOWN gemeldet,
  nicht erfunden. STALE erholt sich nur durch frische, gueltige Evidenz.
- Transportneutral: PeerTransport-Protokoll als dokumentierter Adapter-
  Vertrag; InMemoryTransport ist ein Demo-/Test-Adapter ohne Netz.

`tests/test_peer_coordination.py`: 18 Tests. Die Registry-Logik laeuft
gegen einen deterministischen Stub-Verifizierer (kein Paketbedarf), der
echte Ed25519-Pfad zusaetzlich immer dann, wenn das deklarierte Paket
`cryptography` verfuegbar ist (CI installiert es). Ein Negativtest
verriegelt, dass das Modul keine Netz- oder Code-Ausfuehrungs-Primitive
enthaelt (import socket/subprocess/urllib/requests/eval/exec/__import__).

## Was bewusst NICHT behauptet wird

- KEIN Netzwerktransport, KEIN Discovery, KEINE Fernsteuerung: Stufe 3
  (autorisierte Steuerungsadapter) und Stufe 4 (gemeinsame Wirkungs-
  metrik) sind nicht Teil dieses Blocks.
- ECHTER Multi-Node-Betrieb: NICHT_GEPRUEFT. Es existiert kein Messlauf
  mit zwei echten Knoten (v91-core-system Issue #103 bleibt offen).
- SIGNATUR != WAHRHEIT: Eine gueltige Signatur belegt Schluesselbesitz,
  nicht die Wahrheit des Inhalts.
- VERIFIZIERUNG != AUTORISIERUNG: Eine akzeptierte Nachricht gewaehrt
  keine Rechte ausser den registrierten Scopes; ACCEPTED != EXECUTED.
- Der InMemoryTransport ist kein Multi-Node-Nachweis: Peers in einem
  Prozess teilen sich keine verteilte Laufzeit.

## Nachweisgrenzen

- Lokale Verifikation (28.11.2026, Vibe-Sandbox): compileall OK, 18/18
  Testfunktionen gegen die Registry-Logik (Stub-Verifizierer); das Paket
  `cryptography` ist in der Sandbox nicht installierbar
  (Paketinstallation verboten), daher lief der Ed25519-Echttest nicht
  lokal, sondern laeuft in der CI (deklarierte Abhaengigkeit, pyproject).
- CI (GitHub Actions, ci.yml): pytest ueber das gesamte Repo inklusive
  der neuen Dateien; Ergebnis ist am PR-Head zu verifizieren
  (CI_PASS != PRODUCTION, SCRIPTED != INSTALLED).

## Abgrenzung (NO_DUPLICATE_SYSTEMS)

- multinode.py (lokaler Lifecycle, Stufe 1) bleibt unveraendert.
- Keine zweite Hashkette, keine zweite Signatur-Logik neben der
  deklarierten `cryptography`-Ed25519-Schicht; Kanonisierung per REUSE
  aus ledger.py.
