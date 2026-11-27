#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests fuer den Requirements-Audit (Issue #26).

Pinnt die Audit-Evidenz: requirements.txt enthaelt NUR die in
pyproject.toml deklarierte Laufzeit-Abhaengigkeit; die entfernten
Pakete Flask/requests/SQLAlchemy kommen nicht still zurueck.
AUDIT-PI != DAUERGARANTIE: neue Pflicht-Abhaengigkeiten werden
zuerst in pyproject.toml deklariert und von diesen Tests dann
mitgepinnt (keine schleichende Aufweichung nach unten).
"""
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
PYPROJECT = ROOT / "pyproject.toml"
ENTFERNT = ("flask", "requests", "sqlalchemy")


def _normalisiere(pakete):
    return {
        name.strip().lower().replace("_", "-"): spec.strip()
        for name, spec in pakete.items()
    }


def _requirements_pakete():
    pakete = {}
    for zeile in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        name, _, spec = zeile.partition(">=")
        pakete[name] = (">=" + spec) if spec else ""
    return _normalisiere(pakete)


def _pyproject_pakete():
    with PYPROJECT.open("rb") as handle:
        daten = tomllib.load(handle)
    pakete = {}
    for eintrag in daten["project"]["dependencies"]:
        name, _, rest = eintrag.partition(">=")
        pakete[name] = (">=" + rest) if rest else ""
    return _normalisiere(pakete)


def test_dateien_vorhanden():
    assert REQUIREMENTS.is_file()
    assert PYPROJECT.is_file()


def test_requirements_deckungsgleich_mit_metadaten():
    req = _requirements_pakete()
    proj = _pyproject_pakete()
    assert req, "requirements.txt muss mindestens eine Zeile tragen"
    assert set(req) == set(proj), (
        "requirements.txt und pyproject.toml weichen ab: "
        "nur-metadaten=%r requirements=%r" % (proj, req)
    )
    assert req == proj, "Versionsspezifikationen weichen ab: %r != %r" % (req, proj)


def test_entfernte_pakete_bleiben_entfernt():
    req = _requirements_pakete()
    for name in ENTFERNT:
        assert name not in req, "still wieder eingefuegt: " + name


def test_kommentar_dokumentiert_audit_und_messung():
    text = REQUIREMENTS.read_text(encoding="utf-8")
    assert "Issue #26" in text
    assert "2,248,359" in text       # gemessene Direkt-Wheel-Summe
    assert "973,637" in text        # gemessene transitive Wheel-Summe
    assert "3,221,996" in text      # gemessene Gesamtsumme
    assert "NICHT_GEPRUEFT" in text # Zeitmessung bleibt ehrlich offen
