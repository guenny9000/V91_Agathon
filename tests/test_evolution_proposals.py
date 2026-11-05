import pytest

from v91.creative_generator import generate_ideas
from v91.self_evolution import increment_patch, run_evolution_cycles


def test_patch_increment_is_real_and_sequential():
    cycles = run_evolution_cycles("1.0.0", 3)
    assert [(c.current_version, c.proposed_version) for c in cycles] == [
        ("1.0.0", "1.0.1"),
        ("1.0.1", "1.0.2"),
        ("1.0.2", "1.0.3"),
    ]
    assert all(c.action == "ASSESSMENT_ONLY" for c in cycles)


@pytest.mark.parametrize("version", ["", "1", "v1.0.0", "01.0.0", None])
def test_invalid_version_fails_closed(version):
    with pytest.raises(ValueError):
        increment_patch(version)


@pytest.mark.parametrize("cycles", [0, -1, 101, True, 1.5, "3"])
def test_cycle_count_is_bounded(cycles):
    with pytest.raises(ValueError):
        run_evolution_cycles("1.0.0", cycles)


def test_creative_catalog_has_eight_proposals_across_four_domains():
    ideas = generate_ideas()
    assert len(ideas) == 8
    assert {idea["domain"] for idea in ideas} == {
        "general", "security", "community", "ecology"
    }
    assert all(idea["status"] == "PROPOSAL" for idea in ideas)


def test_creative_catalog_is_deterministic_and_return_value_is_isolated():
    first = generate_ideas()
    second = generate_ideas()
    assert first == second
    first[0]["title"] = "mutated by caller"
    assert generate_ideas()[0]["title"] != "mutated by caller"
