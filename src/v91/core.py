"""Executable core components for V91 Agathon.

These small, deterministic helpers provide a working API for the documented
conflict-assessment and resource-governance concepts. They do not take external
actions or make authorization decisions.
"""
from dataclasses import dataclass, field
from math import isfinite
from typing import Any


@dataclass
class Component1:
    """Record and summarize a conflict assessment."""

    assessments: list[dict[str, Any]] = field(default_factory=list)

    def assess(self, subject: str, impact: str, evidence: str) -> dict[str, str]:
        """Record an assessment; evidence must be supplied explicitly."""
        for field_name, value in (("subject", subject), ("impact", impact), ("evidence", evidence)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
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
        if not isinstance(resource, str) or not resource.strip():
            raise ValueError("resource must be a non-empty string")
        name = resource.strip()
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("amount must be a number")
        if not isfinite(float(amount)):
            raise ValueError("amount must be finite")
        if amount < 0:
            raise ValueError("amount must be non-negative")
        self.allocations[name] = float(amount)
        return {"resource": name, "amount": float(amount)}

    def total_allocated(self) -> float:
        """Return the sum of recorded allocations."""
        return sum(self.allocations.values())
