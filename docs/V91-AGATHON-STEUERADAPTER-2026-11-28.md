# V91 Agathon: Autorisierter Steuerungsadapter, Stufe 3 (28.11.2026)

Issue: V91_Agathon #24 Zielstufe 3 (autorisierter Steuerungsadapter)
bzw. v91-core-system Issue #592 Abnahmekriterium 2 auf der Laufzeitseite:
ein autorisierter Adapter kann eine Testkomponente pausieren/isolieren
und ueber definierten Rollback wiederherstellen; unautorisierte
Aktionen werden fail-closed abgewiesen.

## Umfang (gebaut und getestet)

`src/v91/control_adapter.py`:

- STEUERAKTIONEN: pause, resume, isolate, restore. Bewusst KEINE
  zerstoerenden Aktionen: ABSCHALTEN == ISOLIEREN, ISOLATE_NOT_DESTROY.
- TestComponent: explizit lokale, prozessinterne Testkomponente mit
  Zustand (LAUFEND/PAUSIERT/ISOLIERT), Payload und Snapshot je
  Kontrollpunkt. Restore ist echter Rollback auf den letzten Snapshot.
- ControlPolicy: explizite Grants je (peer, komponente) -> Aktionsmenge;
  Wildcards ("*") und unbekannte Aktionen werden bei der Konstruktion
  abgelehnt; leere Policy gewaehrt nichts (fail-closed default).
- ControlRequest: Pflichtfelder je Aktion: Identitaet (peer_id), Ziel,
  Aktion, policy_version, ausloesekriterium, belege (nicht-leer),
  rollback_plan, wirkungsradius. Fehlende Evidenz = ABGELEHNT.
- AuthorizedControlAdapter: prueft Reihenfolge strukturiert (unvollstaendig
  -> unbekannte Komponente -> unbekannte Aktion -> keine Berechtigung ->
  kein gueltiger Uebergang -> Ausfuehrung), fuehrt nur mit explizitem
  Grant aus, isoliert Komponentenfehler (andere Komponenten bleiben
  steuerbar), und journalisiert ZWEIPHASIG:
  1. control:autorisiert:<aktion> VOR der Ausfuehrung (kaputtes Journal
     => Ausnahme, NICHTS wird ausgefuehrt, fail-closed),
  2. control:ausgefuehrt:<aktion> danach (bei Versagen bleibt der
     Autorisierungseintrag, der Fehler ist laut, Teiljournal ehrlich).
  Ablehnungen werden als control:abgelehnt mit Grund journaliert;
  unidentifizierte Requester werden als UNBEKANNTER_PEER bezeichnet
  (BEZEICHNUNG != IDENTITAET).

`tests/test_control_adapter.py`: 14 Tests, self-contained, als plain
functions auch ohne pytest lauffaehig. REUSE-Nachweis: das Audit-Journal
in den Tests ist der ECHTE HashChainAuditLogger (src/v91/audit.py),
verify_chain() prueft die Kette am Ende. Negativtest verriegelt die
Abwesenheit von socket/subprocess/urllib/requests/eval/exec/os.system.

## Was bewusst NICHT behauptet wird

- ENTSCHEIDUNG != VOLLZUG: gesteuert werden NUR explizit registrierte
  Testkomponenten im eigenen Prozess. Echte externe Systeme brauchen
  echte Adapter und eine Betreiber-Allowlist je Aktion und je Ziel
  (FREIGABE != BERECHTIGUNG; jede reale Aktion einzeln).
- Kein Netz, kein Remote-Code, keine automatische Rechteausweitung.
- ROLLEN != CODE: die Core-Vertragspruefung
  (controller/verbund_arbeitszyklus.py, pruefe_steueraktion) bleibt die
  massgebliche Verbund-Entscheidungsschicht; dieser Adapter dupliziert
  sie nicht, sondern setzt lokal um (Laufzeitseite).
- KEIN Produktions- oder Weltwirkungsclaim: Scripted != Installed,
  CI_PASS != PRODUCTION.

## Nachweisgrenzen

- Lokale Verifikation (28.11.2026, Vibe-Sandbox): compileall OK, 14/14
  Testfunktionen PASS gegen echtes audit.py (stdlib-only). cryptography
  wird von diesem Modul NICHT benoetigt.
- CI (ci.yml): pytest ueber das gesamte Repo; Ergebnis am PR-Head am
  exakten SHA zu verifizieren.
