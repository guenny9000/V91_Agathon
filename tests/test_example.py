from examples.simple_pipeline import run_demo


def test_demo_is_explicitly_local_and_non_operational():
    result = run_demo()
    assert result["mode"] == "DEMO_ONLY"
    assert result["external_actions_performed"] is False
    assert "synthetic fixture" in result["assessment"]["evidence"]
    assert result["resource_allocation"]["amount"] == 1.0
