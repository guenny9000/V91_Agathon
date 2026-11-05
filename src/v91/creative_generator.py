"""Deterministic creative proposal catalog.

Ideas are suggestions, not evidence that a project has been implemented.
No network, filesystem, or production action is performed.
"""
from __future__ import annotations

from typing import TypedDict


class Idea(TypedDict):
    domain: str
    title: str
    feasibility: str
    status: str


_IDEAS: tuple[Idea, ...] = (
    {"domain": "ecology", "title": "Regional earthen-building resource map", "feasibility": "medium", "status": "PROPOSAL"},
    {"domain": "ecology", "title": "Repair and reuse material exchange", "feasibility": "high", "status": "PROPOSAL"},
    {"domain": "community", "title": "Tool and seed lending board", "feasibility": "high", "status": "PROPOSAL"},
    {"domain": "community", "title": "Consent-based volunteer matching", "feasibility": "medium", "status": "PROPOSAL"},
    {"domain": "security", "title": "Automated audit-ledger tamper tests", "feasibility": "high", "status": "PROPOSAL"},
    {"domain": "security", "title": "Credential and secret-leak checks in CI", "feasibility": "high", "status": "PROPOSAL"},
    {"domain": "general", "title": "Bounded test scheduling to reduce wasted compute", "feasibility": "medium", "status": "PROPOSAL"},
    {"domain": "general", "title": "Evidence-linked issue prioritization", "feasibility": "high", "status": "PROPOSAL"},
)


def generate_ideas() -> list[Idea]:
    """Return a fresh copy of eight deterministic proposals."""
    return [dict(idea) for idea in _IDEAS]
