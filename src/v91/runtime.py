"""Small, explicit integration boundary for V91 Agathon.

This module intentionally does not connect to external systems. Callers must
provide and validate any integration source themselves.
"""
from typing import Any


class V91Runtime:
    """Minimal runtime boundary; no external actions are performed."""

    def integrate(self, source: Any) -> bool:
        """Accept a non-None source reference without activating it.

        Returns True when a source reference is present. This is a structural
        check only, not proof that the source is reachable or trusted.
        """
        return source is not None

    def process_data(self, data: Any) -> Any:
        """Return input unchanged; transformation is not implemented."""
        return data
