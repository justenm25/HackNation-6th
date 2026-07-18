"""
MOCK backend for Genome Firewall.

The frontend imports `predict_genome`, `list_samples`, and `get_model_metrics`
from here. They return hand-built, realistic data so the UI can be fully built and
demoed BEFORE the real model exists.

ML/backend team: replace the bodies of `predict_genome` and `get_model_metrics`
with the real pipeline (AMRFinderPlus -> features -> calibrated per-drug models).
Keep the return TYPES identical (see contract.py) and the frontend needs no changes.
"""
from __future__ import annotations
import time
from .contract import (
    Verdict, EvidenceCategory, SupportingGene, DrugPrediction,
    DrugMetrics, GenomeResult, SUPPORTED_SPECIES, SUPPORTED_DRUGS,
)

# Auto-upgrade: once real models are trained (models/artifacts/), use them.
try:
    from src import model as _real
except Exception:
    _real = None


def _use_real() -> bool:
    return _real is not None and _real.is_ready()

# ------------------------------------------------------------------ evidence
_KPC = SupportingGene("blaKPC-2", "carbapenem-hydrolyzing class A beta-lactamase KPC-2",
                      "EXACT", "BETA-LACTAM", "CARBAPENEM", True)
_CTXM = SupportingGene("blaCTX-M-15", "extended-spectrum class A beta-lactamase CTX-M-15",
                       "EXACT", "BETA-LACTAM", "CEPHALOSPORIN", True)
_GYRA = SupportingGene("gyrA_S83L", "fluoroquinolone resistance point mutation gyrA S83L",
                       "POINT", "QUINOLONE", "FLUOROQUINOLONE", True)
_AAC = SupportingGene("aac(3)-IIa", "aminoglycoside N-acetyltransferase",
                      "EXACT", "AMINOGLYCOSIDE", "GENTAMICIN", True)
_OQXA = SupportingGene("oqxA", "efflux pump membrane-fusion protein (broad, non-specific)",
                       "BLAST", "MULTIDRUG", "EFFLUX", False)


def _pred(drug, dclass, target, target_present, verdict, conf, ci, cat, genes,
          reason_txt, no_call_reason=None):
    lo, hi = (None, None) if ci is None else ci
    return DrugPrediction(
        drug=drug, drug_class=dclass, target=target, target_present=target_present,
        verdict=verdict, confidence=conf, calibrated=True, evidence_category=cat,
        supporting_genes=genes, no_call_reason=no_call_reason, reasoning=reason_txt,
        ci_low=lo, ci_high=hi,
    )


# ------------------------------------------------------------------ samples
def _sample_mixed():
    """One isolate that exercises every call state — the look-locking demo."""
    return GenomeResult(
        genome_id="573.30001", species=SUPPORTED_SPECIES, species_supported=True,
        novelty_score=0.19, is_ood=False, mlst_or_cluster="ST258",
        detected_genes=[_KPC, _CTXM, _GYRA, _OQXA],
        predictions=[
            _pred("Meropenem", "Carbapenem", "penicillin-binding proteins", True,
                  Verdict.FAIL, 0.96, (0.92, 0.98), EvidenceCategory.KNOWN_GENE, [_KPC],
                  "blaKPC-2 (exact match) produces a carbapenemase that hydrolyses meropenem. "
                  "Known causal mechanism — narrow, high-confidence interval."),
            _pred("Ceftazidime", "Cephalosporin", "penicillin-binding proteins", True,
                  Verdict.FAIL, 0.92, (0.86, 0.96), EvidenceCategory.KNOWN_GENE, [_CTXM, _KPC],
                  "ESBL blaCTX-M-15 plus KPC confer cephalosporin resistance. Known mechanism."),
            _pred("Ciprofloxacin", "Fluoroquinolone", "DNA gyrase / topoisomerase IV", True,
                  Verdict.FAIL, 0.88, (0.79, 0.93), EvidenceCategory.KNOWN_GENE, [_GYRA],
                  "gyrA S83L point mutation alters the fluoroquinolone target. Known mechanism."),
            _pred("Gentamicin", "Aminoglycoside", "30S ribosomal subunit", True,
                  Verdict.WORK, 0.83, (0.71, 0.91), EvidenceCategory.NO_SIGNAL, [],
                  "No aminoglycoside-modifying enzyme detected and the target is present "
                  "(target gate passed). Wider interval reflects reliance on absence of signal."),
            _pred("Amikacin", "Aminoglycoside", "30S ribosomal subunit", True,
                  Verdict.NO_CALL, None, None, EvidenceCategory.STATISTICAL, [_OQXA],
                  "Only a broad efflux marker (oqxA) is present — statistically associated with "
                  "resistance but NOT a curated cause for amikacin. Withholding is safer than guessing.",
                  no_call_reason="Evidence is a statistical association only, not a known mechanism"),
            _pred("Tigecycline", "Glycylcycline", "30S ribosomal subunit", True,
                  Verdict.NO_CALL, None, None, EvidenceCategory.NO_SIGNAL, [],
                  "No known tigecycline determinant, and this drug is sparsely represented in "
                  "training for this lineage. Confidence too low to call.",
                  no_call_reason="Weak / insufficient evidence for a calibrated call"),
        ],
        speed_seconds=1.8, model_meta={"model": "MOCK", "grouped_split": True},
    )


def _sample_susceptible():
    """A susceptible isolate: no resistance determinants, target present -> WORK."""
    def w(drug, dclass, target, conf, ci):
        return _pred(drug, dclass, target, True, Verdict.WORK, conf, ci,
                     EvidenceCategory.NO_SIGNAL, [],
                     "No resistance determinant detected and the drug target is present "
                     "(target gate passed).")
    return GenomeResult(
        genome_id="573.30002", species=SUPPORTED_SPECIES, species_supported=True,
        novelty_score=0.24, is_ood=False, mlst_or_cluster="ST45",
        detected_genes=[],
        predictions=[
            w("Meropenem", "Carbapenem", "penicillin-binding proteins", 0.90, (0.82, 0.95)),
            w("Ceftazidime", "Cephalosporin", "penicillin-binding proteins", 0.86, (0.77, 0.92)),
            w("Ciprofloxacin", "Fluoroquinolone", "DNA gyrase / topoisomerase IV", 0.81, (0.70, 0.89)),
            w("Gentamicin", "Aminoglycoside", "30S ribosomal subunit", 0.84, (0.74, 0.91)),
            w("Amikacin", "Aminoglycoside", "30S ribosomal subunit", 0.82, (0.71, 0.90)),
            w("Tigecycline", "Glycylcycline", "30S ribosomal subunit", 0.79, (0.67, 0.88)),
        ],
        speed_seconds=1.5, model_meta={"model": "MOCK", "grouped_split": True},
    )


def _sample_novel():
    """Out-of-distribution genome: most calls withheld."""
    def nc(drug, dclass, target, reason, cat=EvidenceCategory.NO_SIGNAL, genes=None):
        return _pred(drug, dclass, target, True, Verdict.NO_CALL, None, None, cat,
                     genes or [],
                     "Genome is unlike anything in the training set; a prediction here would "
                     "not be trustworthy.", no_call_reason=reason)
    return GenomeResult(
        genome_id="573.30003", species=SUPPORTED_SPECIES, species_supported=True,
        novelty_score=0.88, is_ood=True, mlst_or_cluster="novel (no close cluster)",
        detected_genes=[_OQXA],
        predictions=[
            nc("Meropenem", "Carbapenem", "penicillin-binding proteins", "Out-of-distribution genome"),
            nc("Ceftazidime", "Cephalosporin", "penicillin-binding proteins", "Out-of-distribution genome"),
            nc("Ciprofloxacin", "Fluoroquinolone", "DNA gyrase / topoisomerase IV",
               "Out-of-distribution + statistical evidence only",
               EvidenceCategory.STATISTICAL, [_OQXA]),
            _pred("Gentamicin", "Aminoglycoside", "30S ribosomal subunit", True,
                  Verdict.WORK, 0.66, (0.51, 0.79), EvidenceCategory.NO_SIGNAL, [],
                  "No modifying enzyme detected; target present. Confidence tempered by novelty."),
            nc("Amikacin", "Aminoglycoside", "30S ribosomal subunit", "Out-of-distribution genome"),
            nc("Tigecycline", "Glycylcycline", "30S ribosomal subunit", "Out-of-distribution genome"),
        ],
        speed_seconds=1.9, model_meta={"model": "MOCK", "grouped_split": True},
    )


_SAMPLES = {
    "Klebsiella pneumoniae — mixed calls (573.30001)": _sample_mixed,
    "Klebsiella pneumoniae — susceptible (573.30002)": _sample_susceptible,
    "Klebsiella pneumoniae — novel lineage, withheld (573.30003)": _sample_novel,
}


def list_samples() -> list[str]:
    if _use_real():
        return _real.list_samples()
    return list(_SAMPLES.keys())


def predict_genome(source, species: str = SUPPORTED_SPECIES,
                   sample_name: str | None = None) -> GenomeResult:
    """
    MOCK. In production: parse FASTA `source` -> AMRFinderPlus -> features ->
    per-drug calibrated models -> GenomeResult.
    """
    if _use_real():
        return _real.predict_genome(source, species=species, sample_name=sample_name)
    time.sleep(0.4)
    if sample_name and sample_name in _SAMPLES:
        return _SAMPLES[sample_name]()

    if species and species.strip().lower() != SUPPORTED_SPECIES.lower():
        return GenomeResult(
            genome_id="uploaded", species=species, species_supported=False,
            novelty_score=1.0, is_ood=True, mlst_or_cluster=None, detected_genes=[],
            predictions=[
                _pred(d, "-", "-", False, Verdict.NO_CALL, None, None,
                      EvidenceCategory.NO_SIGNAL, [],
                      "Species is outside the model's coverage. No prediction made.",
                      no_call_reason="Unsupported species")
                for d in SUPPORTED_DRUGS
            ],
            speed_seconds=0.6, model_meta={"model": "MOCK"},
        )

    r = _sample_mixed()
    r.genome_id = "uploaded genome"
    return r


def get_model_metrics() -> list[DrugMetrics]:
    """MOCK held-out metrics. The random-vs-grouped gap is the honesty story."""
    if _use_real():
        return _real.get_model_metrics()
    return [
        DrugMetrics("Meropenem",     0.97, 0.89, 0.91, 0.88, 0.90, 0.95, 0.93, 0.08, 0.11, 0.94),
        DrugMetrics("Ceftazidime",   0.96, 0.85, 0.87, 0.84, 0.86, 0.92, 0.90, 0.10, 0.14, 0.91),
        DrugMetrics("Ciprofloxacin", 0.95, 0.82, 0.84, 0.81, 0.83, 0.90, 0.86, 0.12, 0.19, 0.90),
        DrugMetrics("Gentamicin",    0.94, 0.78, 0.79, 0.77, 0.78, 0.87, 0.82, 0.14, 0.23, 0.88),
        DrugMetrics("Amikacin",      0.93, 0.76, 0.77, 0.75, 0.76, 0.85, 0.80, 0.15, 0.26, 0.87),
        DrugMetrics("Tigecycline",   0.90, 0.71, 0.72, 0.70, 0.71, 0.81, 0.74, 0.18, 0.31, 0.85),
    ]
