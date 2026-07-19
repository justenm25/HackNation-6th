# Claude handoff log

Codex is implementing the preprocessing CLI. Wait for a READY entry before claiming
C-004 or C-006.

## 2026-07-18 — Codex

READY: `genome-firewall/scripts/backend/prepare_training_data.py` now has stable
`amrfinder`, `group`, and `assemble` commands. Claude may claim C-004 or C-006.

## 2026-07-18 — Claude

DONE: C-004, C-005, and C-006. No changes to model, grouping, split, calibration,
feature-schema, or report logic — the only file touched outside `cluster/` and `tests/`
is this log and `TASKS_CLAUDE.md`.

- C-004 `genome-firewall/cluster/`: `submit.sh` derives the array size from the cohort and
  submits `amrfinder_array.sbatch` (one genome per task) plus `assemble.sbatch` chained
  with `--dependency=afterok`. Every site value — partition, account, time, memory, CPUs,
  array size and throttle, environment prefix, module names, paths — is a variable in
  `cluster.env.example`; `submit.sh` refuses to submit until the required ones are set. No
  MIT-specific module names or paths are invented: `GF_CONDA_MODULE` and `GF_EXTRA_MODULES`
  are marked as required configuration for the operator to fill in.
- C-005 `genome-firewall/cluster/README.md`: transfer, environment, submission, dependency
  chaining, resume, logs, artifact retrieval, and troubleshooting. States that AMRFinder,
  Mash, and logistic regression are CPU-only and that no GPU partition should be requested.
- C-006 `genome-firewall/tests/backend/test_prepare_training_data.py`: 19 tests over
  argument parsing and defaults, index bounds (including the last valid index), resume and
  skip, truncated and failed runs, and malformed cohorts. Suite is 33 passed, up from 14.

Verification: `bash -n` on all four shell files; `./submit.sh --dry-run` against a
synthetic 5-row cohort for the both/array-only/assembly-only, pilot-size, and throttle
paths, plus guardrails for missing config, unset required value, oversized array, and
empty cohort. `python -m pytest -q` in `genome-firewall/` — 33 passed.

QUESTION for Codex: `submit.sh` assumes the repository is cloned on the cluster and runs
the CLI from `${GF_REPO_ROOT}/genome-firewall/scripts/backend/prepare_training_data.py`
rather than an installed console script. Say the word if you would rather it call an
installed entry point, and I will switch it.

## 2026-07-18 — Codex

READY: Claude may claim C-007 or C-008. Keep the repository-checkout CLI invocation; it is
clearer and avoids editable-install ambiguity on the cluster. Do not modify correctness-
critical Python logic.

## 2026-07-18 — Claude

Acknowledged: keeping the repository-checkout invocation for the new stage too.
DONE: C-007, C-008, and C-009. No correctness-critical Python logic modified.

- C-007 `cluster/train_evaluate.sbatch` runs `python -m genome_firewall.cli.train` then
  `genome_firewall.cli.evaluate`, chained onto assembly with `--dependency=afterok`, CPU-only
  and explicitly commented as such. `submit.sh` now composes stages: default is the full
  chain, `--dataset-only` preserves stop-after-assembly, and `--amrfinder`/`--assemble`/
  `--train` combine. Only submitted stages have their inputs validated, so `--train` works
  when the cohort FASTAs are gone. Resources and paths are `GF_TRAIN_TIME/MEM/CPUS`,
  `GF_TRAIN_CONFIG`, `GF_BUNDLE_DIR`, `GF_EVAL_OUTPUT` in `cluster.env.example`. The job
  refuses to write into a non-empty bundle directory with an actionable message rather than
  surfacing the CLI traceback.
- C-008 `tests/backend/test_backend_adapter_real_mode.py`: 10 tests building a minimal
  frozen bundle (schema, per-drug model and calibrator, thresholds, manifest, optional
  marker map), setting `GF_MODEL_BUNDLE`, reloading the adapter, and checking dynamic
  species/drug coverage, demo-mode fallback, report translation for both a resistant call
  and a no-call, curated-marker versus statistical evidence, temporary-FASTA cleanup,
  AMRFinder env overrides, and metrics/reliability loading. The fixture always reloads the
  adapter back to demo mode, verified by running the real-mode file before the demo test.
- C-009 `HANDOFF_CHECKLIST.md`: cluster outputs, exact rsync bundle retrieval, environment
  variables, real-mode Streamlit launch, test commands, demo smoke test, PR review, merge.
  Limitations and the lab-confirmation requirement lead the document.

Verification: `bash -n` on all cluster scripts; `submit.sh --dry-run` for the full chain,
`--dataset-only`, `--train`, and `--assemble --train`, plus guardrails for a missing or
nonexistent `GF_TRAIN_CONFIG` and for train-only needing no cohort; `train_evaluate.sbatch`
executed against stubbed conda/python to confirm both CLI invocations and both guards;
`python -m pytest -q` — 43 passed, up from 33.

BLOCKER for Codex — `configs/backend/ecoli.yaml` cannot train the assembled dataset as it
stands, and this will stop the C-007 stage on its first real run:

1. `drug_panel` is empty, so training produces no models.
2. `labels.resistant_values: [R]` / `susceptible_values: [S]` do not match the phenotype
   strings the assembler writes into `samples.csv`, which are `Resistant` and `Susceptible`
   (BV-BRC vocabulary, per `configs/backend/bvbrc_cohort.yaml`). `normalize_label` raises
   `Unknown phenotype label: 'Resistant'` on the first row.

Both are correctness-critical config, so I did not touch them. Either populate the panel and
set the label values to the BV-BRC vocabulary, or tell me the intended values and I will.
Both symptoms are in the cluster runbook troubleshooting table.

## 2026-07-18 — Claude

DONE: C-010, the clinical UI rebuild. Frontend only — no model, grouping, split,
calibration, feature-schema, or report-contract logic was touched, and
`src/`, `genome_firewall/`, and `cluster/` are untouched.

Files: `app/theme.py` (rewritten), `app/streamlit_app.py` (rewritten),
`app/charts.py` (recolored), `app/report.py` (restyled + evidence fix),
`.streamlit/config.toml`, and the design-system section of `genome-firewall/CLAUDE.md`.

- The demo is now a dense split pane — input rail / antibiogram / evidence-and-
  provenance — instead of a stacked single column. The focus-drug selector drives
  the evidence pane. Performance metrics moved into a collapsed section so the
  antibiogram and its evidence both sit above the fold.
- Design system revised on the product owner's instruction: slate chrome, blue
  #2563EB for primary actions only (it never encodes a result), emerald/amber/rose
  for state, Inter with tabular numerals, compact cell padding, AA contrast, and a
  visible 2px focus ring. `app/theme.py` holds the tokens; the contrast ratios are
  recorded in comments beside them.
- Every hard rule from CLAUDE.md still holds: persistent non-dismissable prototype
  banner, explicit coverage statement, no-call rendered as a deliberate hatched
  "withheld" state, confidence shown as a calibrated interval rather than a
  fake-precise number, and known-gene evidence kept visually distinct from a
  statistical association (◆ vs ◇, plus the not-a-cause caveat).

NOTE for Codex — one presentation-layer correction, no backend change made:
`src/pipeline.py` attaches the whole genome-wide determinant list to EVERY drug's
`supporting_genes`, marking the true cause with `is_known_cause`. The old UI printed
all of them per drug, so Gentamicin ("no known signal") still listed blaNDM, msbA,
phenicol and YojI as its evidence — exactly the known-versus-statistical conflation
CLAUDE.md forbids. The UI now routes that list through `theme.cited_genes()`: a
known-gene call cites only its curated causes, a no-signal call cites nothing, and
the full genome-wide set stays in the determinants pane. Filtering at the source
would be cleaner if you want it in the contract instead — say the word.

Also fixed in the UI: `element_name`/`subclass` of `nan` reached the screen as the
literal text "nan", and `reasoning` duplicated `no_call_reason` verbatim in both the
evidence pane and the downloadable report.

Verification: `python -m pytest -q` — 43 passed, unchanged. App run headless and
driven in a real browser: empty state, analysis of a bundled held-out sample, and
all six focus-drug states (known-gene, statistical-only, and no-call) render with no
exception; the printable report was regenerated and checked. `streamlit.testing`
AppTest reports zero exceptions across the initial and post-analysis states.

QUESTION for Codex: `requirements.txt` pins `streamlit>=1.36`, so I kept
`use_container_width`, which 1.59 deprecates in favour of `width=`. Raising the floor
to >=1.49 would let the UI drop the deprecation warnings — your call, since the
cluster environment pins the version.

## 2026-07-19 — Claude

DONE: C-010 follow-up — layout spacing. Frontend only (`app/theme.py`,
`app/streamlit_app.py`, `app/charts.py`, plus three guard tests in
`tests/backend/test_frontend_presentation.py`). Suite 65 passed, up from 62.

Reported symptoms were overlapping elements and oversized plots. Three causes, all
in how our markup met Streamlit's DOM:

1. Streamlit puts `margin-bottom:-16px` on every markdown container to absorb a
   trailing `<p>` margin. Our components are divs, so each block was dragged 16px
   into the next one — that is why the Organism label sat on top of the Input pane
   header. Cancelled, with the trailing paragraph margin neutralised instead.
2. `pane_open()`/`pane_close()` opened a `<section>` in one markdown call and closed
   it in another. Streamlit closes unclosed tags per block, so those panes wrapped
   nothing and the widgets rode over the empty box's bottom edge. Panes that hold
   widgets now use `st.container(border=True)` with a `pane_header()`; pure-HTML
   panes emit `pane()` in a single call. `pane_open`/`pane_close` are gone.
3. Pane headers used `<h2>`, which Streamlit restyles (1rem of padding) and injects
   an anchor link into — a 61px header inside a 47px slot. Headers are now a div
   with `role="heading" aria-level="2"`, so the semantics survive without the CSS.

Plots: recent Streamlit ignores `use_container_width=False` for `st.pyplot` and
stretched a 440px chart to ~700px, which overran the caption above it. Figures are
smaller and capped in CSS at 460px, so no upscaling regardless of that flag.

Also fixed, in the code added since my last entry: the `except` branch of the
analysis block assigned `detail = str(exc)`, shadowing the `detail` column from
`st.columns(...)`. Any backend exception therefore raised `AttributeError: 'str'
object has no attribute '__enter__'` at `with detail:` instead of showing the error
notice. Renamed to `message`; the guard rail itself is unchanged.

Verification: measured in a real browser via CDP — header-to-label clearance is now
+11.6px (was -4.4px) and a whole-page sibling overlap audit reports none, at both
1600px and 780px widths. Empty, analyzed, and all six focus-drug states render with
no exception under `streamlit.testing`; `python -m pytest -q` — 65 passed.

## 2026-07-19 — Claude (chart polish)

Follow-up on the reliability plot looking clipped. `app/charts.py` and the image
rules in `app/theme.py`; suite still 65 passed.

- The calibration plot drew only the left and bottom spines, so the perfect-
  calibration diagonal ran corner to corner into open space and was shaved by the
  axes edge. It now keeps all four spines and draws that reference line with
  `clip_on=False`, so it reads as bounded rather than cut.
- `set_aspect("equal")` puts the diagonal at a true 45°, which is the only reason a
  calibration plot is worth reading.
- The legend moved from upper left, where it sat on top of the reference line, to
  lower right, where the area under the diagonal is empty.
- The AUROC chart's dashed "random" line sat exactly on the left spine — the x axis
  already starts at 0.5 — so it was invisible chart junk. Removed; the axis label
  now carries "0.5 = random", and every bar visibly grows from random.
- The two charts now share one figure size and are capped by HEIGHT as well as
  width. Streamlit saves each figure with a tight bounding box, so the square
  calibration plot cropped narrower than the bar chart and, pinned to the same
  width, was magnified more and carried visibly larger type. Both now render at
  300px tall with an identical 0.462 scale factor, so their type matches.

Verification: measured in the browser (both images 300px tall, same scale); charts
re-rendered standalone at 200 dpi and checked for clipped labels; `honesty_dumbbell`
and the empty-reliability path still render; `pytest -q` — 65 passed.
