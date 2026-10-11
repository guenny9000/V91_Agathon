"""Executable core components for V91 Agathon.

These small, deterministic helpers provide a working API for the documented
conflict-assessment and resource-governance concepts. They do not take external
actions or make authorization decisions.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Component1:
    """Record and summarize a conflict assessment."""

    assessments: list[dict[str, Any]] = field(default_factory=list)

    def assess(self, subject: str, impact: str, evidence: str) -> dict[str, str]:
        """Record an assessment; evidence must be supplied explicitly."""
        if not subject.strip():
            raise ValueError("subject must not be empty")
        if not impact.strip():
            raise ValueError("impact must not be empty")
        if not evidence.strip():
            raise ValueError("evidence must not be empty")
        record = {
            "subject": subject.strip(),
            "impact": impact.strip(),
            "evidence": evidence.strip(),
        }
        self.assessments.append(record)
        return record

    def list_assessments(self) -> list[dict[str, str]]:
        """Return a copy so callers cannot mutate the internal list."""
        return [dict(item) for item in self.assessments]


@dataclass
class Component2:
    """Track resource allocations without performing external operations."""

    allocations: dict[str, float] = field(default_factory=dict)

    def allocate(self, resource: str, amount: float) -> dict[str, float | str]:
        """Record a non-negative allocation for a named resource."""
        name = resource.strip()
        if not name:
            raise ValueError("resource must not be empty")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("amount must be a number")
        if amount < 0:
            raise ValueError("amount must be non-negative")
        self.allocations[name] = float(amount)
        return {"resource": name, "amount": float(amount)}

    def total_allocated(self) -> float:
        """Return the sum of recorded allocations."""
        return sum(self.allocations.values())
