"""
Genome Firewall — clinical design system.

High-density EHR chrome: slate base, white surfaces, slate-900 text. Blue is
reserved for primary actions and never used to encode a result. Result state is
carried by emerald (works), rose (fails) and a hatched slate (withheld). All
numerals are tabular so vitals, confidences and times align vertically.
No gradients, no shadows, no hero, no emoji.
"""
from __future__ import annotations
from src.contract import Verdict, EvidenceCategory

# ---- tokens ---------------------------------------------------------------
# Surfaces / chrome
CANVAS   = "#F8FAFC"   # slate-50   app background
SURFACE  = "#FFFFFF"   # white      panels, rows
INK      = "#0F172A"   # slate-900  primary text            17.4:1 on white
INK_60   = "#475569"   # slate-600  secondary text           7.5:1 on white
INK_45   = "#64748B"   # slate-500  muted text (AA floor)    4.8:1 on white
LINE     = "#E2E8F0"   # slate-200  hairlines
LINE_60  = "#CBD5E1"   # slate-300  stronger rules
FILL     = "#F1F5F9"   # slate-100  zebra / track

# Action (never encodes a result)
ACTION   = "#2563EB"   # blue-600                            5.2:1 white text
ACTION_D = "#1D4ED8"   # blue-700   hover/active

# State
WORK     = "#047857"   # emerald-700 normal                  5.6:1 white text
WARN     = "#B45309"   # amber-700   warning                 5.1:1 white text
FAIL     = "#BE123C"   # rose-700    critical                6.2:1 white text
NOCALL   = "#64748B"   # slate-500   withheld
WORK_BG  = "#ECFDF5"
WARN_BG  = "#FFFBEB"
FAIL_BG  = "#FFF1F2"

# Back-compat aliases for the previous token names.
PAPER, INK_40 = CANVAS, INK_45

CALL_COLOR = {Verdict.FAIL: FAIL, Verdict.WORK: WORK, Verdict.NO_CALL: NOCALL}
CALL_LABEL = {Verdict.FAIL: "Likely to fail", Verdict.WORK: "Likely to work",
              Verdict.NO_CALL: "No-call"}
CALL_TEXT  = {Verdict.FAIL: "LIKELY TO FAIL", Verdict.WORK: "LIKELY TO WORK",
              Verdict.NO_CALL: "WITHHELD"}

_HATCH = ("repeating-linear-gradient(45deg,#E2E8F0 0 4px,#F1F5F9 4px 8px)")


# ---- global CSS -----------------------------------------------------------
def inject_css() -> str:
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root{
  --canvas:#F8FAFC; --surface:#FFFFFF; --ink:#0F172A; --ink-60:#475569;
  --ink-45:#64748B; --line:#E2E8F0; --line-60:#CBD5E1; --fill:#F1F5F9;
  --action:#2563EB; --action-d:#1D4ED8;
  --work:#047857; --warn:#B45309; --fail:#BE123C;
}

#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"]{display:none;}
[data-testid="stHeader"]{height:0; background:transparent;}

html, body, .stApp, [data-testid="stMarkdownContainer"], p, span, div, label,
h1,h2,h3,h4,h5,h6, button, input, select, textarea{
  font-family:'Inter', -apple-system, 'SF Pro Text', system-ui, sans-serif;
  -webkit-font-smoothing:antialiased;
}
.stApp{background:var(--canvas); color:var(--ink);}

/* Streamlit gives every markdown container a -16px bottom margin to absorb the
   trailing <p> margin. Our components are divs, not paragraphs, so that margin
   dragged each block 16px into the next one — headers landed on top of the labels
   below them. Cancel it and neutralise the trailing paragraph margin instead. */
[data-testid="stMarkdownContainer"]{margin-bottom:0 !important;}
[data-testid="stMarkdownContainer"] > p:last-child{margin-bottom:0;}

/* density: reclaim the page for data, but never at the cost of legibility */
.block-container{padding:0.7rem 1.1rem 1.4rem; max-width:100%;}
[data-testid="stVerticalBlock"]{gap:0.6rem;}
[data-testid="stHorizontalBlock"]{gap:0.85rem;}
hr{margin:0.5rem 0;}

/* Panes that hold Streamlit widgets must be real containers: Streamlit closes any
   unclosed tag at the end of its own markdown block, so an HTML-only wrapper would
   render as an empty box and the widgets would collide with its bottom edge. Those
   panes use st.container(border=True) and mark themselves with a pane_header().
   Match on that header so plain columns — same testid, no border — stay untouched.
   Streamlit has moved the border between the wrapper and the inner block across
   versions, so normalise both. */
[data-testid="stVerticalBlockBorderWrapper"]:has(
    [data-testid="stMarkdownContainer"] > .gf-pane-hd){border:none; padding:0;}
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] [data-testid="stMarkdownContainer"] > .gf-pane-hd){
  border:1px solid var(--line) !important; border-radius:6px; background:var(--surface);
  padding:0 12px 12px !important; gap:0.6rem; overflow:hidden;}
/* a standalone header (direct child of the markdown container) bleeds to the box
   edges; the one nested inside a pure-HTML .gf-pane must not move */
[data-testid="stMarkdownContainer"] > .gf-pane-hd{
  margin:0 -12px 2px; border-radius:5px 5px 0 0;}

/* numerals: vitals, labs, confidences, times all align */
.gf-num, .gf-num *{font-variant-numeric:tabular-nums; font-feature-settings:'tnum' 1;}
/* identifiers only: gene symbols, accessions, sample ids */
.gf-id, .gf-id *{font-family:ui-monospace,'SF Mono',Menlo,monospace;
  font-variant-numeric:tabular-nums; letter-spacing:-.01em;}

/* panes */
.gf-pane{background:var(--surface); border:1px solid var(--line); border-radius:6px;}
.gf-pane-hd{display:flex; align-items:center; justify-content:space-between;
  gap:8px; padding:6px 12px; border-bottom:1px solid var(--line);
  background:var(--fill); border-radius:6px 6px 0 0;}
/* neutralise Streamlit's heading styling wherever it can reach our markup */
.gf-pane-hd .gf-pane-ttl, .gf-pane-hd h2{margin:0 !important; padding:0 !important;
  font-size:.69rem !important; font-weight:700; letter-spacing:.06em; line-height:1.35;
  text-transform:uppercase; color:var(--ink-60); scroll-margin:0;}
.gf-pane-hd a, .gf-pane-hd [data-testid="stHeaderActionElements"]{display:none !important;}
.gf-pane-hd .gf-hd-meta{font-size:.7rem; color:var(--ink-45); white-space:nowrap;}
.gf-pane-bd{padding:11px 13px;}

/* dense data grid */
table.gf-grid{width:100%; border-collapse:collapse; font-size:.8rem;}
table.gf-grid caption{position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0);}
table.gf-grid th{text-align:left; padding:5px 10px; font-size:.66rem; font-weight:700;
  letter-spacing:.06em; text-transform:uppercase; color:var(--ink-60);
  background:var(--fill); border-bottom:1px solid var(--line-60); white-space:nowrap;}
table.gf-grid td{padding:7px 10px; border-bottom:1px solid var(--line);
  vertical-align:middle; color:var(--ink);}
table.gf-grid tbody tr:last-child td{border-bottom:none;}
table.gf-grid tbody tr:hover td{background:#F8FAFC;}
table.gf-grid td.gf-drug{font-weight:600; white-space:nowrap;}
table.gf-grid td .gf-sub{font-size:.68rem; color:var(--ink-45); font-weight:400;}

/* key/value strip */
.gf-strip{display:flex; flex-wrap:wrap; gap:0 22px; padding:8px 12px;}
.gf-strip dt{font-size:.63rem; font-weight:700; letter-spacing:.06em;
  text-transform:uppercase; color:var(--ink-45); margin:0;}
.gf-strip dd{margin:1px 0 0; font-size:.8rem; font-weight:600; color:var(--ink);}

/* charts are reference material, not the headline: never let one upscale over its
   own caption or push the grid off screen */
.gf-chart-cap{display:block; font-size:.7rem; font-weight:600; color:var(--ink-60);
  line-height:1.4; margin:2px 0 6px;}
[data-testid="stImage"], [data-testid="stImageContainer"], .stImage{margin-top:2px;}
/* Capped in CSS, not by use_container_width: recent Streamlit ignores that flag for
   st.pyplot and stretches the PNG to the column, which upscales a 440px chart to
   700px and dwarfs the grid it is meant to annotate. Constrain the HEIGHT too:
   Streamlit saves each figure with a tight bounding box, so a square chart crops
   narrower than a wide one and, pinned to the same width, would be magnified more
   and carry visibly larger type than the chart beside it. */
[data-testid="stImage"] img, [data-testid="stImageContainer"] img, .stImage img,
[data-testid="stFullScreenFrame"] img{
  max-width:min(100%, 460px) !important; max-height:300px !important;
  width:auto !important; height:auto !important; display:block;}

/* streamlit widgets, compacted */
[data-testid="stWidgetLabel"]{margin-bottom:1px;}
[data-testid="stWidgetLabel"] p{font-size:.7rem; font-weight:600; color:var(--ink-60);
  letter-spacing:.02em; margin-bottom:3px; line-height:1.35;}
[data-baseweb="select"] > div, .stTextInput input{
  border-radius:5px; border-color:var(--line-60); font-size:.8rem; min-height:34px;}
.stTextInput input{color:var(--ink);}
[data-testid="stFileUploaderDropzone"]{padding:10px 12px; background:var(--fill);
  border:1px dashed var(--line-60); border-radius:5px;}
[data-testid="stFileUploaderDropzone"] small{font-size:.68rem;}
[role="radiogroup"]{gap:2px;}
[role="radiogroup"] label p{font-size:.78rem; color:var(--ink);}
[data-testid="stExpander"]{border:1px solid var(--line); border-radius:6px;
  background:var(--surface);}
[data-testid="stExpander"] summary p{font-size:.76rem; font-weight:600; color:var(--ink-60);}
[data-testid="stExpander"] [data-testid="stExpanderDetails"]{padding-top:2px;}

/* blue = primary action, and nothing else */
.stButton>button[kind="primary"]{background:var(--action); border:1px solid var(--action);
  color:#fff; border-radius:5px; font-weight:600; font-size:.8rem; padding:.4rem .8rem;
  min-height:34px;}
.stButton>button[kind="primary"]:hover{background:var(--action-d); border-color:var(--action-d);}
.stButton>button[kind="secondary"], .stDownloadButton>button{background:var(--surface);
  border:1px solid var(--line-60); color:var(--ink); border-radius:5px; font-weight:600;
  font-size:.75rem; padding:.3rem .7rem; min-height:30px;}
.stDownloadButton>button:hover{border-color:var(--action); color:var(--action-d);}

/* accessibility floor */
*:focus-visible{outline:2px solid var(--action); outline-offset:2px; border-radius:3px;}
.stButton>button:focus-visible, .stDownloadButton>button:focus-visible{
  outline:2px solid var(--action); outline-offset:2px;}
@media (prefers-reduced-motion: reduce){*{animation:none!important; transition:none!important;}}

/* stack the split pane on narrow screens */
@media (max-width:900px){
  [data-testid="stHorizontalBlock"]{flex-direction:column;}
  [data-testid="stHorizontalBlock"] > div{width:100%!important; flex:1 1 100%!important;}
}
</style>
"""


# ---- trust surface --------------------------------------------------------
def safety_banner() -> str:
    return (
        f'<div role="note" style="display:flex;gap:8px;align-items:baseline;'
        f'background:{WARN_BG};border:1px solid #FDE68A;border-left:3px solid {WARN};'
        f'border-radius:5px;padding:6px 12px;margin-bottom:6px;font-size:.76rem;'
        f'color:{INK};line-height:1.45;">'
        f'<b style="color:{WARN};letter-spacing:.03em;font-size:.68rem;'
        f'text-transform:uppercase;">Research prototype</b>'
        f'<span>Confirm every result with standard laboratory testing. This tool '
        f'supports a clinician\'s decision — it does not make one.</span></div>'
    )


def topbar(species: str, drugs: list[str], mode_note: str = "") -> str:
    """One dense strip: identity, coverage, backend state. No hero."""
    covered = ", ".join(d.lower() for d in drugs)
    note = (
        f'<span style="font-size:.68rem;font-weight:600;color:{WARN};background:{WARN_BG};'
        f'border:1px solid #FDE68A;border-radius:4px;padding:1px 7px;">{mode_note}</span>'
        if mode_note else ""
    )
    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'gap:14px;flex-wrap:wrap;border-bottom:1px solid {LINE_60};'
        f'padding-bottom:7px;margin-bottom:8px;">'
        f'<div style="display:flex;align-items:baseline;gap:10px;">'
        f'<span style="font-size:1.02rem;font-weight:700;letter-spacing:-.015em;color:{INK};">'
        f'Genome Firewall</span>'
        f'<span style="font-size:.76rem;color:{INK_45};">Predicted antibiotic response</span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:10px;font-size:.72rem;color:{INK_60};">'
        f'<span><b style="color:{INK};">Covers</b> <i>{species}</i> · {covered}</span>{note}</div>'
        f'</div>'
    )


def coverage_line(species: str, supported_drugs: list[str]) -> str:
    drugs = ", ".join(d.lower() for d in supported_drugs)
    return (
        f'<div style="font-size:.72rem;color:{INK_60};line-height:1.5;">'
        f'<b style="color:{INK};">In coverage.</b> {species} · {drugs}.<br>'
        f'<b style="color:{INK};">Out of scope.</b> Sample collection, species '
        f'identification, genome reconstruction, and every other species or antibiotic.'
        f'</div>'
    )


# ---- pane scaffolding -----------------------------------------------------
# Two kinds of pane, and the distinction matters:
#   pane()        — self-contained HTML, emitted in ONE markdown call.
#   pane_header() — the header bar for a pane whose body is Streamlit widgets;
#                   put it inside `st.container(border=True)`, which draws the box.
# Never open a <section> in one markdown call and close it in another: Streamlit
# closes unclosed tags at the end of each block, so the box would wrap nothing and
# the following widget would ride up over its bottom edge.
def pane_header(title: str, meta: str = "") -> str:
    # A div with heading semantics, not an <h2>: Streamlit restyles real headings
    # (1rem of padding) and injects an anchor link into them, which made every pane
    # header overflow its slot and collide with the element below.
    meta_html = f'<span class="gf-hd-meta">{meta}</span>' if meta else ""
    return (f'<div class="gf-pane-hd">'
            f'<div class="gf-pane-ttl" role="heading" aria-level="2">{title}</div>'
            f'{meta_html}</div>')


def pane(title: str, inner: str, meta: str = "", pad: bool = True) -> str:
    body = f'<div class="gf-pane-bd">{inner}</div>' if pad else f"<div>{inner}</div>"
    return f'<section class="gf-pane">{pane_header(title, meta)}{body}</section>'


# ---- isolate identity strip ----------------------------------------------
def isolate_strip(result) -> str:
    novelty_color = WARN if result.is_ood else INK
    items = [
        ("Isolate", f'<span class="gf-id">{result.genome_id}</span>'),
        ("Species", f'<i>{result.species}</i>'),
        ("Lineage", f'<span class="gf-id">{result.mlst_or_cluster or "unknown"}</span>'),
        ("Novelty", f'<span class="gf-num" style="color:{novelty_color};">'
                    f'{result.novelty_score:.0%}</span>'),
        ("Signal to decision", f'<span class="gf-num">{result.speed_seconds:.1f}s</span>'),
    ]
    cells = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in items)
    return f'<dl class="gf-strip" style="margin:0;">{cells}</dl>'


# ---- signature: call · calibrated interval · evidence provenance ----------
def call_chip(verdict: Verdict) -> str:
    label = CALL_TEXT[verdict]
    if verdict == Verdict.NO_CALL:
        return (
            f'<span class="gf-num" role="img" aria-label="Withheld, no call" '
            f'style="display:inline-block;padding:1px 8px;border-radius:4px;font-size:.66rem;'
            f'font-weight:700;letter-spacing:.04em;color:{INK_60};border:1px solid {LINE_60};'
            f'background-image:{_HATCH};">{label}</span>'
        )
    color = CALL_COLOR[verdict]
    return (
        f'<span class="gf-num" role="img" aria-label="{CALL_LABEL[verdict]}" '
        f'style="display:inline-block;padding:1px 8px;border-radius:4px;font-size:.66rem;'
        f'font-weight:700;letter-spacing:.04em;color:#fff;background:{color};">{label}</span>'
    )


def interval_bar(p) -> str:
    """Calibrated confidence as an interval, never a fake-precise single number."""
    if p.verdict == Verdict.NO_CALL or p.confidence is None:
        return (
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<div style="flex:1;height:8px;border-radius:4px;border:1px solid {LINE_60};'
            f'background-image:{_HATCH};"></div>'
            f'<span class="gf-num" style="font-size:.72rem;color:{INK_45};min-width:88px;">'
            f'withheld</span></div>'
        )
    color = CALL_COLOR[p.verdict]
    pt, lo, hi, has_interval = confidence_bounds(p)
    band = max(hi - lo, 1)
    # Without a real interval the number is a point estimate; label it as one rather
    # than printing a zero-width band that looks like a measurement.
    readout = (f'{pt}%<span style="color:{INK_45};font-weight:400;"> [{lo}–{hi}]</span>'
               if has_interval else
               f'{pt}%<span style="color:{INK_45};font-weight:400;"> point</span>')
    aria = (f"Calibrated confidence {pt} percent, interval {lo} to {hi}" if has_interval
            else f"Calibrated confidence {pt} percent, point estimate, no interval reported")
    return (
        f'<div style="display:flex;align-items:center;gap:8px;" role="img" '
        f'aria-label="{aria}">'
        f'<div style="position:relative;flex:1;height:8px;border-radius:4px;background:{FILL};'
        f'border:1px solid {LINE};min-width:70px;">'
        + (f'<div style="position:absolute;left:{lo}%;width:{band}%;top:0;bottom:0;'
           f'background:{color};opacity:.28;border-radius:4px;"></div>' if has_interval else "")
        + f'<div style="position:absolute;left:{pt}%;top:-3px;width:2px;height:12px;'
        f'background:{color};"></div></div>'
        f'<span class="gf-num" style="font-size:.75rem;color:{INK};min-width:88px;'
        f'font-weight:600;">{readout}</span></div>'
    )


def evidence_mark(cat: EvidenceCategory) -> str:
    """Shape and weight carry the provenance so it survives without color."""
    if cat == EvidenceCategory.KNOWN_GENE:
        glyph, gcol, txt, tcol, weight = "◆", INK, "known gene", INK, 600
    elif cat == EvidenceCategory.STATISTICAL:
        glyph, gcol, txt, tcol, weight = "◇", INK_45, "statistical only", INK_60, 400
    else:
        glyph, gcol, txt, tcol, weight = "·", INK_45, "no signal", INK_45, 400
    return (
        f'<span style="white-space:nowrap;"><span style="font-size:.8rem;color:{gcol};">'
        f'{glyph}</span> <span style="font-size:.73rem;color:{tcol};font-weight:{weight};">'
        f'{txt}</span></span>'
    )


# ---- evidence selection ---------------------------------------------------
def clean(value) -> str:
    """Backend nulls ('nan', None, '') must never reach a clinician as text."""
    text = str(value).strip() if value is not None else ""
    return "—" if text.lower() in ("", "nan", "none", "null") else text


def gene_label(symbol: str) -> str:
    """Render a backend feature id as the identifier a clinician recognises.

    The E. coli backend cites features by schema id (``gene::blaTEM-1``,
    ``mutation::gyrA::S83L``). The collaborator demo already cites bare symbols, so
    anything without the ``::`` prefix passes through untouched.
    """
    text = str(symbol or "").strip()
    if text.startswith("gene::"):
        return text.split("::", 1)[1]
    if text.startswith("mutation::"):
        parts = text.split("::")
        return f"{parts[1]} {parts[2]}" if len(parts) >= 3 else text.split("::", 1)[1]
    return text


# Backend reason codes are machine tokens. A clinician reads the sentence, never the
# token; anything unmapped falls through to the backend's own wording.
_REASON_TEXT = {
    "calibrated_probability_within_no_call_band":
        "the calibrated probability fell between the decision thresholds",
    "absence_of_resistance_markers_does_not_establish_susceptibility":
        "no resistance marker was found, and absence of a marker does not establish "
        "susceptibility",
    "known_marker_conflicts_with_model_probability":
        "a known resistance marker conflicts with the model's probability",
    "input_or_schema_warning":
        "this genome carries features the model was not trained on",
}


def humanize_reason(text: str) -> str:
    """Turn one or more backend reason codes into a plain clinical sentence."""
    raw = (text or "").strip()
    if not raw:
        return ""
    parts = []
    for chunk in (piece.strip() for piece in raw.split(";")):
        if not chunk:
            continue
        mapped = _REASON_TEXT.get(chunk)
        if mapped is None and chunk.startswith("unknown_model_feature:"):
            mapped = (f"the genome carries a feature the model was not trained on "
                      f"({gene_label(chunk.split(':', 1)[1])})")
        parts.append(mapped or chunk.replace("_", " "))
    sentence = "; ".join(parts).rstrip(". ")
    return sentence[0].upper() + sentence[1:] if sentence else ""


def confidence_bounds(p):
    """(point, low, high, has_interval) as percentages.

    A backend that reports no interval sets ci_low == ci_high == confidence. Printing
    that as "99% [99-99]" would dress a point estimate up as a measured interval, so
    the caller renders a bare point estimate instead.
    """
    if p.confidence is None:
        return None, None, None, False
    point = int(round(p.confidence * 100))
    low = p.ci_low if p.ci_low is not None else p.confidence
    high = p.ci_high if p.ci_high is not None else p.confidence
    lo, hi = int(round(low * 100)), int(round(high * 100))
    return point, lo, hi, hi > lo


def cited_genes(p):
    """Only the determinants that actually back THIS drug's call.

    The backend attaches the genome-wide determinant set to every drug and marks
    the real cause with ``is_known_cause``. Listing the whole set per drug would
    present incidental genes as evidence, so a known-gene call cites only its
    curated causes and a no-signal call cites nothing. The full genome-wide set
    stays visible in the determinants pane.
    """
    cat = p.evidence_category
    if cat == EvidenceCategory.KNOWN_GENE:
        known = [g for g in p.supporting_genes if g.is_known_cause]
        return known or list(p.supporting_genes)
    if cat == EvidenceCategory.STATISTICAL:
        return list(p.supporting_genes)
    return []


# ---- the antibiogram grid -------------------------------------------------
def antibiogram(predictions) -> str:
    head = (
        "<tr><th scope='col'>Antibiotic</th><th scope='col'>Call</th>"
        "<th scope='col' style='width:230px;'>Calibrated confidence</th>"
        "<th scope='col'>Evidence</th><th scope='col'>Cited determinants</th></tr>"
    )
    rows = []
    for p in predictions:
        genes = ", ".join(gene_label(g.symbol) for g in cited_genes(p)) or "—"
        rows.append(
            "<tr>"
            f'<td class="gf-drug">{p.drug}<div class="gf-sub">{p.drug_class}</div></td>'
            f"<td>{call_chip(p.verdict)}</td>"
            f"<td>{interval_bar(p)}</td>"
            f"<td>{evidence_mark(p.evidence_category)}</td>"
            f'<td class="gf-id" style="font-size:.72rem;color:{INK_60};">{genes}</td>'
            "</tr>"
        )
    return (
        '<table class="gf-grid"><caption>Predicted antibiotic response by drug</caption>'
        f'<thead>{head}</thead><tbody>{"".join(rows)}</tbody></table>'
    )


# keep the previous name working
report_table = antibiogram


# ---- evidence detail pane -------------------------------------------------
def evidence_detail(p) -> str:
    gate = ("not assessed" if p.target == "not assessed"
            else ("present" if p.target_present else "absent (intrinsic resistance)"))
    out = [
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'gap:8px;margin-bottom:7px;">'
        f'<span style="font-size:.86rem;font-weight:700;color:{INK};">{p.drug}</span>'
        f'{call_chip(p.verdict)}</div>',
    ]
    # The backend often sets `reasoning` to the withheld reason verbatim; showing
    # both would print the same sentence twice in a pane that must stay scannable.
    reason = (p.reasoning or "").strip()
    withheld = (p.no_call_reason or "").strip()
    if reason and not (withheld and echoes(reason, withheld)):
        out.append(f'<div style="font-size:.76rem;color:{INK_60};line-height:1.5;'
                   f'margin-bottom:8px;">{reason}</div>')
    if withheld:
        text = humanize_reason(withheld)
        out.append(
            f'<div style="font-size:.73rem;color:{INK};background:{FILL};'
            f'border-left:3px solid {NOCALL};border-radius:0 4px 4px 0;padding:5px 9px;'
            f'margin-bottom:8px;"><b>Withheld.</b> {text}. '
            f'Withholding is deliberate, not an error.</div>')

    out.append(_kv_row("Target gate", f'<span class="gf-id">{gate}</span>'))
    out.append(_kv_row("Target", p.target))
    out.append(_kv_row("Calibration",
                       "calibrated" if p.calibrated else "uncalibrated — treat with caution"))

    cat = p.evidence_category
    cited = cited_genes(p)
    if cat == EvidenceCategory.KNOWN_GENE and cited:
        out.append(_section("Curated cause for this drug"))
        for g in cited:
            detail = " · ".join(x for x in (clean(g.element_name), clean(g.method),
                                            clean(g.subclass)) if x != "—") or "—"
            out.append(
                f'<div style="padding:4px 0;border-bottom:1px solid {LINE};">'
                f'<span class="gf-id" style="font-size:.76rem;font-weight:600;color:{INK};">'
                f'{gene_label(g.symbol)}</span>'
                f'<div style="font-size:.7rem;color:{INK_45};line-height:1.4;">{detail}</div>'
                f'</div>')
    elif cat == EvidenceCategory.STATISTICAL:
        genes = ", ".join(gene_label(g.symbol) for g in cited) or "model features"
        out.append(_section("Statistical association only"))
        out.append(
            f'<div style="font-size:.75rem;color:{INK_60};line-height:1.5;">No curated '
            f'cause for this drug was detected. The call rests on association across the '
            f'detected determinant set '
            f'(<span class="gf-id" style="color:{INK};">{genes}</span>).</div>'
            f'<div style="font-size:.72rem;color:{WARN};background:{WARN_BG};'
            f'border:1px solid #FDE68A;border-radius:4px;padding:5px 9px;margin-top:5px;'
            f'line-height:1.45;"><b>Caveat.</b> Feature importance is not proof of a '
            f'biological cause. Treat this as weaker than a curated mechanism.</div>')
    else:
        out.append(_section("Evidence"))
        out.append(
            f'<div style="font-size:.75rem;color:{INK_45};line-height:1.5;">No known '
            f'resistance determinant was detected for this drug. Determinants found '
            f'elsewhere in the genome are listed in the determinants pane and do not '
            f'support this call.</div>')
    return "".join(out)


def echoes(text: str, other: str) -> bool:
    """True when the two strings say the same thing modulo punctuation/case."""
    def norm(s):
        return " ".join("".join(c for c in s.lower() if c.isalnum() or c.isspace()).split())
    a, b = norm(text), norm(other)
    return bool(a and b) and (b in a or a in b)


def _kv_row(k: str, v: str) -> str:
    return (f'<div style="display:flex;justify-content:space-between;gap:10px;'
            f'padding:4px 0;border-bottom:1px solid {LINE};font-size:.75rem;">'
            f'<span style="color:{INK_45};">{k}</span>'
            f'<span style="color:{INK};font-weight:500;text-align:right;">{v}</span></div>')


def _section(title: str) -> str:
    return (f'<div style="font-size:.63rem;font-weight:700;letter-spacing:.06em;'
            f'text-transform:uppercase;color:{INK_45};margin:10px 0 3px;">{title}</div>')


# ---- determinants ---------------------------------------------------------
def determinant_chips(genes) -> str:
    if not genes:
        return f'<div style="font-size:.75rem;color:{INK_45};">None detected.</div>'
    chips = "".join(
        f'<span class="gf-id" title="{clean(g.element_name)}" style="background:{FILL};'
        f'border:1px solid {LINE};border-radius:4px;padding:1px 6px;font-size:.72rem;'
        f'color:{INK};margin:0 3px 3px 0;display:inline-block;">{gene_label(g.symbol)}</span>'
        for g in genes)
    return f'<div style="line-height:1.7;">{chips}</div>'


# ---- performance ----------------------------------------------------------
def kpi_row(items) -> str:
    """items: [(label, value, hint)]"""
    cells = "".join(
        f'<div style="flex:1;min-width:120px;padding:7px 12px;border-right:1px solid {LINE};">'
        f'<div style="font-size:.62rem;font-weight:700;letter-spacing:.06em;'
        f'text-transform:uppercase;color:{INK_45};">{label}</div>'
        f'<div class="gf-num" style="font-size:1.05rem;font-weight:700;color:{INK};'
        f'line-height:1.3;">{value}</div>'
        f'<div style="font-size:.66rem;color:{INK_45};">{hint}</div></div>'
        for label, value, hint in items)
    return (f'<div style="display:flex;flex-wrap:wrap;border-bottom:1px solid {LINE};">'
            f'{cells}</div>')


def metrics_grid(metrics) -> str:
    cols = ["Drug", "AUROC", "PR-AUC", "Recall R", "Recall S",
            "Grouped / random", "Brier", "No-call"]
    head = "".join(f"<th scope='col'>{c}</th>" for c in cols)
    rows = []
    for m in metrics:
        rows.append(
            "<tr>"
            f'<td class="gf-drug">{m.drug}</td>'
            f'<td class="gf-num">{m.auroc:.2f}</td>'
            f'<td class="gf-num">{m.pr_auc:.2f}</td>'
            f'<td class="gf-num">{m.recall_resistant:.2f}</td>'
            f'<td class="gf-num">{m.recall_susceptible:.2f}</td>'
            f'<td class="gf-num">{m.balanced_acc_grouped:.2f}'
            f'<span style="color:{INK_45};"> / {m.balanced_acc_random:.2f}</span></td>'
            f'<td class="gf-num">{m.brier:.2f}</td>'
            f'<td class="gf-num">{m.no_call_rate:.0%}</td></tr>')
    return (f'<table class="gf-grid"><caption>Held-out performance by drug</caption>'
            f'<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>')


# ---- states ---------------------------------------------------------------
def notice(text: str, level: str = "info") -> str:
    color, bg, border = {
        "info": (INK_60, SURFACE, LINE_60),
        "warn": (WARN, WARN_BG, "#FDE68A"),
        "critical": (FAIL, FAIL_BG, "#FECDD3"),
    }[level]
    return (f'<div role="note" style="background:{bg};border:1px solid {border};'
            f'border-left:3px solid {color};border-radius:5px;padding:6px 11px;'
            f'margin:6px 0;font-size:.76rem;color:{INK};line-height:1.45;">{text}</div>')


def empty_state(species: str) -> str:
    return (
        f'<div style="border:1px dashed {LINE_60};border-radius:6px;padding:26px 20px;'
        f'text-align:center;background:{SURFACE};">'
        f'<div style="font-weight:700;color:{INK};font-size:.86rem;margin-bottom:3px;">'
        f'No genome loaded</div>'
        f'<div style="font-size:.76rem;color:{INK_60};line-height:1.5;">'
        f'Select a bundled <i>{species}</i> sample, or upload a quality-checked FASTA, '
        f'then run the analysis to see the predicted antibiotic response.</div></div>'
    )


def wordmark() -> str:
    return (
        f'<div style="display:flex;align-items:baseline;gap:10px;">'
        f'<span style="font-size:1.02rem;font-weight:700;letter-spacing:-.015em;'
        f'color:{INK};">Genome Firewall</span>'
        f'<span style="color:{INK_45};font-size:.76rem;">Predicted antibiotic response</span>'
        f'</div>'
    )
