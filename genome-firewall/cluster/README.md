# Running Genome Firewall preprocessing on a Slurm cluster

Preprocessing turns a BV-BRC cohort into the canonical training dataset in two stages: an
AMRFinderPlus job array with one genome per task, then a single aggregation job that Mash
groups the cohort, chooses a group-safe split, and assembles the sparse feature matrix.
The second stage is submitted with a dependency on the first, so one `./submit.sh` queues
the whole pipeline and you can log off.

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
./submit.sh              # array, then assembly once every task succeeds
```

`submit.sh` derives the array size from the cohort, so the array always matches the data.
It prints both job ids and the log directory. Useful variants:

```bash
./submit.sh --amrfinder              # array only
./submit.sh --assemble               # assembly only, when the array already finished
GF_AMR_ARRAY_SIZE=25 ./submit.sh     # pilot on the first 25 genomes
GF_AMR_ARRAY_THROTTLE=10 ./submit.sh # cap concurrently running tasks
```

Environment variables override `cluster.env`, so a pilot run needs no edit to the committed
configuration. Do a pilot first: it surfaces a wrong organism, path, or database in minutes
instead of after a full cohort has queued.

`GF_AMR_ARRAY_THROTTLE` is the `%N` limit on concurrent tasks. AMRFinder reads its database
for every task, so a large array can saturate a shared filesystem. Start near the default of
50 and raise it only if your storage tolerates it.

## 4. Dependency chaining

The assembly job is submitted with `--dependency=afterok:<array-job-id>`. It starts only if
**every** array task exits zero. If any task fails, the assembly job stays in the queue with
reason `DependencyNeverSatisfied` and never runs on an incomplete cohort. That is the
intended behavior: fix the failures, resubmit, and the assembly proceeds.

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

To force a genome to be recomputed, delete its TSV from `${GF_WORK_ROOT}/amrfinder/` and
resubmit.

## 6. Logs

Logs land in `${GF_WORK_ROOT}/logs/`, one pair of files per array task:

```
logs/amrfinder-<array-job-id>_<task-id>.out    # "<index> <genome_id> completed|skipped"
logs/amrfinder-<array-job-id>_<task-id>.err
logs/assemble-<job-id>.out                     # group and dataset summary lines
logs/assemble-<job-id>.err
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

Alongside it, `genetic_groups.csv` records the Mash grouping and
`mash/qualifying_edges.csv` the pairs that fell within the distance threshold — keep both,
they are the evidence that the held-out split is leakage-safe.

```bash
rsync -avP you@cluster:"${GF_WORK_ROOT}/dataset/" data/processed/ecoli/
rsync -avP you@cluster:"${GF_WORK_ROOT}/genetic_groups.csv" data/processed/
```

Model training runs from this dataset and is fast enough to do locally; nothing after
assembly needs the cluster.

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
