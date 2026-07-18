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
- The UI chrome is near-monochrome slate. The ONLY saturated colors in the app are
  the three call states.
- Palette: --paper #F7F8FA, --ink #10212E, --line #D8DEE6,
  --fail #A4373A, --work #1F7A5A, --nocall #8A8F98 (hatched fill).
- Type: IBM Plex Sans for UI; IBM Plex Mono for ALL data (genes, mutations,
  accessions, sequences, confidence numerals) with tabular-nums.
- No landing hero — open directly on the tool.
- Signature element: per-antibiotic call + calibrated-confidence-interval +
  evidence-provenance mark. No-call is a deliberate "withheld" state, never an error.
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
