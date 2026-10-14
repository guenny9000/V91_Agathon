"""Semgrep policy integration interface.

This module intentionally fails loudly until a real scanner/policy adapter is
implemented. Importing the package does not imply that a scan was performed.
"""
try:
    import semgrep as _semgrep
except ImportError:
    _semgrep = None


class SemgrepIntegrator:
    def __init__(self):
        self.client = _semgrep

    def available(self):
        """Return whether the Semgrep Python package is importable."""
        return self.client is not None

    def integrate(self):
        raise NotImplementedError(
            "Semgrep integration is not implemented; no scan was executed."
        )

    def generate_policy(self):
        raise NotImplementedError(
            "Policy generation is not implemented; no policy was generated."
        )


if __name__ == "__main__":
    integrator = SemgrepIntegrator()
    raise SystemExit(
        "Semgrep integration is a placeholder. "
        f"Semgrep importable: {integrator.available()}. No scan was executed."
    )
