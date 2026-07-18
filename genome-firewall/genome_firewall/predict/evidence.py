from __future__ import annotations

from ..types import EvidenceCategory, NormalizedFinding


def classify_evidence(findings: list[NormalizedFinding], known_features: set[str]) -> tuple[EvidenceCategory, list[dict]]:
    matched = [finding for finding in findings if finding.feature_id in known_features]
    if matched:
        return EvidenceCategory.KNOWN_RESISTANCE_MARKER, [
            {"type": finding.kind, "feature_id": finding.feature_id,
             "interpretation": "configured_resistance_marker"} for finding in matched
        ]
    if findings:
        return EvidenceCategory.STATISTICAL_ASSOCIATION_ONLY, [
            {"type": finding.kind, "feature_id": finding.feature_id,
             "interpretation": "model_feature_not_curated_for_this_drug"} for finding in findings
        ]
    return EvidenceCategory.NO_KNOWN_SIGNAL, []

