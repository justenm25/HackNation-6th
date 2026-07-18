"""
Backend <-> Frontend CONTRACT for Genome Firewall.

This is the single interface both sides build against. The frontend only ever
sees objects shaped like `GenomeResult`. The ML/backend team's only job is to
make `predict_genome(...)` (in pipeline.py) return one of these for real.

Everything here is plain dataclasses so it serialises cleanly to JSON if we
later add a FastAPI/React path (asdict()).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class Verdict(str, Enum):
    WORK = "likely_to_work"      # antibiotic likely to be effective (susceptible)
    FAIL = "likely_to_fail"      # antibiotic likely ineffective (resistant)
    NO_CALL = "no_call"          # not enough / conflicting evidence -> abstain


class EvidenceCategory(str, Enum):
    KNOWN_GENE = "known_gene"        # (i)  curated resistance gene/mutation for THIS drug -> high trust
    STATISTICAL = "statistical"      # (ii) model leaned on a feature that is NOT a known cause -> flag
    NO_SIGNAL = "no_signal"          # (iii) nothing found -> lean to no-call / target gate


@dataclass
class SupportingGene:
    """One piece of cited evidence detected by AMRFinderPlus."""
    symbol: str                 # e.g. "blaKPC-2" or point mutation "gyrA_S83L"
    element_name: str           # human-readable description
    method: str                 # EXACT / ALLELE / BLAST / HMM / POINT / PARTIAL
    drug_class: str             # e.g. "BETA-LACTAM"
    subclass: str               # e.g. "CARBAPENEM"
    is_known_cause: bool        # True if curated as a cause for the predicted drug


@dataclass
class DrugPrediction:
    drug: str                           # e.g. "Meropenem"
    drug_class: str                     # e.g. "Carbapenem"
    target: str                         # molecular target, e.g. "penicillin-binding proteins"
    target_present: bool                # deterministic gate: is the target even present?
    verdict: Verdict
    confidence: Optional[float]         # calibrated point estimate 0..1 ; None when NO_CALL
    calibrated: bool                    # were probabilities calibrated?
    evidence_category: EvidenceCategory
    supporting_genes: list[SupportingGene] = field(default_factory=list)
    no_call_reason: Optional[str] = None    # e.g. "novel lineage (out-of-distribution)"
    reasoning: str = ""                     # plain-language explanation (OpenAI-generated)
    ci_low: Optional[float] = None          # calibrated confidence interval, lower bound
    ci_high: Optional[float] = None         # calibrated confidence interval, upper bound


@dataclass
class DrugMetrics:
    """Per-drug honest performance, shown in the Model Honesty tab."""
    drug: str
    balanced_acc_random: float          # inflated random-split number (for the honesty comparison)
    balanced_acc_grouped: float         # the real, grouped/phylo-split number
    recall_resistant: float
    recall_susceptible: float
    f1: float
    auroc: float
    pr_auc: float
    brier: float
    no_call_rate: float
    accuracy_on_calls: float


@dataclass
class GenomeResult:
    genome_id: str
    species: str
    species_supported: bool             # is this one of our covered species?
    novelty_score: float                # 0..1 ; distance from training distribution
    is_ood: bool                        # out-of-distribution flag (drives no-calls)
    mlst_or_cluster: Optional[str]      # sequence type / cluster id if known
    detected_genes: list[SupportingGene]
    predictions: list[DrugPrediction]
    speed_seconds: float                # first-signal -> decision timer
    model_meta: dict = field(default_factory=dict)  # versions, thresholds, etc.

    def to_dict(self) -> dict:
        return asdict(self)


# ---- Static config the frontend can trust ----------------------------------
SUPPORTED_SPECIES = "Klebsiella pneumoniae"

SUPPORTED_DRUGS = ["Meropenem", "Ceftazidime", "Ciprofloxacin",
                   "Gentamicin", "Amikacin", "Tigecycline"]

DISCLAIMER = (
    "Research prototype. Every antibiotic-response result MUST be confirmed by "
    "standard laboratory testing. This is decision support only and must never "
    "make a treatment decision on its own."
)

COVERAGE_NOTE = (
    f"Covers ONE species ({SUPPORTED_SPECIES}) and {len(SUPPORTED_DRUGS)} antibiotics "
    f"({', '.join(SUPPORTED_DRUGS)}). All other species and drugs are out of coverage "
    f"and will return a no-call."
)

DEFENSIVE_NOTE = (
    "Defensive by construction: this tool only predicts and explains resistance that "
    "already exists, to support faster targeted treatment and public-health tracking. "
    "It never designs, modifies, strengthens, or optimizes any organism."
)
