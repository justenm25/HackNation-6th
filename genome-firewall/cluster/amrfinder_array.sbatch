#!/usr/bin/env bash
#SBATCH --job-name=gf-amrfinder
#SBATCH --nodes=1
#SBATCH --ntasks=1
# Partition, account, time, memory, CPUs, array range, and log paths are supplied by
# submit.sh from cluster.env. They are deliberately not hard-coded here: sbatch command
# line options override #SBATCH directives, and a stale directive in this file would be
# a silent, confusing default on a cluster it was not written for.
set -euo pipefail

CLUSTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_environment.sh
source "${CLUSTER_DIR}/_environment.sh"
gf_load_config "${GF_CONFIG:-${CLUSTER_DIR}/cluster.env}"
gf_activate_environment

INDEX="${SLURM_ARRAY_TASK_ID:?This script must be submitted as a job array}"
AMR_DIR="${GF_WORK_ROOT}/amrfinder"
mkdir -p "${AMR_DIR}"

# One genome per array task. The command is resumable: a task whose output TSV already
# exists reports "skipped" and exits successfully, so resubmitting the same array after a
# timeout or preemption only reruns the genomes that are actually missing.
python "${GF_REPO_ROOT}/genome-firewall/scripts/backend/prepare_training_data.py" amrfinder \
    --cohort "${GF_COHORT_CSV}" \
    --fasta-root "${GF_FASTA_ROOT}" \
    --output "${AMR_DIR}" \
    --index "${INDEX}" \
    --threads-per-task "${SLURM_CPUS_PER_TASK:-${GF_AMR_CPUS:-1}}" \
    --organism "${GF_ORGANISM}" \
    ${GF_AMRFINDER_DB:+--database-dir "${GF_AMRFINDER_DB}"}
