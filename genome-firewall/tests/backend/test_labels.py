import pytest

from genome_firewall.exceptions import InputValidationError
from genome_firewall.labels.policy import normalize_label


def test_label_policy_is_explicit():
    assert normalize_label("R") == 1
    assert normalize_label("S") == 0
    assert normalize_label("I") is None
    assert normalize_label(None) is None
    with pytest.raises(InputValidationError):
        normalize_label("UNKNOWN")
