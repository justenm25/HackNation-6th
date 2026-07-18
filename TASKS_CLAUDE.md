# Claude task queue — integration branch

Read `genome-firewall/CLAUDE.md` first. Claim one task at a time and record status in
`CLAUDE_HANDOFF.md`. Do not modify model, grouping, split, calibration, feature-schema,
or report-contract logic.

## C-004 — MIT cluster wrappers

- Status: READY
- Add Slurm job-array wrappers under `genome-firewall/cluster/` for the documented
  AMRFinder task command and one dependent aggregation/training job.
- Parameters (partition, time, memory, array size, environment path) must be variables.
- Do not invent MIT-specific module names or paths; mark them as required configuration.

## C-005 — Cluster runbook

- Status: BLOCKED on C-004.
- Add `genome-firewall/cluster/README.md` explaining data transfer, environment setup,
  submission, resume behavior, logs, dependency chaining, and artifact retrieval.
- Clearly state that AMRFinderPlus, Mash, and logistic regression use CPUs, not GPUs.

## C-006 — Preprocessing CLI smoke tests

- Status: READY
- Add tests for argument parsing, index bounds, resume/skip behavior, and malformed
  cohort rows using tiny fixtures/mocks.
- Tests may not alter production behavior or run AMRFinder/Mash over real genomes.
