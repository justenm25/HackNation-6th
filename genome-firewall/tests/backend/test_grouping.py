import pytest

from genome_firewall.exceptions import LeakageError
from genome_firewall.grouping.clustering import connected_components
from genome_firewall.grouping.leakage_audit import audit_split_homology


def test_connected_components_are_transitive():
    groups = connected_components(["a", "b", "c", "d"], [("a", "b"), ("b", "c")])
    assert groups["a"] == groups["b"] == groups["c"]
    assert groups["d"] != groups["a"]


def test_cross_split_group_is_fatal():
    with pytest.raises(LeakageError):
        audit_split_homology({"a": "train", "b": "hidden_test"}, {"a": "g1", "b": "g1"})


def test_clean_groups_pass():
    result = audit_split_homology(
        {"a": "train", "b": "calibration", "c": "hidden_test"},
        {"a": "g1", "b": "g2", "c": "g3"},
    )
    assert result["passed"]

