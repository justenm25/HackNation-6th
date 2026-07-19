"""Adapter tests against a synthetic frozen bundle.

`app.backend_adapter` decides its mode at import time from ``GF_MODEL_BUNDLE``, so each
test here builds a minimal bundle on disk, points the variable at it, and reloads the
module. The ``real_mode`` fixture always reloads the adapter back to demo mode afterwards
so the collaborator-demo tests are unaffected by ordering.

AMRFinder is never executed: ``genome_firewall.api.run_amrfinder`` is replaced with a stub
that copies a committed fixture TSV to the path the API expects.
"""

from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pytest
from scipy.sparse import csr_matrix
from sklearn.linear_model import LogisticRegression

from genome_firewall.calibrate.calibrators import ProbabilityCalibrator
from genome_firewall.featurize.schema import FeatureSchema
from genome_firewall.types import NormalizedFinding


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
# Exactly the features in amrfinder_genes.tsv. The schema must cover all of them: an
# unknown feature raises a warning that makes every drug abstain, which would mask the
# translation behavior these tests are checking.
FEATURES = ("gene::blaTEM-1", "gene::sul1", "gene::tetA")
# Drug ids and the display names the frontend should surface.
PANEL = [{"id": "ampicillin", "display_name": "Ampicillin"},
         {"id": "gentamicin", "display_name": "Gentamicin"}]


def _finding(feature_id: str) -> NormalizedFinding:
    return NormalizedFinding(feature_id=feature_id, kind="gene",
                             gene_symbol=feature_id.split("::")[1])


def _fitted_pair(weights: list[float], intercept: float):
    """A logistic model over the synthetic schema plus a calibrator fitted on its output."""
    model = LogisticRegression()
    # Fit on a trivial separable problem, then overwrite the coefficients so the decision
    # is fully determined by the test rather than by the optimizer.
    x = csr_matrix(np.eye(len(FEATURES), dtype=float))
    model.fit(x, [0, 1, 0][: len(FEATURES)])
    model.coef_ = np.array([weights], dtype=float)
    model.intercept_ = np.array([intercept], dtype=float)

    calibrator = ProbabilityCalibrator("sigmoid")
    raw = np.array([0.02, 0.05, 0.9, 0.95])
    calibrator.fit(raw, np.array([0, 0, 1, 1]))
    return model, calibrator


def build_bundle(path: Path, *, marker_map: dict | None = None,
                 thresholds: dict | None = None) -> Path:
    (path / "models").mkdir(parents=True)
    (path / "calibrators").mkdir()
    schema = FeatureSchema.fit([[_finding(name) for name in FEATURES]])
    schema.save(path / "feature_schema.json")

    # Ampicillin leans hard on blaTEM-1 so the fixture genome scores resistant; gentamicin
    # has no signal in this genome and lands in the no-call band.
    weights = {"ampicillin": ([6.0, 0.0, 0.0], -1.0), "gentamicin": ([0.0, 0.0, 0.0], 0.0)}
    for drug in PANEL:
        model, calibrator = _fitted_pair(*weights[drug["id"]])
        joblib.dump(model, path / "models" / f"{drug['id']}.joblib")
        joblib.dump(calibrator, path / "calibrators" / f"{drug['id']}.joblib")

    (path / "thresholds.json").write_text(json.dumps(thresholds or {
        "ampicillin": {"resistant_threshold": 0.6, "susceptible_threshold": 0.05},
        "gentamicin": {"resistant_threshold": 0.99, "susceptible_threshold": 0.001},
    }), encoding="utf-8")
    (path / "bundle_manifest.json").write_text(json.dumps({
        "bundle_schema_version": "genome-firewall-bundle-v1",
        "feature_schema_id": schema.schema_id, "drug_panel": PANEL,
    }), encoding="utf-8")
    if marker_map is not None:
        (path / "marker_drug_map.json").write_text(json.dumps(marker_map), encoding="utf-8")
    return path


@pytest.fixture
def real_mode(tmp_path, monkeypatch):
    """Reload the adapter in bundle mode, and always restore demo mode afterwards."""
    import app.backend_adapter as adapter

    def _load(bundle: Path):
        monkeypatch.setenv("GF_MODEL_BUNDLE", str(bundle))
        return importlib.reload(adapter)

    try:
        yield _load
    finally:
        monkeypatch.delenv("GF_MODEL_BUNDLE", raising=False)
        importlib.reload(adapter)


@pytest.fixture
def stub_amrfinder(monkeypatch):
    """Replace AMRFinder execution with a copy of a committed fixture TSV."""
    import genome_firewall.api as api

    calls = []

    def fake_run(fasta_path, output_path, **kwargs):
        calls.append({"fasta": Path(fasta_path), "output": Path(output_path), **kwargs})
        shutil.copyfile(FIXTURES / "amrfinder_genes.tsv", output_path)
        return Path(output_path)

    monkeypatch.setattr(api, "run_amrfinder", fake_run)
    return calls


# ------------------------------------------------------------------ mode and coverage


def test_bundle_directory_switches_the_adapter_into_real_mode(tmp_path, real_mode):
    adapter = real_mode(build_bundle(tmp_path / "bundle"))

    assert adapter.REAL_MODE is True
    assert adapter.BACKEND_MODE == "ecoli_bundle"
    assert adapter.SUPPORTED_SPECIES == "Escherichia coli"
    # Coverage is read from the bundle, not hard-coded.
    assert adapter.SUPPORTED_DRUGS == ["Ampicillin", "Gentamicin"]
    # The shipped demo samples belong to the other backend.
    assert adapter.list_samples() == []


def test_drug_coverage_follows_the_bundle_panel(tmp_path, real_mode, monkeypatch):
    bundle = build_bundle(tmp_path / "bundle")
    manifest = json.loads((bundle / "bundle_manifest.json").read_text())
    manifest["drug_panel"] = [{"id": "ciprofloxacin", "display_name": "Ciprofloxacin"}]
    (bundle / "bundle_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    adapter = real_mode(bundle)
    assert adapter.SUPPORTED_DRUGS == ["Ciprofloxacin"]


def test_a_missing_bundle_directory_falls_back_to_the_demo(tmp_path, real_mode):
    adapter = real_mode(tmp_path / "does-not-exist")

    assert adapter.REAL_MODE is False
    assert adapter.BACKEND_MODE == "collaborator_demo"


def test_demo_only_entry_points_are_refused_in_bundle_mode(tmp_path, real_mode):
    adapter = real_mode(build_bundle(tmp_path / "bundle"))

    with pytest.raises(ValueError, match="Bundled demo samples are unavailable"):
        adapter.predict_genome(b">c\nACGT\n", sample_name="demo-1")
    with pytest.raises(ValueError, match="Upload a quality-checked FASTA"):
        adapter.predict_genome(None)


# ---------------------------------------------------------------- report translation


def test_report_is_translated_into_the_frontend_contract(tmp_path, real_mode, stub_amrfinder):
    bundle = build_bundle(tmp_path / "bundle",
                          marker_map={"ampicillin": ["gene::blaTEM-1"]})
    adapter = real_mode(bundle)

    result = adapter.predict_genome(b">contig\nACGTACGTACGT\n")

    assert result.species == "Escherichia coli"
    assert result.species_supported is True
    assert [prediction.drug for prediction in result.predictions] == ["Ampicillin", "Gentamicin"]

    ampicillin, gentamicin = result.predictions
    assert ampicillin.verdict is adapter.Verdict.FAIL
    assert ampicillin.evidence_category is adapter.EvidenceCategory.KNOWN_GENE
    assert ampicillin.calibrated is True
    assert 0.0 <= ampicillin.confidence <= 1.0
    assert ampicillin.no_call_reason is None
    assert ampicillin.reasoning
    # The curated marker for this drug is cited as evidence.
    assert any(gene.symbol == "gene::blaTEM-1" for gene in ampicillin.supporting_genes)
    assert all(gene.is_known_cause for gene in ampicillin.supporting_genes)

    # A probability inside the no-call band abstains, and says why.
    assert gentamicin.verdict is adapter.Verdict.NO_CALL
    assert gentamicin.no_call_reason
    assert gentamicin.confidence is None

    assert result.detected_genes
    assert result.model_meta["backend_mode"] == "ecoli_bundle"
    assert result.model_meta["bundle"] == "bundle"
    # The lab-confirmation requirement must survive translation to the UI.
    assert result.model_meta["confirm_with_lab_testing"] is True


def test_evidence_without_a_curated_marker_is_reported_as_statistical(
        tmp_path, real_mode, stub_amrfinder):
    # No marker_drug_map.json, so nothing in the genome is curated for the drug.
    adapter = real_mode(build_bundle(tmp_path / "bundle"))

    result = adapter.predict_genome(b">contig\nACGTACGTACGT\n")

    ampicillin = result.predictions[0]
    assert ampicillin.evidence_category is adapter.EvidenceCategory.STATISTICAL
    assert not any(gene.is_known_cause for gene in ampicillin.supporting_genes)


def test_prediction_runs_amrfinder_once_and_cleans_up_the_temporary_fasta(
        tmp_path, real_mode, stub_amrfinder):
    adapter = real_mode(build_bundle(tmp_path / "bundle"))

    adapter.predict_genome(b">contig\nACGTACGTACGT\n")

    assert len(stub_amrfinder) == 1
    assert not stub_amrfinder[0]["fasta"].exists(), "temporary FASTA should be removed"


def test_amrfinder_executable_and_database_come_from_the_environment(
        tmp_path, real_mode, stub_amrfinder, monkeypatch):
    monkeypatch.setenv("GF_AMRFINDER", "/custom/amrfinder")
    monkeypatch.setenv("GF_AMRFINDER_DB", "/custom/db")
    adapter = real_mode(build_bundle(tmp_path / "bundle"))

    adapter.predict_genome(b">contig\nACGTACGTACGT\n")

    assert stub_amrfinder[0]["executable"] == "/custom/amrfinder"
    assert stub_amrfinder[0]["database_dir"] == "/custom/db"


# ------------------------------------------------------------------------- metrics


def test_metrics_and_reliability_are_empty_without_artifacts(tmp_path, real_mode):
    adapter = real_mode(build_bundle(tmp_path / "bundle"))

    assert adapter.get_model_metrics() == []
    assert adapter.get_reliability() == []


def test_metrics_are_read_from_the_bundle_when_present(tmp_path, real_mode):
    bundle = build_bundle(tmp_path / "bundle")
    (bundle / "metrics").mkdir()
    (bundle / "metrics" / "summary.json").write_text(json.dumps({"drugs": {"Ampicillin": {
        "balanced_accuracy": 0.81, "resistant_recall": 0.75, "susceptible_recall": 0.87,
        "f1": 0.78, "auroc": 0.9, "pr_auc": 0.85, "brier_score": 0.12,
        "no_call_rate": 0.2, "accuracy_on_called": 0.93,
    }}}), encoding="utf-8")
    (bundle / "metrics" / "reliability.json").write_text(
        json.dumps([{"confidence": 0.9, "accuracy": 0.88}]), encoding="utf-8")

    adapter = real_mode(bundle)

    metrics = adapter.get_model_metrics()
    assert len(metrics) == 1
    assert metrics[0].drug == "Ampicillin"
    assert metrics[0].balanced_acc_grouped == pytest.approx(0.81)
    assert metrics[0].no_call_rate == pytest.approx(0.2)
    assert adapter.get_reliability() == [{"confidence": 0.9, "accuracy": 0.88}]
