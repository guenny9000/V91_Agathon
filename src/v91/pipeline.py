"""Optional Semgrep adapter; never claims a scan unless one is implemented."""
from __future__ import annotations

import importlib.util


class SemgrepIntegrator:
    def available(self) -> bool:
        """Report whether the Semgrep Python package is importable."""
        return importlib.util.find_spec("semgrep") is not None

    def integrate(self) -> None:
        raise NotImplementedError("Semgrep integration is not implemented; no scan was executed.")

    def generate_policy(self) -> None:
        raise NotImplementedError("Policy generation is not implemented; no policy was generated.")
