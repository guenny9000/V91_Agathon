"""Bounded, evidence-first evolution assessments.

This module does not rewrite or execute code. It records repeatable assessment
cycles and proposed version increments; applying changes remains a separate,
reviewed operation.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


@dataclass(frozen=True)
class EvolutionCycle:
    cycle: int
    current_version: str
    proposed_version: str
    action: str = "ASSESSMENT_ONLY"


def _parse_version(version: str) -> tuple[int, int, int]:
    if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
        raise ValueError("version must be a semantic x.y.z version")
    return tuple(int(part) for part in version.split("."))


def increment_patch(version: str) -> str:
    """Return the next patch version without modifying files or project state."""
    major, minor, patch = _parse_version(version)
    return f"{major}.{minor}.{patch + 1}"


def run_evolution_cycles(version: str = "1.0.0", cycles: int = 1) -> list[EvolutionCycle]:
    """Create a bounded sequence of proposed patch versions.

    This is bookkeeping for reviewable proposals, not autonomous code mutation.
    """
    _parse_version(version)
    if isinstance(cycles, bool) or not isinstance(cycles, int) or not 1 <= cycles <= 100:
        raise ValueError("cycles must be an integer from 1 through 100")
    results: list[EvolutionCycle] = []
    current = version
    for index in range(1, cycles + 1):
        proposed = increment_patch(current)
        results.append(EvolutionCycle(index, current, proposed))
        current = proposed
    return results
