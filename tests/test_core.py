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



def test_assessment_rejects_non_string_fields():
    component = Component1()
    for field_value in [None, 1, "   "]:
        try:
            component.assess(field_value, "impact", "evidence")
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid subject accepted: {field_value!r}")


def test_allocation_rejects_non_finite_numbers():
    component = Component2()
    for amount in [float("nan"), float("inf"), float("-inf")]:
        try:
            component.allocate("cpu", amount)
        except ValueError:
            pass
        else:
            raise AssertionError(f"non-finite allocation accepted: {amount!r}")


def test_allocation_rejects_non_string_resource():
    component = Component2()
    for resource in [None, 1, "   "]:
        try:
            component.allocate(resource, 1)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid resource name accepted: {resource!r}")
