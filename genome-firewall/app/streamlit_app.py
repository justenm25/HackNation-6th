"""
Genome Firewall — Streamlit demo (Module 03). Clinical instrument; see CLAUDE.md.

Run from the project root (genome-firewall/):
    streamlit run app/streamlit_app.py

Talks to the backend ONLY through src.pipeline (see src/contract.py).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st
from src.pipeline import predict_genome, list_samples, get_model_metrics
from src.contract import Verdict, SUPPORTED_SPECIES, SUPPORTED_DRUGS, DEFENSIVE_NOTE
from app import theme as T
from app import charts
from app.report import build_html_report

st.set_page_config(page_title="Genome Firewall", layout="wide")
st.markdown(T.inject_css(), unsafe_allow_html=True)


def notice(text: str) -> None:
    st.markdown(
        f'<div style="background:#fff;border:1px solid #D8DEE6;border-left:4px solid #10212E;'
        f'border-radius:6px;padding:9px 14px;margin:8px 0;font-size:.85rem;color:#10212E;">{text}</div>',
        unsafe_allow_html=True)


# ---- persistent trust surface --------------------------------------------
st.markdown(T.safety_banner(), unsafe_allow_html=True)
st.markdown(T.wordmark(), unsafe_allow_html=True)
st.markdown(T.coverage_line(), unsafe_allow_html=True)
st.markdown('<hr style="border:none;border-top:1px solid #D8DEE6;margin:.4rem 0 1rem;">',
            unsafe_allow_html=True)

rail, main = st.columns([1, 3], gap="large")

# ---- input rail -----------------------------------------------------------
with rail:
    st.markdown("**Input**")
    st.selectbox("Organism", [SUPPORTED_SPECIES], help="Coverage is limited to one species.")
    mode = st.radio("Source", ["Sample genome", "Upload FASTA"], label_visibility="collapsed")
    sample_name, uploaded, species = None, None, SUPPORTED_SPECIES
    if mode == "Sample genome":
        sample_name = st.selectbox("Sample genome (held-out)", list_samples())
    else:
        uploaded = st.file_uploader("Quality-checked assembly (FASTA)",
                                    type=["fna", "fasta", "fa", "txt"])
        species = st.text_input("Species", value=SUPPORTED_SPECIES)
    go = st.button("Analyze genome", type="primary", use_container_width=True)
    if go:
        src = uploaded.read() if uploaded else None
        with st.spinner("Reading genome → detecting determinants → predicting…"):
            st.session_state["result"] = predict_genome(src, species=species, sample_name=sample_name)

# ---- main -----------------------------------------------------------------
with main:
    result = st.session_state.get("result")
    if not result:
        st.markdown(T.empty_state(), unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div style="font-size:1.05rem;font-weight:600;">Predicted response — '
            f'isolate <span class="gf-mono">{result.genome_id}</span></div>'
            f'<div class="gf-mono" style="font-size:.8rem;color:#5A6b78;margin:2px 0 10px;">'
            f'{result.species} · lineage {result.mlst_or_cluster or "unknown"} · '
            f'novelty {result.novelty_score:.0%} · signal→decision {result.speed_seconds:.1f}s</div>',
            unsafe_allow_html=True)

        if not result.species_supported:
            notice("<b>Out of coverage.</b> This species is not supported — all antibiotics "
                   "are withheld. Supported: " + SUPPORTED_SPECIES + ".")
        elif result.is_ood:
            notice("<b>Novel lineage.</b> This genome is unlike the training set "
                   f"(novelty {result.novelty_score:.0%}); calls are withheld where they cannot "
                   "be trusted. Withholding is deliberate, not an error.")

        st.markdown(T.report_table(result.predictions), unsafe_allow_html=True)
        st.write("")
        st.download_button("Download report (HTML — print to PDF)",
                           data=build_html_report(result),
                           file_name="genome_firewall_report.html",
                           mime="text/html")

        # ---- evidence & provenance ----
        st.markdown("##### Evidence & provenance")
        for p in result.predictions:
            with st.expander(f"{p.drug} — {T.CALL_LABEL[p.verdict]}"):
                st.markdown(f"<span style='color:#5A6b78;font-size:.88rem;'>{p.reasoning}</span>",
                            unsafe_allow_html=True)
                gate = "present" if p.target_present else "absent (intrinsic resistance)"
                st.markdown(f"<span style='font-size:.82rem;color:#5A6b78;'>Target gate: "
                            f"<span class='gf-mono'>{gate}</span></span>", unsafe_allow_html=True)
                if p.evidence_category.value == "known_gene" and p.supporting_genes:
                    st.markdown("<span style='font-size:.82rem;'>Known resistance determinants:</span>",
                                unsafe_allow_html=True)
                    for g in p.supporting_genes:
                        st.markdown(
                            f"<span class='gf-mono' style='font-size:.82rem;'>{g.symbol}</span> "
                            f"<span style='font-size:.78rem;color:#8A94A0;'>· {g.method} · "
                            f"{g.element_name}</span>", unsafe_allow_html=True)
                elif p.evidence_category.value == "statistical":
                    genes = ", ".join(g.symbol for g in p.supporting_genes) or "model features"
                    st.markdown(
                        f"<div style='font-size:.82rem;'>Leaned on <span class='gf-mono'>{genes}</span> "
                        f"— a statistical association.</div>"
                        f"<div style='font-size:.78rem;color:#A4373A;margin-top:2px;'>Caveat: "
                        f"feature importance is not proof of a biological cause.</div>",
                        unsafe_allow_html=True)
                else:
                    st.markdown("<span style='font-size:.82rem;color:#8A94A0;'>No known resistance "
                                "determinant detected.</span>", unsafe_allow_html=True)

        # ---- genome determinants ----
        if result.detected_genes:
            st.markdown("##### Detected determinants (genome)")
            chips = " ".join(
                f"<span class='gf-mono' style='background:#EEF1F4;border:1px solid #D8DEE6;"
                f"border-radius:4px;padding:1px 7px;font-size:.8rem;margin:0 4px 4px 0;"
                f"display:inline-block;'>{g.symbol}</span>" for g in result.detected_genes)
            st.markdown(chips, unsafe_allow_html=True)

        # ---- performance & honesty ----
        st.markdown("##### Performance & honesty (held-out, grouped by MLST)")
        m = get_model_metrics()
        brier = sum(x.brier for x in m) / len(m)
        ncall = sum(x.no_call_rate for x in m) / len(m)
        acc = sum(x.accuracy_on_calls for x in m) / len(m)
        st.markdown(
            '<div class="gf-mono" style="display:flex;gap:26px;font-size:.85rem;margin-bottom:8px;">'
            f'<span>Mean Brier <b>{brier:.2f}</b></span>'
            f'<span>Mean no-call rate <b>{ncall:.0%}</b></span>'
            f'<span>Accuracy on calls <b>{acc:.2f}</b></span></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<span style='font-size:.82rem;color:#5A6b78;'>Discrimination — resistant "
                        "vs susceptible separation (AUROC, 0.5 = random)</span>", unsafe_allow_html=True)
            st.pyplot(charts.auroc_bars(m), use_container_width=True)
        with c2:
            st.markdown("<span style='font-size:.82rem;color:#5A6b78;'>Reliability — is the "
                        "confidence trustworthy?</span>", unsafe_allow_html=True)
            st.pyplot(charts.reliability_curve(), use_container_width=True)
        st.dataframe(
            [{"Drug": x.drug, "AUROC": f"{x.auroc:.2f}", "PR-AUC": f"{x.pr_auc:.2f}",
              "Recall R": f"{x.recall_resistant:.2f}", "Recall S": f"{x.recall_susceptible:.2f}",
              "Grouped / random": f"{x.balanced_acc_grouped:.2f} / {x.balanced_acc_random:.2f}",
              "Brier": f"{x.brier:.2f}", "No-call %": f"{x.no_call_rate:.0%}"}
             for x in m],
            use_container_width=True, hide_index=True)
        st.markdown(
            "<div style='font-size:.82rem;color:#5A6b78;line-height:1.5;'>"
            "<b>Reading this.</b> AUROC is threshold-free discrimination. The model separates "
            "resistant from susceptible best for acquired-gene drugs (ceftazidime, ciprofloxacin). "
            "Grouped ≈ random accuracy is a good sign — it relies on horizontally-transferred "
            "resistance genes, not memorised clonal lineages.<br>"
            "<b>Documented limitation.</b> Weak drugs (amikacin, tigecycline; part of carbapenem / "
            "fluoroquinolone) resist mainly via <i>mutations</i> (gyrA/parC, porin ompK loss) that "
            "acquired-gene annotations do not capture — so the system withholds there rather than "
            "guessing.</div>", unsafe_allow_html=True)

    st.markdown('<hr style="border:none;border-top:1px solid #D8DEE6;margin:1rem 0 .5rem;">',
                unsafe_allow_html=True)
    st.markdown(f"<span style='font-size:.78rem;color:#8A94A0;'>{DEFENSIVE_NOTE} "
                "Every result must be confirmed by standard laboratory testing.</span>",
                unsafe_allow_html=True)
