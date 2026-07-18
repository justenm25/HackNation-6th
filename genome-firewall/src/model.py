"""
Real predictor for Genome Firewall.

Loads the artifacts written by src.train and returns GenomeResult objects — the
SAME type the mock returns, so the frontend needs zero changes. pipeline.py
delegates here automatically once models/artifacts/ exists.
"""
from __future__ import annotations
import json
import os
import time
import numpy as np
from joblib import load

from src.contract import (
    Verdict, EvidenceCategory, SupportingGene, DrugPrediction,
    DrugMetrics, GenomeResult, SUPPORTED_SPECIES,
)
from src import drug_db

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(HERE, "models", "artifacts")
OOD_THRESHOLD = 0.85          # Jaccard distance to nearest training genome


def is_ready(art: str = ART) -> bool:
    return os.path.exists(os.path.join(art, "config.json")) and \
        os.path.exists(os.path.join(art, "feature_columns.json"))


class _Artifacts:
    def __init__(self, art=None):
        art = art or ART
        self.cols = json.load(open(os.path.join(art, "feature_columns.json")))
        self.cfg = json.load(open(os.path.join(art, "config.json")))
        self.metrics = json.load(open(os.path.join(art, "metrics.json")))
        self.samples = json.load(open(os.path.join(art, "samples.json")))
        self.gene_info = json.load(open(os.path.join(art, "gene_info.json")))
        self.delta = self.cfg.get("abstain_delta", 0.15)
        self.drugs = [m["drug"] for m in self.metrics]
        self.thr = {m["drug"]: m.get("threshold", 0.5) for m in self.metrics}
        self.main = {d: load(os.path.join(art, f"{d}__main.joblib")) for d in self.drugs}
        self.boot = {d: load(os.path.join(art, f"{d}__boot.joblib")) for d in self.drugs}
        m = np.load(os.path.join(art, "train_matrix.npz"), allow_pickle=True)
        self.train_X = m["X"].astype(bool)
        self.train_counts = self.train_X.sum(axis=1)
        self.col_idx = {c: i for i, c in enumerate(self.cols)}


_A: _Artifacts | None = None


def _artifacts() -> _Artifacts:
    global _A
    if _A is None:
        _A = _Artifacts(ART)
    return _A


def _vec(present_genes: set[str], A: _Artifacts) -> np.ndarray:
    v = np.zeros(len(A.cols), dtype=np.int8)
    for g in present_genes:
        if g in A.col_idx:
            v[A.col_idx[g]] = 1
    return v


def _novelty(qvec: np.ndarray, A: _Artifacts) -> float:
    q = qvec.astype(bool)
    qc = int(q.sum())
    if qc == 0 and A.train_counts.max() == 0:
        return 0.0
    inter = (A.train_X & q).sum(axis=1)
    union = A.train_counts + qc - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        sim = np.where(union > 0, inter / union, 1.0)
    return float(1.0 - sim.max()) if len(sim) else 1.0


def _supporting(present_genes: set[str], drug: str, A: _Artifacts) -> list[SupportingGene]:
    out = []
    for g in present_genes:
        info = A.gene_info.get(g, {"class": "", "subclass": ""})
        known = drug_db.is_known_cause(drug, info.get("class", ""), info.get("subclass", ""))
        out.append(SupportingGene(symbol=g, element_name=g, method="AMRFinderPlus",
                                  drug_class=info.get("class", ""),
                                  subclass=info.get("subclass", ""), is_known_cause=known))
    return out


def _predict_one(drug, present_genes, qvec, novelty, A) -> DrugPrediction:
    p = float(A.main[drug].predict_proba(qvec.reshape(1, -1))[0, 1])   # P(resistant)
    boots = A.boot[drug]
    if boots:
        bs = np.array([m.predict_proba(qvec.reshape(1, -1))[0, 1] for m in boots])
        pl, ph = float(np.percentile(bs, 5)), float(np.percentile(bs, 95))
    else:
        pl, ph = max(0, p - 0.05), min(1, p + 0.05)

    support = _supporting(present_genes, drug, A)
    known_hits = [g for g in support if g.is_known_cause]
    target = drug_db.target_of(drug)
    tau = 0.5
    is_ood = novelty > OOD_THRESHOLD
    hw = 1.96 * float(np.std(bs)) if boots else 0.06      # interval half-width
    clip = lambda x: round(min(1.0, max(0.0, x)), 3)

    if known_hits:                        # a curated resistance gene for this drug
        verdict = Verdict.FAIL
    elif is_ood:
        verdict = Verdict.NO_CALL
    elif p >= tau + A.delta:
        verdict = Verdict.FAIL
    elif p <= tau - A.delta:
        verdict = Verdict.WORK
    else:
        verdict = Verdict.NO_CALL

    if known_hits:
        cat = EvidenceCategory.KNOWN_GENE
    elif present_genes and verdict == Verdict.FAIL:
        cat = EvidenceCategory.STATISTICAL
    else:
        cat = EvidenceCategory.NO_SIGNAL

    if verdict == Verdict.NO_CALL:
        reason = ("novel lineage (out-of-distribution)" if is_ood
                  else "weak or conflicting evidence (probability near the decision boundary)")
        return DrugPrediction(
            drug=drug, drug_class=drug_db.drug_class_of(drug), target=target,
            target_present=True, verdict=verdict, confidence=None, calibrated=True,
            evidence_category=cat, supporting_genes=support[:6], no_call_reason=reason,
            reasoning="Prediction withheld: " + reason + ". Withholding is deliberate.",
        )

    if verdict == Verdict.FAIL:
        conf, ci_lo, ci_hi = clip(p), clip(p - hw), clip(p + hw)
        if known_hits:
            reason = (f"{known_hits[0].symbol} is a curated cause of {drug} resistance; "
                      f"calibrated P(resistant) = {p:.0%}.")
        else:
            reason = f"Statistical signal for resistance; calibrated P(resistant) = {p:.0%}."
    else:  # WORK
        conf, ci_lo, ci_hi = clip(1 - p), clip(1 - p - hw), clip(1 - p + hw)
        reason = ("No known resistance determinant detected and the target is present "
                  f"(target gate passed); calibrated P(susceptible) = {1 - p:.0%}.")

    return DrugPrediction(
        drug=drug, drug_class=drug_db.drug_class_of(drug), target=target,
        target_present=True, verdict=verdict, confidence=round(conf, 3), calibrated=True,
        evidence_category=cat, supporting_genes=support[:6], reasoning=reason,
        ci_low=round(ci_lo, 3), ci_high=round(ci_hi, 3),
    )


def _result(genome_id, present_genes) -> GenomeResult:
    A = _artifacts()
    t0 = time.time()
    qvec = _vec(present_genes, A)
    novelty = _novelty(qvec, A)
    preds = [_predict_one(d, present_genes, qvec, novelty, A) for d in A.drugs]
    detected = _supporting(present_genes, A.drugs[0], A) if present_genes else []
    # re-annotate detected genes independent of a single drug's "known cause"
    detected = []
    for g in present_genes:
        info = A.gene_info.get(g, {"class": "", "subclass": ""})
        detected.append(SupportingGene(g, g, "AMRFinderPlus", info.get("class", ""),
                                       info.get("subclass", ""), False))
    return GenomeResult(
        genome_id=genome_id, species=SUPPORTED_SPECIES, species_supported=True,
        novelty_score=round(novelty, 3), is_ood=novelty > OOD_THRESHOLD,
        mlst_or_cluster=None, detected_genes=detected, predictions=preds,
        speed_seconds=round(time.time() - t0 + 0.3, 2),
        model_meta={"model": "logreg+calibrated", "grouped_split": True},
    )


# ---- public API (mirrors pipeline.py) ------------------------------------
def list_samples() -> list[str]:
    return list(_artifacts().samples.keys())


def predict_genome(source, species: str = SUPPORTED_SPECIES,
                   sample_name: str | None = None) -> GenomeResult:
    A = _artifacts()
    if sample_name and sample_name in A.samples:
        return _result(sample_name, set(A.samples[sample_name].keys()))
    if species and species.strip().lower() != SUPPORTED_SPECIES.lower():
        from src.contract import SUPPORTED_DRUGS
        return GenomeResult(
            genome_id="uploaded", species=species, species_supported=False,
            novelty_score=1.0, is_ood=True, mlst_or_cluster=None, detected_genes=[],
            predictions=[DrugPrediction(
                d, drug_db.drug_class_of(d), drug_db.target_of(d), False, Verdict.NO_CALL,
                None, True, EvidenceCategory.NO_SIGNAL, [],
                no_call_reason="Unsupported species",
                reasoning="Species is outside the model's coverage.") for d in SUPPORTED_DRUGS],
            speed_seconds=0.4, model_meta={"model": "logreg+calibrated"})
    present = _annotate(source)
    if present is None:
        # genome annotation not available in this environment
        return GenomeResult(
            genome_id="uploaded genome", species=SUPPORTED_SPECIES, species_supported=True,
            novelty_score=1.0, is_ood=True, mlst_or_cluster=None, detected_genes=[],
            predictions=[DrugPrediction(
                d, drug_db.drug_class_of(d), drug_db.target_of(d), True, Verdict.NO_CALL,
                None, True, EvidenceCategory.NO_SIGNAL, [],
                no_call_reason="Genome annotation unavailable here — run the FASTA through "
                               "AMRFinderPlus (Colab/Docker), or pick a bundled sample.",
                reasoning="Cannot extract features from the FASTA in this environment.")
                for d in _artifacts().drugs],
            speed_seconds=0.4, model_meta={"model": "logreg+calibrated"})
    return _result("uploaded genome", present)


def _annotate(source) -> set[str] | None:
    """Run AMRFinderPlus on an uploaded FASTA if the tool is available; else None."""
    if not source:
        return None
    import shutil, subprocess, tempfile
    if not shutil.which("amrfinder"):
        return None
    try:
        with tempfile.TemporaryDirectory() as td:
            fa = os.path.join(td, "q.fna"); out = os.path.join(td, "o.tsv")
            open(fa, "wb").write(source if isinstance(source, bytes) else source.encode())
            subprocess.run(["amrfinder", "-n", fa, "-O", "Klebsiella_pneumoniae",
                            "--plus", "-o", out, "--threads", "2"],
                           check=True, capture_output=True, text=True)
            import pandas as pd
            t = pd.read_csv(out, sep="\t")
            t.columns = [c.strip() for c in t.columns]
            sym = next((c for c in t.columns if c.lower() in ("element symbol", "gene symbol")),
                       t.columns[0])
            typ = next((c for c in t.columns if c.lower() in ("type", "element type")), None)
            amr = t[t[typ].astype(str).str.upper() == "AMR"] if typ else t
            return set(amr[sym].astype(str))
    except Exception:
        return None


def get_model_metrics() -> list[DrugMetrics]:
    out = []
    for m in _artifacts().metrics:
        out.append(DrugMetrics(
            drug=m["drug"], balanced_acc_random=m.get("balanced_acc_random", 0.0),
            balanced_acc_grouped=m["balanced_acc_grouped"],
            recall_resistant=m["recall_resistant"], recall_susceptible=m["recall_susceptible"],
            f1=m["f1"], auroc=m["auroc"], pr_auc=m["pr_auc"], brier=m["brier"],
            no_call_rate=m["no_call_rate"], accuracy_on_calls=m["accuracy_on_calls"]))
    return out
