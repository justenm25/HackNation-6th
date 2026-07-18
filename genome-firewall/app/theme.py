"""
Genome Firewall — clinical design system (see CLAUDE.md).

Chrome is near-monochrome slate. The ONLY saturated colors in the app are the
three clinical calls (fail / work / no-call). Data is IBM Plex Mono with
tabular figures; UI is IBM Plex Sans. No hero, no emoji, no gradients.
"""
from __future__ import annotations
from src.contract import Verdict, EvidenceCategory, SUPPORTED_SPECIES, SUPPORTED_DRUGS

# ---- the six tokens -------------------------------------------------------
PAPER   = "#F7F8FA"
INK     = "#10212E"
LINE    = "#D8DEE6"
FAIL    = "#A4373A"
WORK    = "#1F7A5A"
NOCALL  = "#8A8F98"
INK_60  = "#5A6b78"   # secondary ink (derived, still slate)
INK_40  = "#8A94A0"   # muted ink

CALL_COLOR = {Verdict.FAIL: FAIL, Verdict.WORK: WORK, Verdict.NO_CALL: NOCALL}
CALL_LABEL = {Verdict.FAIL: "Likely to fail", Verdict.WORK: "Likely to work",
              Verdict.NO_CALL: "No-call"}


# ---- global CSS (fonts, chrome, discipline) -------------------------------
def inject_css() -> str:
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

#MainMenu, footer, header [data-testid="stToolbar"] {visibility:hidden;}
[data-testid="stHeader"] {height:0;}

html, body, .stApp, [data-testid="stMarkdownContainer"], p, span, div, label,
h1, h2, h3, h4, h5, h6, button, input, select, textarea, .stButton>button {
  font-family:'IBM Plex Sans', system-ui, -apple-system, sans-serif;
}
.stApp {background:#F7F8FA; color:#10212E;}
.block-container {padding-top:1.1rem; max-width:1160px;}

/* data / numerals always mono + tabular */
.gf-mono, .gf-mono * {font-family:'IBM Plex Mono', ui-monospace, monospace;
  font-variant-numeric:tabular-nums;}

/* primary action = restrained ink, not a marketing button */
.stButton>button[kind="primary"] {background:#10212E; border:1px solid #10212E;
  border-radius:6px; font-weight:600; letter-spacing:.01em;}
.stButton>button[kind="primary"]:hover {background:#1c3547; border-color:#1c3547;}

/* quiet expanders */
[data-testid="stExpander"] {border:1px solid #D8DEE6; border-radius:8px; background:#fff;}

/* focus + motion floor */
*:focus-visible {outline:2px solid #10212E; outline-offset:2px;}
@media (prefers-reduced-motion: reduce) {* {animation:none!important; transition:none!important;}}
</style>
"""


# ---- trust surface --------------------------------------------------------
def safety_banner() -> str:
    return (
        '<div style="background:#fff;border:1px solid #D8DEE6;border-left:4px solid #10212E;'
        'border-radius:6px;padding:9px 14px;margin-bottom:10px;font-size:.85rem;color:#10212E;">'
        '<b>Research prototype.</b> Confirm every result with standard laboratory testing. '
        'This tool supports a clinician\'s decision — it does not make one.</div>'
    )


def wordmark() -> str:
    return (
        '<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:2px;">'
        '<span style="font-size:1.35rem;font-weight:700;color:#10212E;letter-spacing:-.01em;">'
        'Genome Firewall</span>'
        '<span style="color:#5A6b78;font-size:.95rem;">Predicted antibiotic response</span></div>'
    )


def coverage_line() -> str:
    drugs = ", ".join(d.lower() for d in SUPPORTED_DRUGS)
    return (
        f'<div style="font-size:.82rem;color:#5A6b78;line-height:1.5;margin-bottom:6px;">'
        f'<b style="color:#10212E;">Coverage.</b> {SUPPORTED_SPECIES} · {drugs}.<br>'
        f'<b style="color:#10212E;">Out of scope.</b> sample collection, species identification, '
        f'genome reconstruction, and any other species or antibiotic.</div>'
    )


# ---- signature element: call · confidence interval · evidence -------------
def call_chip(verdict: Verdict) -> str:
    if verdict == Verdict.NO_CALL:
        return (
            '<span class="gf-mono" style="display:inline-block;padding:2px 10px;border-radius:4px;'
            'font-size:.74rem;font-weight:600;color:#5A6b78;border:1px solid #C4CAD2;'
            'background-image:repeating-linear-gradient(45deg,#E7EAEE 0 5px,#F3F5F7 5px 10px);">'
            'WITHHELD</span>'
        )
    color = CALL_COLOR[verdict]
    text = "LIKELY TO FAIL" if verdict == Verdict.FAIL else "LIKELY TO WORK"
    return (
        f'<span class="gf-mono" style="display:inline-block;padding:2px 10px;border-radius:4px;'
        f'font-size:.74rem;font-weight:600;color:#fff;background:{color};">{text}</span>'
    )


def interval_bar(p) -> str:
    """Calibrated confidence as a filled interval, not a bare %."""
    if p.verdict == Verdict.NO_CALL or p.confidence is None:
        return (
            '<div style="display:flex;align-items:center;gap:8px;">'
            '<div style="flex:1;height:9px;border-radius:5px;border:1px solid #C4CAD2;'
            'background-image:repeating-linear-gradient(45deg,#E7EAEE 0 5px,#F3F5F7 5px 10px);"></div>'
            '<span class="gf-mono" style="font-size:.74rem;color:#8A94A0;min-width:64px;">withheld</span></div>'
        )
    color = CALL_COLOR[p.verdict]
    lo = int(round((p.ci_low if p.ci_low is not None else p.confidence) * 100))
    hi = int(round((p.ci_high if p.ci_high is not None else p.confidence) * 100))
    pt = int(round(p.confidence * 100))
    band = max(hi - lo, 1)
    return (
        '<div style="display:flex;align-items:center;gap:8px;">'
        '<div style="position:relative;flex:1;height:9px;border-radius:5px;background:#EAEDF1;">'
        f'<div style="position:absolute;left:{lo}%;width:{band}%;top:0;bottom:0;'
        f'background:{color};opacity:.30;border-radius:5px;"></div>'
        f'<div style="position:absolute;left:{pt}%;top:-2px;width:2px;height:13px;background:{color};"></div>'
        '</div>'
        f'<span class="gf-mono" style="font-size:.78rem;color:#10212E;min-width:96px;font-weight:600;">'
        f'{pt}% <span style="color:#8A94A0;font-weight:400;">[{lo}–{hi}]</span></span></div>'
    )


def evidence_mark(cat: EvidenceCategory) -> str:
    """Monochrome — shape + weight carries meaning, so (ii) reads weaker than (i)."""
    if cat == EvidenceCategory.KNOWN_GENE:
        glyph, gcol, txt, tcol = "◆", INK, "known gene", INK
    elif cat == EvidenceCategory.STATISTICAL:
        glyph, gcol, txt, tcol = "◇", INK_40, "statistical only", INK_60
    else:
        glyph, gcol, txt, tcol = "·", INK_40, "no signal", INK_40
    return (
        f'<span style="font-size:.9rem;color:{gcol};">{glyph}</span> '
        f'<span style="font-size:.8rem;color:{tcol};">{txt}</span>'
    )


def report_table(predictions) -> str:
    head = (
        '<tr style="border-bottom:1px solid #C4CAD2;">'
        '<th style="text-align:left;padding:6px 8px;font-size:.72rem;color:#5A6b78;'
        'font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Antibiotic</th>'
        '<th style="text-align:left;padding:6px 8px;font-size:.72rem;color:#5A6b78;'
        'font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Call</th>'
        '<th style="text-align:left;padding:6px 8px;width:280px;font-size:.72rem;color:#5A6b78;'
        'font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Calibrated confidence</th>'
        '<th style="text-align:left;padding:6px 8px;font-size:.72rem;color:#5A6b78;'
        'font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Evidence</th></tr>'
    )
    rows = []
    for p in predictions:
        rows.append(
            '<tr style="border-bottom:1px solid #EAEDF1;">'
            f'<td style="padding:9px 8px;font-weight:600;color:#10212E;">{p.drug}'
            f'<div style="font-size:.72rem;color:#8A94A0;font-weight:400;">{p.drug_class}</div></td>'
            f'<td style="padding:9px 8px;">{call_chip(p.verdict)}</td>'
            f'<td style="padding:9px 8px;">{interval_bar(p)}</td>'
            f'<td style="padding:9px 8px;">{evidence_mark(p.evidence_category)}</td></tr>'
        )
    return (
        '<table style="width:100%;border-collapse:collapse;background:#fff;'
        'border:1px solid #D8DEE6;border-radius:8px;overflow:hidden;">'
        f'<thead>{head}</thead><tbody>{"".join(rows)}</tbody></table>'
    )


def empty_state() -> str:
    return (
        '<div style="border:1px dashed #C4CAD2;border-radius:8px;padding:34px;text-align:center;'
        'background:#fff;color:#5A6b78;">'
        f'<div style="font-weight:600;color:#10212E;margin-bottom:4px;">No genome loaded</div>'
        f'Select a bundled {SUPPORTED_SPECIES} sample, or upload a quality-checked FASTA, '
        f'then run the analysis to see the predicted antibiotic response.</div>'
    )
