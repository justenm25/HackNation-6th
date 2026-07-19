"""
Genome Firewall — clinical decision-support console (Module 03).

Dense split-pane layout, EHR conventions: an input rail on the left, the
antibiogram in the centre, and evidence/provenance for the focused drug on the
right. See CLAUDE.md — this is a clinical instrument, not a website.

Run from the project root (genome-firewall/):
    streamlit run app/streamlit_app.py

Talks to the backend ONLY through the contract in src/contract.py.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st
from app.backend_adapter import (
    BACKEND_MODE, REAL_MODE, SUPPORTED_DRUGS, SUPPORTED_SPECIES, get_model_metrics,
    get_reliability, list_samples, predict_genome,
)
from src.contract import Verdict, DEFENSIVE_NOTE
from app import theme as T
from app import charts
from app.report import build_html_report

st.set_page_config(page_title="Genome Firewall — antibiotic response",
                   layout="wide", initial_sidebar_state="collapsed")
st.markdown(T.inject_css(), unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


# ---- persistent trust surface + identity strip ----------------------------
html(T.safety_banner())
html(T.topbar(SUPPORTED_SPECIES, SUPPORTED_DRUGS,
              "Demo mode · collaborator Klebsiella model"
              if BACKEND_MODE == "collaborator_demo" else ""))

result = st.session_state.get("result")

# ---- split pane: input rail | antibiogram | evidence ----------------------
rail, center, detail = st.columns([1.05, 2.5, 1.45], gap="small")

# ---- pane 1: input --------------------------------------------------------
with rail:
    with st.container(border=True):
        html(T.pane_header("Input", "step 1"))
        st.selectbox("Organism", [SUPPORTED_SPECIES],
                     help="Coverage is limited to one species.")
        samples = list_samples()
        source_modes = ["Sample genome", "Upload FASTA"] if samples else ["Upload FASTA"]
        mode = st.radio("Source", source_modes, horizontal=True)
        sample_name, uploaded, species = None, None, SUPPORTED_SPECIES
        if mode == "Sample genome":
            sample_name = st.selectbox("Sample genome (held-out)", samples)
        else:
            uploaded = st.file_uploader("Quality-checked assembly (FASTA)",
                                        type=["fna", "fasta", "fa", "txt"])
            # A bundle covers exactly one species, so in bundle mode the field is fixed.
            # The demo backend models the out-of-coverage path itself, so it stays editable.
            species = st.text_input("Species", value=SUPPORTED_SPECIES,
                                    disabled=REAL_MODE,
                                    help="This model bundle covers one species."
                                    if REAL_MODE else None)
        go = st.button("Analyze genome", type="primary", use_container_width=True)

    if go:
        # Refuse before calling the backend rather than letting it substitute a
        # default: a missing file or an out-of-coverage species must never come back
        # looking like a result.
        refusal = None
        if mode == "Upload FASTA":
            if uploaded is None:
                refusal = ("<b>No genome selected.</b> Choose a quality-checked FASTA "
                           "file, then run the analysis.")
            elif REAL_MODE and species.strip().lower() != SUPPORTED_SPECIES.lower():
                refusal = ("<b>Out of coverage.</b> This bundle covers "
                           f"<i>{SUPPORTED_SPECIES}</i> only, so nothing was analyzed. "
                           "Analyzing another species through it would produce an "
                           "unsupported result.")
        if refusal:
            st.session_state.pop("result", None)
            result = None
            html(T.notice(refusal, "critical"))
        else:
            try:
                with st.spinner("Reading genome → detecting determinants → predicting…"):
                    st.session_state["result"] = predict_genome(
                        uploaded.read() if uploaded else None,
                        species=species, sample_name=sample_name)
                result = st.session_state["result"]
            except Exception as exc:  # surfaced to the user, never a traceback
                st.session_state.pop("result", None)
                result = None
                # NB: not `detail` — that name holds the evidence column.
                message = str(exc).strip() or exc.__class__.__name__
                html(T.notice(
                    "<b>The genome could not be analyzed.</b> Nothing was predicted. "
                    f"Check that the file is a quality-checked assembly. <br>"
                    f'<span style="color:{T.INK_45};">{message[:300]}</span>', "critical"))

    html('<div style="height:6px;"></div>')
    html(T.pane("Coverage", T.coverage_line(SUPPORTED_SPECIES, SUPPORTED_DRUGS)))

    if result:
        html('<div style="height:6px;"></div>')
        html(T.pane("Detected determinants",
                    T.determinant_chips(result.detected_genes),
                    meta=f"{len(result.detected_genes)} in genome"))

# ---- pane 2: antibiogram --------------------------------------------------
focused = None
with center:
    if not result:
        html(T.pane("Predicted antibiotic response",
                    T.empty_state(SUPPORTED_SPECIES), meta="awaiting genome"))
    else:
        withheld = sum(1 for p in result.predictions if p.verdict == Verdict.NO_CALL)
        if not result.species_supported:
            banner = '<div style="padding:2px 12px 0;">' + T.notice(
                "<b>Out of coverage.</b> This species is not supported, so every "
                f"antibiotic is withheld. Supported: {SUPPORTED_SPECIES}.",
                "critical") + "</div>"
        elif result.is_ood:
            banner = '<div style="padding:2px 12px 0;">' + T.notice(
                "<b>Novel lineage.</b> This genome is unlike the training set "
                f"(novelty {result.novelty_score:.0%}); calls are withheld where they "
                "cannot be trusted. Withholding is deliberate, not an error.",
                "warn") + "</div>"
        else:
            banner = ""
        # One markdown call: the pane must be a single block to wrap its own body.
        html(T.pane(
            "Predicted antibiotic response",
            T.isolate_strip(result)
            + '<div style="border-top:1px solid #E2E8F0;"></div>'
            + banner
            + T.antibiogram(result.predictions),
            meta=f"{len(result.predictions)} drugs · {withheld} withheld", pad=False))

        row = st.columns([1, 1])
        with row[0]:
            st.download_button("Download report (HTML — print to PDF)",
                               data=build_html_report(result),
                               file_name="genome_firewall_report.html",
                               mime="text/html", use_container_width=True)

# ---- pane 3: evidence & provenance ---------------------------------------
with detail:
    if not result:
        html(T.pane("Evidence & provenance",
                    '<div style="font-size:.76rem;color:#64748B;line-height:1.5;">'
                    "Evidence for the focused antibiotic appears here: the target "
                    "gate, the calibration state, and whether the call rests on a "
                    "curated resistance determinant or a statistical association "
                    "only.</div>", meta="—"))
    else:
        picked = st.selectbox("Focus drug", [p.drug for p in result.predictions])
        focused = next(p for p in result.predictions if p.drug == picked)
        html(T.pane("Evidence & provenance", T.evidence_detail(focused),
                    meta=T.CALL_LABEL[focused.verdict].lower()))

# ---- performance, below the fold -----------------------------------------
if result:
    html('<div style="height:8px;"></div>')
    with st.expander("Model performance and honesty — held-out genetic groups",
                     expanded=False):
        m = get_model_metrics()
        if not m:
            html(T.notice("Evaluation metrics are not present in this model bundle yet."))
        else:
            html(T.kpi_row([
                ("Mean Brier", f"{sum(x.brier for x in m) / len(m):.2f}",
                 "lower is better"),
                ("Mean no-call rate", f"{sum(x.no_call_rate for x in m) / len(m):.0%}",
                 "withheld by design"),
                ("Accuracy on calls", f"{sum(x.accuracy_on_calls for x in m) / len(m):.2f}",
                 "when not withheld"),
                ("Drugs evaluated", f"{len(m)}", "grouped split"),
            ]))
            html('<div style="height:8px;"></div>')
            html(T.metrics_grid(m))
            html('<div style="height:10px;"></div>')
            c1, c2 = st.columns(2)
            # Rendered at natural size: stretching a matplotlib PNG to the column
            # width blows the charts up past the grid and over their own captions.
            with c1:
                html('<span class="gf-chart-cap">Discrimination — resistant vs '
                     "susceptible separation (AUROC, 0.5 = random)</span>")
                st.pyplot(charts.auroc_bars(m), use_container_width=False)
            with c2:
                html('<span class="gf-chart-cap">Reliability — is the confidence '
                     "trustworthy?</span>")
                st.pyplot(charts.reliability_curve(get_reliability()),
                          use_container_width=False)
        html('<div style="font-size:.73rem;color:#475569;line-height:1.5;">'
             "<b>Reading this.</b> AUROC measures resistant-versus-susceptible ranking; "
             "the Brier score measures probability quality. Grouped evaluation keeps "
             "related genomes together, reducing lineage leakage. Low-confidence or "
             "conflicting cases are deliberately withheld.</div>")

# ---- footer ---------------------------------------------------------------
html(f'<div style="border-top:1px solid #E2E8F0;margin-top:10px;padding-top:7px;'
     f'font-size:.7rem;color:#64748B;line-height:1.5;">{DEFENSIVE_NOTE} '
     "Every result must be confirmed by standard laboratory testing.</div>")
