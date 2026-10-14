"""Offline demonstration of V91 Agathon components.

This is a local demo using synthetic example input. It does not inspect hardware,
contact external services, write a ledger, or perform real-world actions.
"""
import json

from v91 import Component1, Component2


def run_demo():
    assessment = Component1().assess(
        subject="demo-only",
        impact="no external action",
        evidence="synthetic fixture; not independently verified evidence",
    )
    allocation = Component2().allocate("demo_units", 1)
    return {
        "mode": "DEMO_ONLY",
        "external_actions_performed": False,
        "assessment": assessment,
        "resource_allocation": allocation,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, indent=2))
