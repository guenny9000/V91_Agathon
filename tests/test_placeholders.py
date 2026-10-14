import pytest

from v91.multinode import MultiNodeOrchestrator
from v91.pipeline import SemgrepIntegrator


def test_semgrep_placeholder_imports_but_never_claims_a_scan():
    integrator = SemgrepIntegrator()
    assert isinstance(integrator.available(), bool)
    with pytest.raises(NotImplementedError, match="no scan was executed"):
        integrator.integrate()
    with pytest.raises(NotImplementedError, match="no policy was generated"):
        integrator.generate_policy()


def test_multinode_registration_is_local_and_lifecycle_is_not_implemented():
    orchestrator = MultiNodeOrchestrator()
    node = object()
    orchestrator.add_node(node)
    assert orchestrator.nodes == [node]
    with pytest.raises(NotImplementedError, match="not implemented"):
        orchestrator.start()
    with pytest.raises(NotImplementedError, match="not implemented"):
        orchestrator.stop()


def test_multinode_rejects_missing_node():
    with pytest.raises(ValueError, match="must not be None"):
        MultiNodeOrchestrator().add_node(None)
