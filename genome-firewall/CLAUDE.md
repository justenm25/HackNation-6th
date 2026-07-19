# Genome Firewall — project rules

## What this is
A strictly DEFENSIVE decision-support prototype. Input: a quality-checked FASTA
for ONE supported bacterial species. Output: per antibiotic, a call
(likely to fail / likely to work / no-call), a calibrated confidence, and the
supporting genes/DNA changes. Required demo: Streamlit.

## Mental model (read before touching the UI)
You are building a **clinical instrument** — an antibiogram / diagnostic lab report
a doctor reads under time pressure and must trust. NOT a website. Every "make it pop"
instinct — hero section, gradient, emoji, three feature cards, marketing copy — is
wrong here and costs points. Trust, legibility, and honestly-shown uncertainty ARE
the aesthetic.

## Hard rules (never break)
- Defensive only. NEVER design, modify, strengthen, or optimize an organism.
- Every result needs a real no-call option; withholding on weak/conflicting/
  out-of-distribution evidence is a strength, not a failure.
- Separate a KNOWN resistance gene/mutation from a merely STATISTICAL association.
  A SHAP/importance value is not proof of biological cause — never imply it is.
- Confidence must be calibrated and shown honestly (interval, not a fake precise %).
- A persistent, non-dismissable banner: "Research prototype — confirm every result
  with standard laboratory testing." Human oversight is required.
- State coverage explicitly: which species + antibiotics are and are NOT covered.

## Scope of the modules (build in this order)
1. Genome Reader: FASTA -> features (presence/absence of known AMR genes and
   mutations) via AMRFinderPlus. Documented, repeatable path; specified output format.
2. Predictor: one regularized logistic-regression model per antibiotic on those
   features. Apply a deterministic gate on the drug's molecular target so we never
   say "likely to work" purely from absent resistance markers. De-duplicate the
   training set by sequence homology; report on a grouped (by genetic similarity)
   held-out split — never random rows.
3. Decision Report (the Streamlit UI): the report described in the design system.

## Design system (follow exactly)
Revised 2026-07-18 to the high-density EHR system below. `app/theme.py` is the single
source of truth for tokens; import from it rather than hard-coding hex values.

- Layout: a dense split pane — input rail, antibiogram, evidence/provenance. No
  landing hero, no large cards, no floating layout. Open directly on the tool.
- Chrome is slate. Blue is reserved for primary actions and NEVER encodes a result.
- Palette: --canvas #F8FAFC, --surface #FFFFFF, --ink #0F172A (slate-900),
  --ink-60 #475569, --ink-45 #64748B (lightest text that still passes AA),
  --line #E2E8F0, --action #2563EB (blue-600, primary action only).
- State: --work #047857 (emerald-700), --warn #B45309 (amber-700),
  --fail #BE123C (rose-700), --nocall #64748B with a hatched fill. No gradients.
- Type: Inter (SF Pro fallback) throughout. Every numeral — confidences, intervals,
  metrics, times — carries tabular-nums via `.gf-num`. Identifiers only (gene
  symbols, accessions, sample ids) use mono via `.gf-id`.
- Density: compact padding, 5–7px in grid cells; maximize data above the fold.
- Accessibility: WCAG 2.1 AA contrast (token comments record the ratios), a visible
  2px blue focus ring on every interactive element, reduced motion respected, and
  meaning never carried by color alone (call chips are also labelled text).
- Signature element: per-antibiotic call + calibrated-confidence-interval +
  evidence-provenance mark. No-call is a deliberate "withheld" state, never an error.
- Evidence honesty: a drug cites ONLY the determinants that back its own call. The
  backend attaches the genome-wide set to every drug, so route it through
  `theme.cited_genes()`; the full set belongs in the determinants pane.
- Copy: active voice, plain, clinical, sentence case. Name things by what the user
  controls. Empty/error states give direction, not apologies or mood.

## Avoid (these are the AI-slop tells — reject them in your own output)
- The three default looks: (a) cream + serif + terracotta, (b) black + acid accent,
  (c) generic broadsheet hairline columns.
- Emoji, gradients, glassmorphism, hero sections, feature-card grids, marketing copy,
  st.balloons/st.snow, default st.table, decorative animation, fake-precise confidence.

## Quality floor
Responsive to mobile, visible keyboard focus, reduced motion respected. Build custom
HTML components for the report rather than relying on default Streamlit widgets.
