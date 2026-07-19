"""Downloadable, print-ready clinical antibiotic-response report (HTML).

Deterministic (no LLM required). Same tokens as app/theme.py: slate chrome,
tabular numerals, and saturated color only on the calls.
"""
from __future__ import annotations
from datetime import datetime
from src.contract import Verdict, DISCLAIMER, DEFENSIVE_NOTE
from app.theme import (
    cited_genes, confidence_bounds, echoes, gene_label, humanize_reason,
)

_CALL = {Verdict.FAIL: ("#BE123C", "Likely to fail"),
         Verdict.WORK: ("#047857", "Likely to work"),
         Verdict.NO_CALL: ("#64748B", "No-call — withheld")}
_EV = {"known_gene": "Known resistance gene / DNA change",
       "statistical": "Statistical association only (not proven causal)",
       "no_signal": "No known resistance signal"}


def build_html_report(result) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for p in result.predictions:
        color, label = _CALL[p.verdict]
        point, lo, hi, has_interval = confidence_bounds(p)
        if point is None:
            conf = "withheld"
        else:
            # No interval from the backend means a point estimate; say so rather than
            # printing a zero-width band that reads as a measurement.
            conf = f"{point}% [{lo}–{hi}]" if has_interval else f"{point}% (point)"
        genes = ", ".join(gene_label(g.symbol) for g in cited_genes(p)) or "—"
        # The backend often repeats the withheld reason as the reasoning text.
        reason = (p.reasoning or "").strip()
        raw_withheld = (p.no_call_reason or "").strip()
        withheld = humanize_reason(raw_withheld)
        nc = f"<div class='nc'>Withheld: {withheld}</div>" if withheld else ""
        # Compare against the raw code: the adapter sets `reasoning` to the same
        # string, and humanizing it first would hide that they are duplicates.
        if raw_withheld and echoes(reason, raw_withheld):
            reason = ""
        rows.append(f"""
        <tr>
          <td class="drug">{p.drug}<div class="mut">{p.drug_class}</div></td>
          <td><span class="chip" style="color:{color};border-color:{color};">{label}</span></td>
          <td class="mono">{conf}</td>
          <td>{_EV[p.evidence_category.value]}</td>
          <td class="mono">{genes}</td>
        </tr>
        <tr class="reason"><td colspan="5">{reason}{nc}</td></tr>""")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Genome Firewall — antibiotic-response report</title>
<style>
  body{{font-family:'Inter',-apple-system,'SF Pro Text',system-ui,sans-serif;color:#0F172A;
       max-width:860px;margin:28px auto;padding:0 20px;line-height:1.45;background:#fff;
       font-variant-numeric:tabular-nums;}}
  .mono{{font-family:ui-monospace,'SF Mono',Menlo,monospace;font-variant-numeric:tabular-nums;}}
  h1{{font-size:1.2rem;margin:0;letter-spacing:-.015em;}}
  .sub{{color:#64748B;margin:.2rem 0 .8rem;font-size:.82rem;}}
  .banner{{background:#FFFBEB;border:1px solid #FDE68A;border-left:3px solid #B45309;
           border-radius:5px;padding:7px 12px;font-size:.78rem;margin:10px 0;}}
  .banner b{{color:#B45309;}}
  .meta{{display:flex;gap:22px;flex-wrap:wrap;border:1px solid #E2E8F0;border-radius:6px;
         padding:9px 14px;margin:10px 0;font-size:.8rem;}}
  .meta b{{display:block;color:#64748B;font-weight:700;font-size:.62rem;text-transform:uppercase;
           letter-spacing:.06em;}}
  table{{width:100%;border-collapse:collapse;font-size:.8rem;}}
  th{{text-align:left;color:#475569;font-size:.62rem;text-transform:uppercase;letter-spacing:.06em;
      font-weight:700;padding:5px 8px;background:#F1F5F9;border-bottom:1px solid #CBD5E1;}}
  td{{padding:7px 8px;border-bottom:1px solid #E2E8F0;vertical-align:top;}}
  td.drug{{font-weight:600;}} .mut{{color:#64748B;font-weight:400;font-size:.7rem;}}
  .chip{{border:1px solid;border-radius:4px;padding:1px 7px;font-size:.66rem;font-weight:700;
         letter-spacing:.04em;white-space:nowrap;}}
  tr.reason td{{color:#475569;font-size:.75rem;border-bottom:1px solid #E2E8F0;padding-top:0;}}
  .nc{{color:#BE123C;margin-top:2px;}}
  footer{{color:#64748B;font-size:.72rem;margin-top:18px;border-top:1px solid #E2E8F0;padding-top:9px;}}
  @media print{{body{{margin:0;}} .banner{{border-left-width:3px;}}}}
</style></head><body>
  <h1>Genome Firewall — antibiotic-response report</h1>
  <div class="sub">Research prototype · decision support only · generated {ts}</div>
  <div class="banner"><b>Research prototype.</b> Confirm every result with standard laboratory testing.</div>
  <div class="meta">
    <div><b>Isolate</b><span class="mono">{result.genome_id}</span></div>
    <div><b>Species</b>{result.species}</div>
    <div><b>Lineage</b><span class="mono">{result.mlst_or_cluster or "unknown"}</span></div>
    <div><b>Novelty</b><span class="mono">{result.novelty_score:.0%}</span>{" · out-of-distribution" if result.is_ood else ""}</div>
    <div><b>Signal to decision</b><span class="mono">{result.speed_seconds:.1f}s</span></div>
  </div>
  <table>
    <thead><tr><th>Antibiotic</th><th>Call</th><th>Calibrated confidence</th>
    <th>Evidence</th><th>Cited determinants</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <footer>{DEFENSIVE_NOTE}<br>Every result must be confirmed by standard laboratory testing.</footer>
</body></html>"""
