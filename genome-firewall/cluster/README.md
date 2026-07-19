# Running Genome Firewall preprocessing on a Slurm cluster

The cluster pipeline runs in three dependent stages:

1. **AMRFinder array** — one genome per array task.
2. **Assembly** — Mash groups the cohort, chooses a group-safe split, and builds the sparse
   feature matrix.
3. **Train and evaluate** — one calibrated logistic-regression model per drug, then metrics
   on the hidden-test split.

Each stage is submitted with a dependency on the one before it, so a single `./submit.sh`
queues the whole pipeline and you can log off. Stop after stage 2 with `--dataset-only`.

**This workload is CPU-only.** AMRFinderPlus (BLAST and HMMER), Mash sketching, and the
logistic-regression models all run on CPUs. Do not request a GPU partition — you will wait
in a longer queue for hardware nothing here can use.

Every cluster-specific value — partition, account, walltime, memory, module names, paths —
is configuration, not something these scripts assume. Fill them in once in `cluster.env`.

## 1. Transfer data to the cluster

Put the cohort and its FASTAs on scratch or project storage with room for one AMRFinder
TSV per genome, plus the Mash sketch. Home directory quotas are usually too small.

```bash
rsync -avP data/cohort.csv you@cluster:/path/to/work/
rsync -avP data/fasta/     you@cluster:/path/to/fasta/
```

The cohort CSV needs `genome_id`, `fasta_path`, and one column per drug
(`ciprofloxacin`, `ceftriaxone`, `gentamicin`, `ampicillin`). `fasta_path` is relative to
`GF_FASTA_ROOT`, and `.gz` files are decompressed per task into node-local scratch.

Clone the repository on the cluster too — the jobs run the CLI from a checkout:

```bash
git clone <repository-url> /path/to/genome-firewall-repo
```

## 2. Set up the environment

Create one conda environment holding AMRFinderPlus, Mash, and the Python dependencies:

```bash
conda create --yes --prefix /path/to/env -c conda-forge -c bioconda ncbi-amrfinderplus mash
conda activate /path/to/env
pip install -r /path/to/genome-firewall-repo/genome-firewall/requirements.txt
amrfinder -u          # download the AMRFinder database once, on a login node
```

Download the database on the login node, not inside a job: array tasks starting together
would otherwise each try to write the same database directory.

Then create your configuration:

```bash
cd /path/to/genome-firewall-repo/genome-firewall/cluster
cp cluster.env.example cluster.env
```

Fill in at minimum `GF_PARTITION`, `GF_ENV_PREFIX`, `GF_REPO_ROOT`, `GF_COHORT_CSV`,
`GF_FASTA_ROOT`, and `GF_WORK_ROOT`; `submit.sh` refuses to run until they are set. If your
site exposes conda through a module rather than a shell hook, set `GF_CONDA_MODULE` to the
module name from `module avail` — the scripts deliberately do not guess module names.

## 3. Submit

```bash
./submit.sh --dry-run    # print the sbatch commands without submitting
./submit.sh              # the full chain: array, assembly, train and evaluate
```

`submit.sh` derives the array size from the cohort, so the array always matches the data.
It prints every job id and the log directory. Useful variants:

```bash
./submit.sh --dataset-only           # stop after dataset assembly, no training
./submit.sh --amrfinder              # array only
./submit.sh --assemble               # assembly only, when the array already finished
./submit.sh --train                  # train and evaluate from an existing dataset
./submit.sh --assemble --train       # stage flags combine and stay chained
GF_AMR_ARRAY_SIZE=25 ./submit.sh     # pilot on the first 25 genomes
GF_AMR_ARRAY_THROTTLE=10 ./submit.sh # cap concurrently running tasks
```

Only the stages you submit have their inputs checked, so `--train` works on a cluster where
the FASTAs have already been cleaned up. The training stage additionally requires
`GF_TRAIN_CONFIG`, and writes to `GF_BUNDLE_DIR` (default `${GF_WORK_ROOT}/bundle`).

Environment variables override `cluster.env`, so a pilot run needs no edit to the committed
configuration. Do a pilot first: it surfaces a wrong organism, path, or database in minutes
instead of after a full cohort has queued.

`GF_AMR_ARRAY_THROTTLE` is the `%N` limit on concurrent tasks. AMRFinder reads its database
for every task, so a large array can saturate a shared filesystem. Start near the default of
50 and raise it only if your storage tolerates it.

## 4. Dependency chaining

Each stage is submitted with `--dependency=afterok` on the previous one: assembly waits on
the array, training waits on assembly. A stage starts only if **every** task it depends on
exits zero. If an array task fails, the assembly job stays queued with reason
`DependencyNeverSatisfied` and never runs on an incomplete cohort — and training never runs
on a dataset that was never built. That is the intended behavior: fix the failures,
resubmit, and the chain proceeds.

```bash
scancel <assemble-job-id>   # clear a job stuck on a never-satisfied dependency
```

## 5. Resume behavior

Both stages are resumable, so the fix for a timeout or preemption is to resubmit.

- **AMRFinder tasks** skip any genome whose output TSV already exists and is non-trivial,
  reporting `skipped`. Resubmitting the same array reruns only the missing genomes.
- Results are written to a `.tsv.part` file and renamed only on success, so a killed task
  never leaves a truncated TSV that a later run would mistake for finished work.
- **Mash sketching** reuses an existing sketch, so rerunning the assembly job after an
  assembly-stage failure does not resketch the cohort.
- **Assembly** fails loudly and lists what is missing if any AMRFinder result is absent,
  rather than quietly building a partial dataset.
- **Training** is deliberately not resumable: it refuses to write into a non-empty bundle
  directory so a frozen bundle is never silently replaced. To retrain, point
  `GF_BUNDLE_DIR` at a new path or remove the old directory. Training is minutes of CPU, so
  there is nothing to salvage by resuming.

To force a genome to be recomputed, delete its TSV from `${GF_WORK_ROOT}/amrfinder/` and
resubmit.

## 6. Logs

Logs land in `${GF_WORK_ROOT}/logs/`, one pair of files per array task:

```
logs/amrfinder-<array-job-id>_<task-id>.out    # "<index> <genome_id> completed|skipped"
logs/amrfinder-<array-job-id>_<task-id>.err
logs/assemble-<job-id>.out                     # group and dataset summary lines
logs/assemble-<job-id>.err
logs/train-<job-id>.out                        # bundle and metrics paths
logs/train-<job-id>.err
```

Monitoring and triage:

```bash
squeue -u "$USER"
sacct -j <array-job-id> --format=JobID,State,ExitCode,Elapsed,MaxRSS
sacct -j <array-job-id> --state=FAILED --format=JobID,State,ExitCode   # failed tasks only
grep -l . "${GF_WORK_ROOT}"/logs/amrfinder-*.err                       # tasks that wrote errors
```

A task id maps directly to a cohort row: array index *N* is the *N*-th data row of the
cohort CSV, zero-based. `OUT_OF_MEMORY` or `TIMEOUT` in `sacct` means raise `GF_AMR_MEM` or
`GF_AMR_TIME` and resubmit; completed genomes will be skipped.

## 7. Retrieve artifacts

The assembly job writes the canonical dataset to `${GF_WORK_ROOT}/dataset/`:

| File | Contents |
| --- | --- |
| `X_features.npz` | sparse binary sample-by-feature matrix |
| `feature_schema.json` | frozen column order and `schema_id`, fitted on the train split only |
| `samples.csv` | sample id, split, genetic group, and phenotypes |
| `unknown_features.json` | per-sample features absent from the schema |

The training stage writes the frozen bundle to `GF_BUNDLE_DIR` (default
`${GF_WORK_ROOT}/bundle`) and hidden-test metrics to `GF_EVAL_OUTPUT` (default
`${GF_WORK_ROOT}/eval/hidden_test.json`):

| File | Contents |
| --- | --- |
| `bundle_manifest.json` | drug panel, feature schema id, and training details |
| `feature_schema.json` | the schema predictions are validated against |
| `models/<drug>.joblib`, `calibrators/<drug>.joblib` | per-drug model and calibrator |
| `thresholds.json` | per-drug resistant and susceptible decision thresholds |
| `leakage_audit.json` | evidence that no genetic group spans two splits |

Alongside it, `genetic_groups.csv` records the Mash grouping and
`mash/qualifying_edges.csv` the pairs that fell within the distance threshold — keep both,
they are the evidence that the held-out split is leakage-safe.

```bash
rsync -avP you@cluster:"${GF_WORK_ROOT}/dataset/" data/processed/ecoli/
rsync -avP you@cluster:"${GF_WORK_ROOT}/genetic_groups.csv" data/processed/
rsync -avP you@cluster:"${GF_WORK_ROOT}/bundle/" models/bundle/
rsync -avP you@cluster:"${GF_WORK_ROOT}/eval/hidden_test.json" models/
```

The bundle is what the Streamlit app loads through `GF_MODEL_BUNDLE`. See the repository
`HANDOFF_CHECKLIST.md` for the exact cluster-to-local handoff and demo steps.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `Set these in cluster.env before submitting: ...` | A required value is still empty. |
| `conda not found` | Set `GF_CONDA_MODULE` to your site's conda module. |
| `amrfinder missing from <prefix>` | The environment prefix is wrong or incomplete. |
| Every task fails immediately | Usually a wrong `GF_FASTA_ROOT` or an unreadable database; check one `.err` file. |
| Assembly stuck, reason `DependencyNeverSatisfied` | An array task failed. Fix, `scancel` the assembly, resubmit. |
| `Index N outside 0..M` | Cohort changed after submission; resubmit so the array is resized. |
| Unknown organism from AMRFinder | `GF_ORGANISM` must be one of `amrfinder --list_organisms`. |
| `Bundle ... already exists and is not empty` | Set `GF_BUNDLE_DIR` to a new path or remove the old bundle. |
| `Unknown phenotype label: 'Resistant'` | The config's `labels.resistant_values` do not match the cohort's phenotype strings. |
| Training produces no models | The config's `drug_panel` is empty; populate it with the drugs to train. |
