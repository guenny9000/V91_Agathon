"""Multi-node orchestration interface placeholder.

Node registration is local only. Scheduling, transport, remote execution, and
lifecycle management are not implemented; start/stop therefore fail explicitly.
"""


class MultiNodeOrchestrator:
    def __init__(self):
        self.nodes = []

    def add_node(self, node):
        """Register a node object locally; this does not connect to it."""
        if node is None:
            raise ValueError("node must not be None")
        self.nodes.append(node)

    def start(self):
        raise NotImplementedError(
            "Multi-node scheduling and communication are not implemented."
        )

    def stop(self):
        raise NotImplementedError(
            "Multi-node lifecycle management is not implemented."
        )
