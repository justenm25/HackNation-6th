from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class Call(str, Enum):
    LIKELY_TO_WORK = "likely_to_work"
    LIKELY_TO_FAIL = "likely_to_fail"
    NO_CALL = "no_call"


class EvidenceCategory(str, Enum):
    KNOWN_RESISTANCE_MARKER = "known_resistance_marker"
    STATISTICAL_ASSOCIATION_ONLY = "statistical_association_only"
    NO_KNOWN_SIGNAL = "no_known_signal"


@dataclass(frozen=True)
class NormalizedFinding:
    feature_id: str
    kind: str
    gene_symbol: str
    mutation: Optional[str] = None
    sequence_name: Optional[str] = None
    method: Optional[str] = None
    element_subtype: Optional[str] = None
    raw: dict[str, str] = field(default_factory=dict, compare=False)


@dataclass
class DrugPrediction:
    drug_id: str
    drug_name: str
    call: Call
    resistance_probability: float
    calibrated_confidence: Optional[float]
    confidence_semantics: str
    evidence_category: EvidenceCategory
    decision_source: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    no_call_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PredictionReport:
    schema_version: str
    report_id: str
    sample: dict[str, Any]
    analysis: dict[str, Any]
    predictions: list[DrugPrediction]
    quality: dict[str, Any]
    confirm_with_lab_testing: bool = True
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

