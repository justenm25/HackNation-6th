"""Stable seam between the Streamlit frontend and either backend.

Without ``GF_MODEL_BUNDLE`` this delegates to the collaborator's shipped Klebsiella
demo.  With a bundle, it calls the leakage-safe E. coli backend and translates its
report into the frontend contract.  The modes are explicit in ``BACKEND_MODE``.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from src.contract import (
    DrugMetrics, DrugPrediction, EvidenceCategory, GenomeResult, SupportingGene, Verdict,
)

BUNDLE = os.environ.get("GF_MODEL_BUNDLE", "").strip()
REAL_MODE = bool(BUNDLE and Path(BUNDLE).is_dir())
BACKEND_MODE = "ecoli_bundle" if REAL_MODE else "collaborator_demo"

if REAL_MODE:
    _bundle_path = Path(BUNDLE)
    _manifest = json.loads((_bundle_path / "bundle_manifest.json").read_text())
    _precomputed_path = _bundle_path / "precomputed_samples.json"
    _precomputed_samples = (json.loads(_precomputed_path.read_text())
                            if _precomputed_path.exists() else {})
    SUPPORTED_SPECIES = "Escherichia coli"
    SUPPORTED_DRUGS = [drug.get("display_name", drug["id"]) for drug in _manifest["drug_panel"]]
else:
    from src.contract import SUPPORTED_DRUGS, SUPPORTED_SPECIES


def list_samples() -> list[str]:
    if not REAL_MODE:
        from src.pipeline import list_samples as legacy_list
        return legacy_list()
    return list(_precomputed_samples)


def predict_genome(source, species: str = SUPPORTED_SPECIES,
                   sample_name: str | None = None) -> GenomeResult:
    if not REAL_MODE:
        from src.pipeline import predict_genome as legacy_predict
        return legacy_predict(source, species=species, sample_name=sample_name)
    from genome_firewall.api import predict

    if sample_name:
        relative = _precomputed_samples.get(sample_name)
        if not isinstance(relative, str):
            raise ValueError(f"Unknown bundled demo sample: {sample_name}")
        sample_path = (_bundle_path / relative).resolve()
        if _bundle_path.resolve() not in sample_path.parents or not sample_path.is_file():
            raise ValueError(f"Invalid bundled demo sample: {sample_name}")
        report = predict(
            sample_path, bundle_path=BUNDLE, input_format="amrfinder_tsv",
            sample_id=sample_name, species_id="escherichia_coli",
            marker_free_susceptible_policy=os.environ.get(
                "GF_SUSCEPTIBLE_POLICY", "conservative"),
        )
        return _translate_report(report)
    if not source:
        raise ValueError("Upload a quality-checked FASTA")

    with tempfile.NamedTemporaryFile(suffix=".fasta", delete=False) as handle:
        handle.write(source if isinstance(source, bytes) else source.encode())
        fasta = Path(handle.name)
    try:
        report = predict(
            fasta, bundle_path=BUNDLE, input_format="fasta", species_id="escherichia_coli",
            amrfinder_executable=os.environ.get("GF_AMRFINDER", "amrfinder"),
            amrfinder_database_dir=os.environ.get("GF_AMRFINDER_DB") or None,
            marker_free_susceptible_policy=os.environ.get(
                "GF_SUSCEPTIBLE_POLICY", "conservative"),
        )
    finally:
        fasta.unlink(missing_ok=True)
    return _translate_report(report)


def _translate_report(report) -> GenomeResult:
    predictions = []
    detected: dict[str, SupportingGene] = {}
    category_map = {
        "known_resistance_marker": EvidenceCategory.KNOWN_GENE,
        "statistical_association_only": EvidenceCategory.STATISTICAL,
        "no_known_signal": EvidenceCategory.NO_SIGNAL,
    }
    verdict_map = {
        "likely_to_work": Verdict.WORK,
        "likely_to_fail": Verdict.FAIL,
        "no_call": Verdict.NO_CALL,
    }
    for item in report.predictions:
        genes = []
        for evidence in item.evidence:
            symbol = evidence.get("feature_id") or evidence.get("rule_id") or evidence.get("type", "evidence")
            gene = SupportingGene(
                symbol=symbol, element_name=evidence.get("interpretation", ""),
                method=evidence.get("type", "AMRFinderPlus"), drug_class="", subclass="",
                is_known_cause=item.evidence_category.value == "known_resistance_marker",
            )
            genes.append(gene)
            detected[symbol] = gene
        reason = "; ".join(item.no_call_reasons) if item.no_call_reasons else (
            "Known resistance evidence and calibrated model output support this call."
            if item.call.value == "likely_to_fail" else
            "Validated calibrated model output supports this call."
        )
        confidence = item.calibrated_confidence
        predictions.append(DrugPrediction(
            drug=item.drug_name, drug_class="configured panel", target="not assessed",
            target_present=True, verdict=verdict_map[item.call.value], confidence=confidence,
            calibrated=True, evidence_category=category_map[item.evidence_category.value],
            supporting_genes=genes, no_call_reason="; ".join(item.no_call_reasons) or None,
            reasoning=reason, ci_low=confidence, ci_high=confidence,
        ))
    return GenomeResult(
        genome_id=report.sample["sample_id"], species="Escherichia coli",
        species_supported=True, novelty_score=0.0, is_ood=False, mlst_or_cluster=None,
        detected_genes=list(detected.values()), predictions=predictions, speed_seconds=0.0,
        model_meta={"backend_mode": BACKEND_MODE, "bundle": Path(BUNDLE).name,
                    "confirm_with_lab_testing": report.confirm_with_lab_testing},
    )


def get_model_metrics() -> list[DrugMetrics]:
    if not REAL_MODE:
        from src.pipeline import get_model_metrics as legacy_metrics
        return legacy_metrics()
    path = Path(BUNDLE) / "metrics" / "summary.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    rows = payload.get("drugs", payload)
    metrics = []
    display_names = {drug["id"]: drug.get("display_name", drug["id"])
                     for drug in _manifest["drug_panel"]}
    for name, values in rows.items():
        classification = values.get("classification", values)
        calibration = values.get("calibration", values)
        abstention = values.get("abstention", values)
        metrics.append(DrugMetrics(
            drug=display_names.get(name, name), balanced_acc_random=0.0,
            balanced_acc_grouped=float(classification["balanced_accuracy"]),
            recall_resistant=float(classification["resistant_recall"]),
            recall_susceptible=float(classification["susceptible_recall"]),
            f1=float(classification.get("f1", 0)), auroc=float(classification["auroc"]),
            pr_auc=float(classification["pr_auc"]), brier=float(calibration["brier_score"]),
            no_call_rate=float(abstention["no_call_rate"]),
            accuracy_on_calls=float(abstention["accuracy_on_called"] or 0),
        ))
    return metrics


def get_reliability() -> list[dict]:
    if not REAL_MODE:
        path = Path(__file__).resolve().parents[1] / "models" / "artifacts" / "reliability.json"
        return json.loads(path.read_text()) if path.exists() else []
    path = Path(BUNDLE) / "metrics" / "reliability.json"
    if path.exists():
        return json.loads(path.read_text())
    summary = Path(BUNDLE) / "metrics" / "summary.json"
    if not summary.exists():
        return []
    payload = json.loads(summary.read_text())
    curves = [values.get("calibration", {}).get("reliability_curve", [])
              for values in payload.get("drugs", payload).values()]
    curves = [curve for curve in curves if curve]
    if not curves:
        return []
    # Convert resistant probabilities into call confidence/accuracy, then pool nearby
    # points for the panel-level chart. Per-drug resistant-probability curves remain in
    # summary.json for scientific inspection.
    bins: dict[int, list[tuple[float, float]]] = {}
    for curve in curves:
        for point in curve:
            probability = float(point["mean_predicted"])
            observed = float(point["observed_resistant_fraction"])
            confidence = max(probability, 1.0 - probability)
            accuracy = observed if probability >= 0.5 else 1.0 - observed
            bins.setdefault(min(9, int((confidence - 0.5) * 10)), []).append(
                (confidence, accuracy))
    return [{"confidence": sum(point[0] for point in bins[index]) / len(bins[index]),
             "accuracy": sum(point[1] for point in bins[index]) / len(bins[index])}
            for index in sorted(bins)]
