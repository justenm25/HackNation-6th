"""Presentation guarantees the clinical UI must not lose.

These cover the translation layer between backend vocabulary and what a clinician
reads: machine reason codes, schema feature ids, and confidence intervals that are
not actually intervals. Rendering only — no model or policy behavior is exercised.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app import theme as T
from app.report import build_html_report
from src.contract import EvidenceCategory, GenomeResult, SupportingGene, Verdict


@dataclass
class FakePrediction:
    drug: str = "Ampicillin"
    drug_class: str = "Penicillin"
    target: str = "not assessed"
    target_present: bool = True
    verdict: Verdict = Verdict.FAIL
    confidence: float | None = 0.99
    calibrated: bool = True
    evidence_category: EvidenceCategory = EvidenceCategory.KNOWN_GENE
    supporting_genes: list = None
    no_call_reason: str | None = None
    reasoning: str = ""
    ci_low: float | None = 0.99
    ci_high: float | None = 0.99

    def __post_init__(self):
        if self.supporting_genes is None:
            self.supporting_genes = [SupportingGene(
                symbol="gene::blaTEM-1", element_name="beta-lactamase",
                method="EXACTX", drug_class="", subclass="", is_known_cause=True)]


# ------------------------------------------------------------------ gene labels


@pytest.mark.parametrize("raw,expected", [
    ("gene::blaTEM-1", "blaTEM-1"),
    ("mutation::gyrA::S83L", "gyrA S83L"),
    ("blaKPC-2", "blaKPC-2"),          # collaborator demo already uses bare symbols
    ("", ""),
])
def test_feature_ids_render_as_recognisable_identifiers(raw, expected):
    assert T.gene_label(raw) == expected


def test_antibiogram_shows_symbols_not_schema_ids():
    markup = T.antibiogram([FakePrediction()])
    assert "blaTEM-1" in markup
    assert "gene::" not in markup


# --------------------------------------------------------------- reason codes


@pytest.mark.parametrize("code", [
    "calibrated_probability_within_no_call_band",
    "absence_of_resistance_markers_does_not_establish_susceptibility",
    "known_marker_conflicts_with_model_probability",
])
def test_backend_reason_codes_become_sentences(code):
    text = T.humanize_reason(code)
    assert "_" not in text, "a machine token reached the clinician"
    assert text[0].isupper()


def test_unknown_feature_warning_names_the_feature():
    text = T.humanize_reason("unknown_model_feature:gene::mcr-1")
    assert "mcr-1" in text
    assert "_" not in text.replace("mcr-1", "")


def test_multiple_reasons_are_joined_readably():
    text = T.humanize_reason(
        "calibrated_probability_within_no_call_band; "
        "known_marker_conflicts_with_model_probability")
    assert "_" not in text
    assert ";" in text


def test_human_written_reasons_pass_through_unchanged():
    # The collaborator demo already writes clinical prose; do not mangle it.
    assert T.humanize_reason("Unsupported species") == "Unsupported species"


def test_no_call_detail_renders_the_reason_and_calls_it_deliberate():
    p = FakePrediction(verdict=Verdict.NO_CALL, confidence=None, ci_low=None, ci_high=None,
                       no_call_reason="calibrated_probability_within_no_call_band",
                       reasoning="calibrated_probability_within_no_call_band",
                       evidence_category=EvidenceCategory.NO_SIGNAL,
                       supporting_genes=[])
    markup = T.evidence_detail(p)
    assert "decision thresholds" in markup
    assert "deliberate, not an error" in markup
    assert "calibrated_probability_within_no_call_band" not in markup


# ---------------------------------------------------------------- confidence


def test_a_point_estimate_is_not_dressed_up_as_an_interval():
    markup = T.interval_bar(FakePrediction(confidence=0.99, ci_low=0.99, ci_high=0.99))
    assert "[99–99]" not in markup
    assert "point" in markup
    assert "99%" in markup


def test_a_real_interval_is_shown_as_one():
    markup = T.interval_bar(FakePrediction(confidence=0.9, ci_low=0.82, ci_high=0.95))
    assert "[82–95]" in markup


def test_a_no_call_shows_no_number_at_all():
    markup = T.interval_bar(FakePrediction(verdict=Verdict.NO_CALL, confidence=None,
                                           ci_low=None, ci_high=None))
    assert "withheld" in markup
    assert "%" not in markup


def test_a_zero_lower_bound_survives():
    # `or`-style defaulting would silently replace a 0.0 bound with the point estimate.
    point, lo, hi, has_interval = T.confidence_bounds(
        FakePrediction(confidence=0.4, ci_low=0.0, ci_high=0.8))
    assert (point, lo, hi, has_interval) == (40, 0, 80, True)


# ------------------------------------------------------- downloadable report


def _result(predictions):
    return GenomeResult(
        genome_id="sample-1", species="Escherichia coli", species_supported=True,
        novelty_score=0.1, is_ood=False, mlst_or_cluster=None,
        detected_genes=predictions[0].supporting_genes, predictions=predictions,
        speed_seconds=1.0, model_meta={})


def test_downloadable_report_uses_the_same_translations():
    html = build_html_report(_result([
        FakePrediction(),
        FakePrediction(drug="Ciprofloxacin", verdict=Verdict.NO_CALL, confidence=None,
                       ci_low=None, ci_high=None,
                       no_call_reason="calibrated_probability_within_no_call_band",
                       reasoning="calibrated_probability_within_no_call_band",
                       evidence_category=EvidenceCategory.NO_SIGNAL, supporting_genes=[]),
    ]))
    assert "gene::" not in html
    assert "calibrated_probability_within_no_call_band" not in html
    assert "decision thresholds" in html
    assert "[99–99]" not in html
    # The lab-confirmation requirement must survive into the exported artifact.
    assert "confirmed by standard laboratory testing" in html


def test_safety_banner_is_present_and_has_no_dismiss_control():
    banner = T.safety_banner()
    assert "Confirm every result with standard laboratory testing" in banner
    for dismissal in ("button", "onclick", "dismiss", "close", "aria-hidden"):
        assert dismissal not in banner.lower()
