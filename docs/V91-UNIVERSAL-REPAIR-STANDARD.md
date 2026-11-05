# V91 Universal Repair Standard (V91-UAPO 2.1)

Status: beschlossen 2026-11-05 durch Sebastian Günter. Gültig für alle künftigen
V91-Konzepte (Hardware, Software, Infrastruktur) und als Prüfmaßstab für
Beschaffungs- und Designentscheidungen.

## 1. Grunddirektive

**KOMPATIBILITÄT = REPARATURFÄHIGKEIT = LANGLEBIGKEIT**

- Austauschbare Komponenten statt Wegwerfgeräte.
- Genormte Akkus und Batterien (z. B. CR2032 statt fest verbauter Spezialzellen).
- Zugängliche BIOS-Batterien und standardisierte Anschlüsse – nicht versteckt
  unter Grafikkarten oder Kühlkörpern verbaut.
- Wiederverwendung statt unnötiger Neuanschaffung.
- Offene Standards statt künstlicher Herstellerabhängigkeit (Vendor Lock-in).
- Reparatur ohne unnötige Spezialwerkzeuge.
- Sicherheitsupdates auch für langlebige Geräte.

## 2. V91-Prüfkriterien

| Kennzahl | Ziel |
| --- | --- |
| Reparierbarkeit | Maximieren |
| Ersatzteilverfügbarkeit | Langfristig sichern |
| Herstellerabhängigkeit | Minimieren |
| Elektroschrott | Reduzieren |
| Energieverbrauch | Minimieren |
| Rückwärtskompatibilität | Erhalten |
| Datensicherheit | Nicht verschlechtern |

## 3. V91-Langlebigkeitsprüfung (Pflichtfragen für jedes neue Konzept)

1. Kann man es reparieren?
2. Kann man Einzelteile ohne Zerstörung anderer Komponenten austauschen?
3. Gibt es offene Standards?
4. Kann es mit älteren Komponenten weiterarbeiten?
5. Werden Energie und Rohstoffe eingespart?
6. Entsteht durch die Verbesserung keine neue Sicherheitslücke?

Keine künstliche Obsoleszenz. Keine unnötige Ressourcenverschwendung.

## 4. Typischer Verstoss (Negativbeispiel, real verbreitet)

Fest verlötete oder unzugänglich verbaute BIOS-Knopfzellen auf Mainboards.
Bei Spannungsabfall nach Jahren muss das halbe System zerlegt werden, statt
eine genormte, leicht zugängliche Zelle (CR2032 im Sockel) zu tauschen.
So ein Design scheitert an Prüfkriterien 1, 2 und 3 und ist für V91-Zwecke
als Fehlkonstruktion einzustufen.

## 5. Geltungsbereich

Computer, Smartphones, Haushaltsgeräte, Energiespeicher und Infrastruktur.
Der Standard ist ein Bewertungsmaßstab, kein erzwungenes Zertifizierungsverfahren:
Er entscheidet, was V91 als "gutes Design" anerkennt und fördert.

Leitsatz: **Nicht ständig neu bauen. Das Vorhandene intelligenter, langlebiger
und besser machen.**
