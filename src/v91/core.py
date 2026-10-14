"""Declarative learning-block metadata, not an autonomous control implementation."""

CAP_01 = {
    "name": "Conflict Assessment & Perception",
    "purpose": "Identify stakeholder conflicts and assess their potential project impact.",
    "steps": [
        "identify stakeholders",
        "gather documented feedback",
        "assess impact",
        "record mitigation options",
    ],
}

RGM_01 = {
    "name": "Resource Governance & Management",
    "purpose": "Document resource allocation, accountability, and sustainability considerations.",
    "principles": ["accountability", "transparency", "sustainability"],
    "steps": [
        "record the resource allocation plan",
        "compare observed use against the plan",
        "record feedback and follow-up decisions",
    ],
}

__all__ = ["CAP_01", "RGM_01"]
