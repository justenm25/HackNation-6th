# Final handoff checklist

Cluster run → local demo → PR → merge. Work top to bottom; each section is a gate for the
next. Cluster mechanics live in `genome-firewall/cluster/README.md`; this file is the
end-to-end path.

## Read this before demoing

Genome Firewall is a **research prototype and decision support only**. Every result must be
confirmed by standard laboratory testing, and a trained professional makes the treatment
decision. Say this out loud during the demo — do not let the audience infer that a call is
a clinical result. The non-dismissable in-app banner must stay visible; if it is missing,
the demo is not ready.

State the limits plainly, ideally while showing a no-call:

- **One species per bundle.** The E. coli bundle covers E. coli and the drugs in its panel.
  Anything else is out of coverage and must not be run through it.
- **A no-call is the honest answer**, not a failure. The system abstains when the calibrated
  probability lands between thresholds, when a feature is unknown to the model, and — by
  default — rather than calling a drug effective purely because no resistance marker was
  found. Absence of a marker is not evidence of susceptibility.
- **Acquired genes are the strength; mutation-mediated resistance is the weakness.** Where
  annotations don't capture the mechanism, expect and welcome no-calls.
- **A statistical association is not a cause.** The report separates curated resistance
  markers from features the model merely leaned on. Never present the latter as mechanism.
- **Confidence is calibrated, not exact.** Show the interval, not a fake-precise percentage.

## 1. Cluster outputs

Confirm on the cluster before transferring anything:

- [ ] Every array task finished: `sacct -j <array-job-id> --state=FAILED` returns no rows.
- [ ] Assembly wrote `${GF_WORK_ROOT}/dataset/` with `X_features.npz`,
      `feature_schema.json`, `samples.csv`, and `unknown_features.json`.
- [ ] `${GF_WORK_ROOT}/genetic_groups.csv` and `mash/qualifying_edges.csv` exist — these
      are the evidence the held-out split is leakage-safe.
- [ ] Training wrote `${GF_WORK_ROOT}/bundle/` with `bundle_manifest.json`,
      `feature_schema.json`, `thresholds.json`, `leakage_audit.json`, and a `models/` and
      `calibrators/` entry per drug.
- [ ] `leakage_audit.json` reports no genetic group spanning two splits.
- [ ] `${GF_WORK_ROOT}/eval/hidden_test.json` has hidden-test metrics for every drug.
- [ ] `logs/train-<job-id>.err` is empty or benign.

Sanity-check the numbers before they reach a slide. A drug whose metrics look impossible is
more likely a label or split problem than a breakthrough.

## 2. Retrieve the bundle

Exact transfer, from the repository root, with `WORK` set to the cluster `GF_WORK_ROOT`:

```bash
CLUSTER=you@cluster
WORK=/path/to/work            # the cluster's GF_WORK_ROOT

# The bundle is the only artifact the app needs.
rsync -avP "$CLUSTER:$WORK/bundle/"                genome-firewall/models/ecoli-bundle/

# Provenance and evaluation evidence, for the PR and the demo's metrics view.
rsync -avP "$CLUSTER:$WORK/eval/hidden_test.json"  genome-firewall/models/
rsync -avP "$CLUSTER:$WORK/genetic_groups.csv"     genome-firewall/data/processed/

# Optional, and large: the dataset, only if retraining locally.
rsync -avP "$CLUSTER:$WORK/dataset/"               genome-firewall/data/processed/ecoli/
```

- [ ] `genome-firewall/models/ecoli-bundle/bundle_manifest.json` exists locally.
- [ ] `feature_schema_id` in `bundle_manifest.json` matches the one in the bundle's
      `feature_schema.json` — the app refuses to load a bundle where they disagree.
- [ ] The bundle is **not** committed if it exceeds the repository's size budget; ship it as
      a release artifact and note where it lives.

To surface metrics in the UI, place them where the adapter looks:

```bash
mkdir -p genome-firewall/models/ecoli-bundle/metrics
cp genome-firewall/models/hidden_test.json \
   genome-firewall/models/ecoli-bundle/metrics/summary.json
```

- [ ] Without `metrics/summary.json` the metrics view is simply empty — acceptable for the
      demo, but decide deliberately rather than discovering it on stage.

## 3. Environment variables

```bash
cd genome-firewall
export GF_MODEL_BUNDLE="$PWD/models/ecoli-bundle"   # absolute path; switches to real mode
export GF_AMRFINDER=/absolute/path/to/amrfinder     # defaults to `amrfinder` on PATH
export GF_AMRFINDER_DB=/absolute/path/to/db         # optional; omit for the default
```

- [ ] `GF_MODEL_BUNDLE` is absolute and points at a **directory**. If it is missing or not a
      directory the app silently runs the collaborator Klebsiella demo instead — the most
      likely way to demo the wrong backend without noticing.
- [ ] `amrfinder --database_version` works in the same shell you will launch from.
- [ ] Leave `GF_SUSCEPTIBLE_POLICY` unset. Only set `validated_low_risk` if that policy was
      validated and frozen with this bundle; it permits "likely to work" from marker absence.

## 4. Launch in real mode

```bash
cd genome-firewall
pip install -r requirements.txt
streamlit run app/streamlit_app.py        # http://localhost:8501
```

- [ ] The UI reports E. coli coverage and the drug names from your bundle's panel — not the
      Klebsiella demo drugs. This is the one check that proves the real backend is live.
- [ ] The lab-confirmation banner is visible and cannot be dismissed.

## 5. Tests

```bash
cd genome-firewall
python -m pytest -q
```

- [ ] Full suite passes.
- [ ] `tests/backend/test_backend_adapter_real_mode.py` passes — adapter mode switching and
      report translation against a synthetic bundle.
- [ ] `tests/backend/test_prepare_training_data.py` passes — preprocessing CLI.
- [ ] Cluster scripts parse: `bash -n genome-firewall/cluster/*.sbatch
      genome-firewall/cluster/submit.sh`.
- [ ] `./submit.sh --dry-run` prints the expected chain against your `cluster.env`.

Tests run without a cluster, without AMRFinder, and without a real bundle; all three are
mocked. A failure here is a real failure, not a missing dependency.

## 6. Demo smoke test

Do this end to end at least once **before** presenting, on the machine you will present
from, with the projector resolution you will use.

- [ ] Upload a quality-checked E. coli FASTA and get a report back.
- [ ] At least one drug shows a call with a calibrated confidence and cited evidence.
- [ ] At least one **no-call** is visible, with its reason — this is the honest-uncertainty
      story, so pick a genome that produces one.
- [ ] Evidence distinguishes a curated resistance marker from a statistical association.
- [ ] Time the run: know the number before someone asks.
- [ ] Have a fallback. If AMRFinder is slow or the network is hostile, keep a screenshot or
      a pre-computed report ready, and say plainly that it is pre-computed.
- [ ] Confirm the out-of-coverage path: a non-E. coli genome must not be presented as a
      supported result.

## 7. PR review

- [ ] Branch is rebased on the integration branch and the full suite passes there.
- [ ] Diff touches no correctness-critical logic unintentionally: feature schema, grouping,
      splits, label policy, calibration, thresholds, or the report contract.
- [ ] Cluster scripts contain no site-specific paths, partitions, or module names — every
      such value belongs in `cluster.env`, which is **not** committed.
- [ ] No credentials, cluster hostnames, or absolute personal paths in the diff.
- [ ] No large artifacts committed: bundles, datasets, sketches, raw FASTAs.
- [ ] `cluster.env.example` documents every variable the scripts read.
- [ ] Docs match behavior: `cluster/README.md`, this checklist, and the root `README.md`.
- [ ] Safety language intact: no-call semantics, coverage statement, and the mandatory
      lab-confirmation banner.

## 8. Merge

- [ ] Squash-merge into the integration branch with a message naming the completed tasks.
- [ ] `TASKS_CLAUDE.md` and `CLAUDE_HANDOFF.md` reflect the final state.
- [ ] Record where the bundle lives and which cohort and config produced it — a bundle whose
      provenance is unknown cannot be reproduced or defended.
- [ ] Note any known-weak drug in the release notes so nobody over-reads a metric.
- [ ] Delete the merged feature branch.
