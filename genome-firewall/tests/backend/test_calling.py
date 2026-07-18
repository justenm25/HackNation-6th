from genome_firewall.predict.calling import decide_call
from genome_firewall.types import Call, EvidenceCategory


def test_low_probability_is_no_call_under_conservative_policy():
    call, _, reasons = decide_call(0.01, resistant_threshold=0.8, susceptible_threshold=0.1,
                                   evidence_category=EvidenceCategory.NO_KNOWN_SIGNAL)
    assert call == Call.NO_CALL
    assert reasons


def test_intrinsic_rule_forces_failure():
    call, source, _ = decide_call(0.01, resistant_threshold=0.8, susceptible_threshold=0.1,
                                  evidence_category=EvidenceCategory.NO_KNOWN_SIGNAL,
                                  intrinsic_rule={"id": "rule"})
    assert call == Call.LIKELY_TO_FAIL
    assert source == "intrinsic_rule"


def test_validated_policy_can_call_work():
    call, _, _ = decide_call(0.01, resistant_threshold=0.8, susceptible_threshold=0.1,
                             evidence_category=EvidenceCategory.NO_KNOWN_SIGNAL,
                             marker_free_susceptible_policy="validated_low_risk")
    assert call == Call.LIKELY_TO_WORK

