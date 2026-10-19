"""Local node registry placeholder; no remote node lifecycle is implemented."""

from __future__ import annotations

from typing import Any


class MultiNodeOrchestrator:
    def __init__(self) -> None:
        self.nodes: list[Any] = []

    def add_node(self, node: Any) -> None:
        if node is None:
            raise ValueError("node must not be None.")
        if any(existing is node for existing in self.nodes):
            raise ValueError("node is already registered.")
        self.nodes.append(node)

    def start(self) -> None:
        raise NotImplementedError(
            "Multi-node startup is not implemented; no remote nodes were started."
        )

    def stop(self) -> None:
        raise NotImplementedError(
            "Multi-node shutdown is not implemented; no remote nodes were stopped."
        )
