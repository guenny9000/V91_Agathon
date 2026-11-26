import pytest

from v91.multinode import MultiNodeOrchestrator, NodeLifecycleError
from v91.pipeline import SemgrepIntegrator


def test_semgrep_placeholder_imports_but_never_claims_a_scan():
    integrator = SemgrepIntegrator()
    assert isinstance(integrator.available(), bool)
    with pytest.raises(NotImplementedError, match="no scan was executed"):
        integrator.integrate()
    with pytest.raises(NotImplementedError, match="no policy was generated"):
        integrator.generate_policy()


class FakeLocalNode:
    def __init__(self, name, events, *, fail_start=False, fail_stops=0):
        self.name = name
        self.events = events
        self.fail_start = fail_start
        self.fail_stops = fail_stops

    def start(self):
        self.events.append((self.name, "start"))
        if self.fail_start:
            raise RuntimeError(f"{self.name} start failed")

    def stop(self):
        self.events.append((self.name, "stop"))
        if self.fail_stops:
            self.fail_stops -= 1
            raise RuntimeError(f"{self.name} stop failed")


def test_multinode_registration_is_local_and_lifecycle_is_explicit():
    events = []
    orchestrator = MultiNodeOrchestrator()
    first = FakeLocalNode("first", events)
    second = FakeLocalNode("second", events)

    orchestrator.add_node(first)
    orchestrator.add_node(second)
    assert orchestrator.nodes == [first, second]
    assert events == []  # Registration has no side effects.

    orchestrator.start()
    assert events == [("first", "start"), ("second", "start")]
    assert orchestrator.active_nodes == (first, second)

    orchestrator.stop()
    assert events[-2:] == [("second", "stop"), ("first", "stop")]
    assert orchestrator.active_nodes == ()


def test_multinode_start_and_stop_are_idempotent():
    events = []
    orchestrator = MultiNodeOrchestrator()
    node = FakeLocalNode("node", events)
    orchestrator.add_node(node)

    orchestrator.start()
    orchestrator.start()
    orchestrator.stop()
    orchestrator.stop()

    assert events == [("node", "start"), ("node", "stop")]


def test_multinode_start_failure_rolls_back_in_reverse_order():
    events = []
    orchestrator = MultiNodeOrchestrator()
    first = FakeLocalNode("first", events)
    failing = FakeLocalNode("failing", events, fail_start=True)
    orchestrator.add_node(first)
    orchestrator.add_node(failing)

    with pytest.raises(NodeLifecycleError) as caught:
        orchestrator.start()

    assert caught.value.operation == "start"
    assert len(caught.value.failures) == 1
    assert events == [
        ("first", "start"),
        ("failing", "start"),
        ("failing", "stop"),
        ("first", "stop"),
    ]
    assert orchestrator.active_nodes == ()


def test_multinode_stop_attempts_all_nodes_and_can_retry_failure():
    events = []
    orchestrator = MultiNodeOrchestrator()
    first = FakeLocalNode("first", events)
    second = FakeLocalNode("second", events, fail_stops=1)
    orchestrator.add_node(first)
    orchestrator.add_node(second)
    orchestrator.start()

    with pytest.raises(NodeLifecycleError) as caught:
        orchestrator.stop()

    assert caught.value.operation == "stop"
    assert len(caught.value.failures) == 1
    assert orchestrator.active_nodes == (second,)
    orchestrator.stop()
    assert orchestrator.active_nodes == ()
    assert events[-2:] == [("first", "stop"), ("second", "stop")]


def test_multinode_rejects_missing_or_invalid_nodes_and_duplicates():
    orchestrator = MultiNodeOrchestrator()
    with pytest.raises(ValueError, match="must not be None"):
        orchestrator.add_node(None)
    with pytest.raises(TypeError, match="start"):
        orchestrator.add_node(object())

    events = []
    node = FakeLocalNode("node", events)
    orchestrator.add_node(node)
    with pytest.raises(ValueError, match="already registered"):
        orchestrator.add_node(node)
