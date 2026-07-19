# Genome Firewall

Genome Firewall is a research backend and Streamlit application that predicts antibiotic
resistance from one quality-checked, assembled *Escherichia coli* genome. For each drug it
returns `likely_to_fail`, `likely_to_work`, or `no_call`, together with calibrated confidence
and an evidence category.

> **Research prototype - not a clinical diagnostic.** Every result must be confirmed with
> standard laboratory antimicrobial-susceptibility testing. A trained professional makes
> treatment decisions.

## What ships in this repository

- A trained E. coli model bundle built from 3,000 BV-BRC genomes.
- Four calibrated models: ciprofloxacin, ceftriaxone, gentamicin, and ampicillin.
- AMRFinderPlus gene and point-mutation featurization with a fixed 460-column schema.
- Mash homology grouping so related genomes cannot cross train, calibration, and test splits.
- A conservative no-call policy: missing resistance evidence is not treated as proof of
  susceptibility.
- A clinical-style Streamlit frontend and a stable `predict()` backend entrypoint.
- Reproducible local and Slurm preprocessing, training, and evaluation commands.

## Quick start

### Prerequisites

- macOS or Linux
- Python 3.11+
- [AMRFinderPlus](https://github.com/ncbi/amr) with its database downloaded
- `mash` only if rebuilding the genetic groups

Install the Python dependencies for the packaged E. coli bundle in your preferred
environment:

```bash
cd genome-firewall
python -m pip install -r requirements-ecoli.txt
```

`requirements-ecoli.txt` pins the scikit-learn version used to serialize the E. coli
models. Do not substitute the root `requirements.txt`: that file exists for the legacy
Streamlit Community Cloud demo, which does not run AMRFinderPlus.

Make sure AMRFinderPlus is ready:

```bash
amrfinder --database_version
```

### Launch

From the repository root:

```bash
./genome-firewall/launch.sh
```

Then open [http://localhost:8501](http://localhost:8501). The launcher automatically uses
the packaged E. coli bundle. Set `GF_AMRFINDER` if `amrfinder` is not on `PATH`:

```bash
GF_AMRFINDER=/absolute/path/to/amrfinder ./genome-firewall/launch.sh
```

Upload one assembled E. coli FASTA (`.fna`, `.fasta`, or `.fa`). Do not upload FASTQ reads,
multiple genomes, or an unassembled/non-E. coli sample.

### Included demo genome

A fresh clone includes a ready-to-upload public BV-BRC E. coli assembly:

```text
genome-firewall/examples/demo_ecoli_562.45650.fna
```

Use this file in the upload control for the presentation. It is BV-BRC genome `562.45650`
(*Escherichia coli* strain EC_43), downloaded through the documented BV-BRC API acquisition
pipeline. Its source and checksum are recorded in
[`genome-firewall/examples/README.md`](genome-firewall/examples/README.md).

### Exactly how to upload a genome

For the included demo, no unzipping or preparation is needed:

1. From the repository root, run `./genome-firewall/launch.sh`.
2. Open `http://localhost:8501` in a browser.
3. In the left **Input** panel, keep the organism as **Escherichia coli**.
4. Under **Source**, choose **Upload FASTA**.
5. Select **Browse files**.
6. Choose `genome-firewall/examples/demo_ecoli_562.45650.fna` from the cloned repository.
7. Select **Analyze genome** and wait for AMRFinderPlus to finish.

The upload must be plain-text FASTA. A valid file begins like this:

```fasta
>contig_1
ATGCGTACGTTAGC...
>contig_2
GCTAACGTAGCTA...
```

Do not upload `.fna.gz` directly: the browser uploader accepts the decompressed `.fna`,
`.fasta`, or `.fa` file. If your own assembly is compressed, keep the original and create a
decompressed copy.

macOS or Linux:

```bash
gzip -dc /path/to/isolate.fna.gz > /path/to/isolate.fna
```

Cross-platform Python, including Windows:

```bash
python -c "import gzip,shutil; i=gzip.open('isolate.fna.gz','rb'); o=open('isolate.fna','wb'); shutil.copyfileobj(i,o); i.close(); o.close()"
```

Verify that decompression worked before uploading:

```bash
ls -lh /path/to/isolate.fna
head -2 /path/to/isolate.fna
```

The file should be several megabytes for a typical E. coli assembly, and the first line
must begin with `>`. If the first line contains `@` and quality characters appear every
fourth line, it is FASTQ raw-read data and is not a supported input.

## Results

Evaluation used an untouched, homology-grouped hidden test. Missing labels were excluded per
drug and never imputed.

| Drug | N | Balanced accuracy | R recall | S recall | AUROC | PR-AUC | Brier | No-call | Accuracy on called |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Ciprofloxacin | 418 | 0.977 | 0.957 | 0.996 | 0.993 | 0.992 | 0.020 | 0.081 | 0.990 |
| Ceftriaxone | 144 | 0.848 | 0.922 | 0.775 | 0.965 | 0.972 | 0.083 | 0.174 | 0.975 |
| Gentamicin | 417 | 0.944 | 0.909 | 0.980 | 0.959 | 0.895 | 0.038 | 0.010 | 0.964 |
| Ampicillin | 340 | 0.892 | 0.946 | 0.839 | 0.965 | 0.992 | 0.053 | 0.226 | 0.992 |

Accuracy-on-called must be interpreted together with the no-call rate. Abstention removes
uncertain cases; it does not make them disappear from operational use.

## Scientific design

```text
assembled E. coli FASTA
        |
        v
AMRFinderPlus genes + mutations
        |
        v
versioned 460-column binary feature vector
        |
        v
four regularized logistic models
        |
        v
held-out Platt calibration + drug-specific thresholds
        |
        v
call + calibrated confidence + evidence + lab-confirmation flag
```

The 3,000 genomes formed 1,548 Mash groups at distance threshold `0.001`. The frozen split is
2,100 train / 452 calibration / 448 hidden test. The leakage audit passes: no genetic group
appears in more than one partition.

Known-marker claims require a reviewed drug-to-marker mapping. The shipped bundle deliberately
does not contain one, so model-supported results are labeled as statistical evidence instead of
overstating causality.

## Backend API

```python
from genome_firewall.api import predict

report = predict(
    "isolate.fna",
    bundle_path="models/ecoli-bundle",
    amrfinder_executable="amrfinder",
)
```

The same API accepts raw AMRFinder TSV output with `input_format="amrfinder_tsv"`. A ready-made
feature row is accepted only when its schema ID and ordered columns exactly match the bundle.

## Important folders and files

### Repository root

| Path | Purpose |
|---|---|
| `README.md` | Main installation, demo, architecture, performance, and safety guide. |
| `requirements.txt` | Lightweight legacy/demo deployment requirements; not the real E. coli runtime. |
| `deploy/huggingface/` | Docker deployment that installs AMRFinderPlus and serves real E. coli predictions on port 7860. |
| `docs/` | Technical provenance PDF and archived execution/frontend/pitch plans. |
| `HANDOFF_CHECKLIST.md` | Operational checklist from cluster artifacts through final demo. |

### `genome-firewall/` application directory

| Path | Purpose |
|---|---|
| `launch.sh` | Recommended local entrypoint. Finds AMRFinderPlus, selects the packaged E. coli bundle, and starts Streamlit. |
| `requirements-ecoli.txt` | Runtime dependencies pinned for the packaged E. coli models. |
| `app/streamlit_app.py` | Streamlit page layout and interaction flow. |
| `app/backend_adapter.py` | Stable seam between the frontend and the real E. coli backend or legacy demo. |
| `app/theme.py` | Clinical UI components, evidence labels, confidence rendering, and safety banner. |
| `app/charts.py` | AUROC and reliability visualizations. |
| `app/report.py` | Downloadable HTML result report. |
| `genome_firewall/api.py` | Single programmatic `predict()` entrypoint. |
| `genome_firewall/featurize/` | AMRFinderPlus runner/parser and versioned feature-matrix construction. |
| `genome_firewall/grouping/` | Mash clustering and split-leakage audit. |
| `genome_firewall/train/` | Dataset loading, group-aware logistic tuning, and bundle creation. |
| `genome_firewall/calibrate/` | Held-out probability calibration and threshold selection. |
| `genome_firewall/predict/` | Calling policy, optional gates, evidence classification, and inference engine. |
| `genome_firewall/evaluate/` | Classification, calibration, abstention, and per-group metrics. |
| `genome_firewall/report/` | Structured backend report construction. |
| `configs/backend/ecoli.yaml` | Species, four-drug panel, label vocabulary, Mash parameters, calibration, and calling policy. |
| `configs/backend/bvbrc_cohort.yaml` | Reproducible BV-BRC cohort and assembly-quality filters. |
| `configs/backend/intrinsic_rules.yaml` | Optional intrinsic-resistance rules; intentionally empty in this release. |
| `scripts/backend/acquire_bvbrc.py` | Downloads laboratory labels, metadata, and FASTAs from the public BV-BRC API. |
| `scripts/backend/prepare_training_data.py` | Resumable AMRFinder, Mash grouping, group-safe split, and canonical dataset assembly. |
| `cluster/` | Slurm array, assembly, training, evaluation wrappers, environment example, and runbook. |
| `tests/backend/` | Tests for parsing, grouping, leakage, labels, calling, training, adapter behavior, and presentation safety. |
| `examples/demo_ecoli_562.45650.fna` | Ready-to-upload public demonstration assembly. |
| `examples/README.md` | Demo-genome source, accession, checksum, and limitations. |

### Packaged model bundle

`genome-firewall/models/ecoli-bundle/` is the complete frozen inference artifact:

| File or folder | Purpose |
|---|---|
| `bundle_manifest.json` | Bundle version, four-drug panel, feature-schema ID, label policy, random seed, and training metadata. |
| `feature_schema.json` | Exact ordered 460-feature contract used at inference. |
| `models/*.joblib` | One regularized logistic-regression model per drug. |
| `calibrators/*.joblib` | One held-out sigmoid/Platt calibrator per drug. |
| `thresholds.json` | Drug-specific resistant and susceptible cutoffs; the middle interval is no-call. |
| `leakage_audit.json` | Proof that none of the 1,548 Mash groups crosses dataset partitions. |
| `metrics/summary.json` | Full hidden-test classification, calibration, abstention, reliability, and group metrics. |

### Legacy collaborator demo

`genome-firewall/src/`, `genome-firewall/models/artifacts/`, and
`genome-firewall/data/processed/` belong to the preserved Klebsiella collaborator demo. They
remain available for presentation fallback, but they are not the E. coli backend described by
the headline results. Real E. coli mode is selected by `launch.sh` through `GF_MODEL_BUNDLE`.

## Test

```bash
cd genome-firewall
python -m pytest -q tests/backend
```

The hand-in version passes 65 tests. A real held-out FASTA also completed the full AMRFinder,
packaged-bundle, report-adapter, and Streamlit health path.

## Rebuild from the fixed cohort

See [`genome-firewall/cluster/README.md`](genome-firewall/cluster/README.md) for the full local
and Slurm workflow. The canonical stages are:

1. Run/resume AMRFinderPlus for each genome.
2. Compute Mash groups and qualifying homology edges.
3. assemble the versioned sparse feature matrix and grouped partitions.
4. Train one logistic model and one held-out calibrator per drug.
5. Evaluate the untouched hidden test and package the frozen bundle.

## Documentation

- [Technical provenance](docs/genome_firewall_technical_provenance.pdf)
- [End-to-end handoff checklist](HANDOFF_CHECKLIST.md)
- [Execution plan](docs/reference/GENOME_FIREWALL_EXECUTION.md)

## Safety and limitations

- E. coli only; no species-identification step is performed.
- Four-drug panel only; other antibiotics are out of coverage.
- Input must already be assembled and quality checked.
- The system predicts existing resistance; it does not design or modify organisms.
- Statistical association is not a molecular mechanism.
- Prospective clinical validity and transportability have not been established.
- Laboratory confirmation is mandatory and is encoded in every report.

Release commit: `3947ea5` plus final hand-in documentation and presentation polish.
