"""Explicitly local node registry and synchronous lifecycle coordinator.

This module does not discover peers, open sockets, execute remote code, or
provide distributed coordination. Nodes are caller-supplied local adapters
with synchronous start() and stop() methods. A failed cleanup is retained
for a later stop() retry rather than being silently forgotten.
"""
from __future__ import annotations

from typing import Any


class NodeLifecycleError(RuntimeError):
    """A lifecycle operation failed; individual node exceptions are retained."""

    def __init__(self, operation: str, failures: list[tuple[Any, Exception]]) -> None:
        self.operation = operation
        self.failures = tuple(failures)
        summary = ", ".join(type(error).__name__ for _, error in failures)
        super().__init__(
            f"Local node {operation} failed for {len(failures)} operation(s): {summary}"
        )


class MultiNodeOrchestrator:
    """Manage explicitly registered local adapters; no network is used."""

    def __init__(self) -> None:
        self.nodes: list[Any] = []
        # Includes nodes whose cleanup failed and whose state is therefore
        # unresolved. Such nodes are not started a second time.
        self._active_nodes: list[Any] = []

    @property
    def active_nodes(self) -> tuple[Any, ...]:
        """Nodes that started successfully or still require cleanup."""
        return tuple(self._active_nodes)

    @staticmethod
    def _contains_identity(items: list[Any], candidate: Any) -> bool:
        return any(item is candidate for item in items)

    def add_node(self, node: Any) -> None:
        """Register a local adapter without starting it."""
        if node is None:
            raise ValueError("node must not be None.")
        if self._contains_identity(self.nodes, node):
            raise ValueError("node is already registered.")
        if not callable(getattr(node, "start", None)) or not callable(
            getattr(node, "stop", None)
        ):
            raise TypeError("local node adapter must provide callable start() and stop().")
        self.nodes.append(node)

    def start(self) -> None:
        """Start registered local adapters in order, rolling back on failure.

        Repeated calls do not start adapters already active. If startup or
        rollback fails, the raised error preserves each original exception.
        Nodes whose rollback failed remain active/unresolved for stop() retry.
        """
        attempted: list[Any] = []
        for node in self.nodes:
            if self._contains_identity(self._active_nodes, node):
                continue
            attempted.append(node)
            try:
                node.start()
            except Exception as start_error:
                failures: list[tuple[Any, Exception]] = [(node, start_error)]
                for candidate in reversed(attempted):
                    try:
                        candidate.stop()
                    except Exception as cleanup_error:
                        failures.append((candidate, cleanup_error))
                        if not self._contains_identity(self._active_nodes, candidate):
                            self._active_nodes.append(candidate)
                    else:
                        self._active_nodes = [
                            active for active in self._active_nodes
                            if active is not candidate
                        ]
                raise NodeLifecycleError("start", failures) from start_error
            else:
                self._active_nodes.append(node)

    def stop(self) -> None:
        """Stop active adapters in reverse order, attempting every cleanup.

        Failed stops remain tracked so a later call can retry them. The method
        is idempotent when no adapter is active.
        """
        failures: list[tuple[Any, Exception]] = []
        for node in reversed(tuple(self._active_nodes)):
            try:
                node.stop()
            except Exception as error:
                failures.append((node, error))
            else:
                self._active_nodes = [
                    active for active in self._active_nodes if active is not node
                ]
        if failures:
            raise NodeLifecycleError("stop", failures)
