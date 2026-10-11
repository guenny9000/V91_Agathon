from v91 import Component1, Component2


def test_conflict_assessment_requires_explicit_evidence():
    component = Component1()
    record = component.assess("deployment", "medium", "review note #17")
    assert record["subject"] == "deployment"
    assert component.list_assessments() == [record]


def test_conflict_assessment_rejects_missing_evidence():
    component = Component1()
    try:
        component.assess("deployment", "medium", " ")
    except ValueError:
        pass
    else:
        raise AssertionError("empty evidence must be rejected")


def test_resource_allocation_and_total():
    component = Component2()
    component.allocate("cpu", 2)
    component.allocate("memory_gb", 4.5)
    assert component.total_allocated() == 6.5


def test_resource_allocation_rejects_negative_amount():
    component = Component2()
    try:
        component.allocate("cpu", -1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative allocation must be rejected")
