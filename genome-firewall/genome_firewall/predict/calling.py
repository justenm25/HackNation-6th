from __future__ import annotations

from ..types import Call, EvidenceCategory


def decide_call(probability: float, *, resistant_threshold: float, susceptible_threshold: float,
                evidence_category: EvidenceCategory, marker_free_susceptible_policy: str = "conservative",
                intrinsic_rule: dict | None = None, warnings: list[str] | None = None) -> tuple[Call, str, list[str]]:
    if intrinsic_rule:
        return Call.LIKELY_TO_FAIL, "intrinsic_rule", []
    if warnings:
        return Call.NO_CALL, "abstention_policy", ["input_or_schema_warning"]
    if probability >= resistant_threshold:
        return Call.LIKELY_TO_FAIL, "model_and_evidence", []
    if probability <= susceptible_threshold:
        if marker_free_susceptible_policy == "validated_low_risk" and evidence_category != EvidenceCategory.KNOWN_RESISTANCE_MARKER:
            return Call.LIKELY_TO_WORK, "calibrated_model", []
        return Call.NO_CALL, "abstention_policy", ["absence_of_resistance_markers_does_not_establish_susceptibility"]
    reasons = ["calibrated_probability_within_no_call_band"]
    if evidence_category == EvidenceCategory.KNOWN_RESISTANCE_MARKER:
        reasons.append("known_marker_conflicts_with_model_probability")
    return Call.NO_CALL, "abstention_policy", reasons

