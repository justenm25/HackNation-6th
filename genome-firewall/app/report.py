"""Downloadable, print-ready clinical antibiotic-response report (HTML).

Deterministic (no LLM required). Monochrome slate; call colors only on the calls.
"""
from __future__ import annotations
from datetime import datetime
from src.contract import Verdict, DISCLAIMER, DEFENSIVE_NOTE

_CALL = {Verdict.FAIL: ("#A4373A", "Likely to fail"),
         Verdict.WORK: ("#1F7A5A", "Likely to work"),
         Verdict.NO_CALL: ("#8A8F98", "No-call — withheld")}
_EV = {"known_gene": "Known resistance gene / DNA change",
       "statistical": "Statistical association only (not proven causal)",
       "no_signal": "No known resistance signal"}


def build_html_report(result) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for p in result.predictions:
        color, label = _CALL[p.verdict]
        if p.confidence is None:
            conf = "withheld"
        else:
            lo = int(round((p.ci_low or p.confidence) * 100))
            hi = int(round((p.ci_high or p.confidence) * 100))
            conf = f"{p.confidence:.0%} [{lo}–{hi}]"
        genes = ", ".join(g.symbol for g in p.supporting_genes) or "—"
        nc = f"<div class='nc'>Withheld: {p.no_call_reason}</div>" if p.no_call_reason else ""
        rows.append(f"""
        <tr>
          <td class="drug">{p.drug}<div class="mut">{p.drug_class}</div></td>
          <td><span class="chip" style="color:{color};border-color:{color};">{label}</span></td>
          <td class="mono">{conf}</td>
          <td>{_EV[p.evidence_category.value]}</td>
          <td class="mono">{genes}</td>
        </tr>
        <tr class="reason"><td colspan="5">{p.reasoning}{nc}</td></tr>""")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Genome Firewall — antibiotic-response report</title>
<style>
  body{{font-family:'IBM Plex Sans',system-ui,sans-serif;color:#10212E;max-width:820px;
       margin:34px auto;padding:0 20px;line-height:1.5;background:#fff;}}
  .mono{{font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums;}}
  h1{{font-size:1.35rem;margin:0;}} .sub{{color:#5A6b78;margin:.2rem 0 1rem;font-size:.9rem;}}
  .banner{{background:#fff;border:1px solid #D8DEE6;border-left:4px solid #10212E;
           border-radius:6px;padding:9px 14px;font-size:.85rem;margin:12px 0;}}
  .meta{{display:flex;gap:26px;flex-wrap:wrap;border:1px solid #D8DEE6;border-radius:8px;
         padding:11px 16px;margin:12px 0;font-size:.85rem;}}
  .meta b{{display:block;color:#5A6b78;font-weight:600;font-size:.68rem;text-transform:uppercase;
           letter-spacing:.04em;}}
  table{{width:100%;border-collapse:collapse;font-size:.88rem;}}
  th{{text-align:left;color:#5A6b78;font-size:.68rem;text-transform:uppercase;letter-spacing:.04em;
      padding:6px 8px;border-bottom:1px solid #C4CAD2;}}
  td{{padding:8px 8px;border-bottom:1px solid #EAEDF1;vertical-align:top;}}
  td.drug{{font-weight:600;}} .mut{{color:#8A94A0;font-weight:400;font-size:.76rem;}}
  .chip{{border:1px solid;border-radius:4px;padding:1px 8px;font-size:.72rem;font-weight:600;
         font-family:'IBM Plex Mono',monospace;}}
  tr.reason td{{color:#5A6b78;font-size:.82rem;border-bottom:1px solid #EAEDF1;padding-top:0;}}
  .nc{{color:#A4373A;margin-top:2px;}}
  footer{{color:#8A94A0;font-size:.78rem;margin-top:22px;border-top:1px solid #D8DEE6;padding-top:10px;}}
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
    <th>Evidence</th><th>Supporting genes</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <footer>{DEFENSIVE_NOTE}<br>Every result must be confirmed by standard laboratory testing.</footer>
</body></html>"""
