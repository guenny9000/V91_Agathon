"""Minimal data pass-through adapter; external integrations remain unimplemented."""
from __future__ import annotations

from typing import Any


class V91Runtime:
    def integrate(self, source: Any) -> None:
        if source is None:
            raise ValueError("source must not be None.")
        raise NotImplementedError(
            "External source integration is not implemented; no connection was attempted."
        )

    def process_data(self, data: Any) -> Any:
        """Return the input unchanged; this method performs no hidden transformation."""
        return data
