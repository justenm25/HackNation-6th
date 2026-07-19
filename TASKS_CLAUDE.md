# Claude task queue — integration branch

Read `genome-firewall/CLAUDE.md` first. Claim one task at a time and record status in
`CLAUDE_HANDOFF.md`. Do not modify model, grouping, split, calibration, feature-schema,
or report-contract logic.

## C-004 — MIT cluster wrappers

- Status: DONE — `genome-firewall/cluster/{submit.sh,amrfinder_array.sbatch,
  assemble.sbatch,_environment.sh,cluster.env.example}`. Verified with `bash -n` and
  `./submit.sh --dry-run` against a synthetic cohort, including the array-only,
  assembly-only, pilot-size, and throttle paths plus the guardrails for a missing config,
  an unset required value, an oversized array, and an empty cohort.
- Add Slurm job-array wrappers under `genome-firewall/cluster/` for the documented
  AMRFinder task command and one dependent aggregation/training job.
- Parameters (partition, time, memory, array size, environment path) must be variables.
- Do not invent MIT-specific module names or paths; mark them as required configuration.

## C-005 — Cluster runbook

- Status: DONE — `genome-firewall/cluster/README.md`, unblocked by C-004. States plainly
  that the workload is CPU-only.
- Add `genome-firewall/cluster/README.md` explaining data transfer, environment setup,
  submission, resume behavior, logs, dependency chaining, and artifact retrieval.
- Clearly state that AMRFinderPlus, Mash, and logistic regression use CPUs, not GPUs.

## C-006 — Preprocessing CLI smoke tests

- Status: DONE — `genome-firewall/tests/backend/test_prepare_training_data.py`, 19 tests.
  Full suite 33 passed (was 14). No production behavior changed; AMRFinder and Mash are
  mocked and never executed.
- Add tests for argument parsing, index bounds, resume/skip behavior, and malformed
  cohort rows using tiny fixtures/mocks.
- Tests may not alter production behavior or run AMRFinder/Mash over real genomes.

## C-007 — Train/evaluate Slurm stage

- Status: DONE — `cluster/train_evaluate.sbatch`, chained onto assembly with
  `--dependency=afterok` and submitted by `submit.sh`. CPU-only. `--dataset-only` preserves
  the stop-after-assembly mode. New `GF_TRAIN_*`, `GF_BUNDLE_DIR`, and `GF_EVAL_OUTPUT`
  variables are documented in `cluster.env.example`. No training, calibration, threshold,
  grouping, or evaluation Python logic changed.
- Extend the existing cluster workflow with a dependent CPU-only job that invokes the
  existing `genome_firewall.cli.train` and `genome_firewall.cli.evaluate` entrypoints after
  dataset assembly.
- All paths/resources must remain configurable in `cluster.env.example`.
- Do not change training, calibration, threshold, grouping, or evaluation Python logic.
- Preserve a mode that stops after dataset assembly.

## C-008 — Real-backend adapter tests

- Status: DONE — `tests/backend/test_backend_adapter_real_mode.py`, 10 tests over a
  synthetic frozen bundle. Suite 43 passed (was 33). AMRFinder is mocked; no adapter or
  model logic changed.
- Add isolated tests that create or mock a minimal frozen bundle, set `GF_MODEL_BUNDLE`,
  reload `app.backend_adapter`, and verify dynamic E. coli species/drugs plus report
  translation. Mock AMRFinder execution; do not change adapter or model logic.

## C-009 — Final handoff checklist

- Status: DONE — `HANDOFF_CHECKLIST.md` at the repository root, unblocked by C-007.
  Limitations and the mandatory lab-confirmation statement lead the document.
- Add a short checklist covering: cluster outputs, bundle retrieval, environment variables,
  real-mode Streamlit launch, test commands, demo smoke test, PR review, and merge.
- Keep scientific limitations and the mandatory lab-confirmation statement prominent.
