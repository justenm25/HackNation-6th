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

Install the Python dependencies in your preferred environment:

```bash
cd genome-firewall
python -m pip install -r requirements.txt
```

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

## Repository layout

```text
genome-firewall/
  app/                  Streamlit UI and backend adapter
  genome_firewall/      E. coli featurize/train/calibrate/predict/report package
  configs/backend/      species, drug-panel, grouping, and calling configuration
  models/ecoli-bundle/  frozen schema, models, calibrators, thresholds, and metrics
  scripts/backend/      BV-BRC acquisition and canonical dataset preparation
  cluster/              resumable Slurm wrappers and runbook
  tests/backend/        leakage, schema, training, adapter, and presentation tests
docs/                   technical provenance and planning/reference material
```

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
