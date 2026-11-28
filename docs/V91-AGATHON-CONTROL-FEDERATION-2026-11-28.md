# V91 Agathon: Federation Control Gate, Stufe 2 + 3 End-to-End (28.11.2026)

Issue: V91_Agathon #24 (naechster benannter Integrationsschritt nach
Stufe 2 PR #28 und Stufe 3 PR #29): die Registry aus Stufe 2 und der
Steueradapter aus Stufe 3 werden zu einem durchgehenden, geprueften Pfad
verbunden.

## Umfang (gebaut und getestet)

`src/v91/control_federation.py`:

- CONTROL_REQUEST_TYPE "control_request" als neuer, geschlossener
  Nachrichtentyp der Peer-Protokoll-Menge (MESSAGE_TYPES erweitert;
  bestehende Peers unberuehrt, Pruefung bleibt teilmengen-basiert).
- build_control_envelope:_payload als kanonisches JSON im signierten
  Body; Ueberschreitung der Body-Grenze wird fail-closed abgelehnt,
  nichts wird still gekuerzt.
- FederatedControlGate.submit: genau ein Pfad von der signierten
  Nachricht zur Ausfuehrung, in fester Reihenfolge:
  1. Stufe-2-Verifikation (Signatur, Ablauf, Widerruf, Replay, Scopes,
     Peer-Zustand) durch die PeerRegistry [REUSE];
  2. Typpruefung control_request;
  3. Body-JSON mit allen Evidenz-Pflichtfeldern;
  4. IDENTITAETSBINDUNG: body.peer_id muss der verifizierten
     envelope-Identitaet entsprechen (kein Steuern fuer andere);
  5. Delegation an den Stufe-3-Adapter [REUSE], der Policy-Grant und
     zweiphasiges Audit selbstaendig anwendet (KEINE zweite Wahrheit).
- Journal: jede Federation-Ablehnung erzeugt einen
  control:federation:abgelehnt-Eintrag, jede Weiterleitung einen
  control:federation:verifiziert-Eintrag VOR der Delegation. Kaputtes
  Journal => Ausnahme, NICHTS wird ausgefuehrt (fail-closed).

`tests/test_control_federation.py`: 17 Tests, u.a. echter End-to-End-
Zyklus (pause/isolate/restore) mit echtem HashChainAuditLogger, Replay,
Scope-Eskalation, Identity-Binding, defekter Journal fail-loud,
VERIFICATION != AUTHORIZATION (verifiziert ohne Grant => keine
Ausfuehrung), Nicht-ASCII/Netz-Primitive-Sonden und eine
Faehigkeitsprobe fuer den echten Ed25519-Pfad (laeuft in CI, ueberspringt
ehrlich bei nicht funktionaler Umgebung).

## Regeln, die hier verbindlich bleiben

- SIGNATURE != TRUTH: eine gueltige Signatur beweist Schluesselbesitz,
  nicht die Wahrheit der Payload-Evidenz.
- ACCEPTED != EXECUTED und VERIFICATION != AUTHORIZATION: verifiziert
  heisst noch nicht berechtigt; ohne expliziten Policy-Grant passiert
  nichts (kein Default-Grant).
- ENTSCHEIDUNG != VOLLZUG: gesteuert werden ausdruecklich nur
  prozessinterne TEST-Komponenten; echte Systeme brauchen je Aktion
  eine Betreiber-Allowlist (FREIGABE != BERECHTIGUNG).
- Kein Netz, kein Discovery, kein Remote-Code; transportneutral.

## Ehrliche Grenzen

- DOKUMENTIERT != INSTALLIERT: der Gate ist Bibliotheks- und Testcode;
  ein echter Transport (Sockets, Message Queues) und echte Peers
  bleiben NICHT_GEPRUEFT bis 2. Hardware (#103).
- Die Stage-3-Adapter-Seite steuert bewusst keine echten Prozesse
  (vgl. V91-AGATHON-STEUERADAPTER-2026-11-28.md).
