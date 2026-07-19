#!/usr/bin/env bash
#SBATCH --job-name=gf-assemble
#SBATCH --nodes=1
#SBATCH --ntasks=1
# Resources and log paths come from submit.sh; see the note in amrfinder_array.sbatch.
# This job is submitted with --dependency=afterok on the AMRFinder array, so it starts
# only once every array task has succeeded.
set -euo pipefail

CLUSTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_environment.sh
source "${CLUSTER_DIR}/_environment.sh"
gf_load_config "${GF_CONFIG:-${CLUSTER_DIR}/cluster.env}"
gf_activate_environment

PREPARE="${GF_REPO_ROOT}/genome-firewall/scripts/backend/prepare_training_data.py"
AMR_DIR="${GF_WORK_ROOT}/amrfinder"
MASH_DIR="${GF_WORK_ROOT}/mash"
GROUPS_CSV="${GF_WORK_ROOT}/genetic_groups.csv"
DATASET_DIR="${GF_WORK_ROOT}/dataset"
mkdir -p "${MASH_DIR}" "${DATASET_DIR}"

# Mash sketching and threshold-connected grouping. The sketch is reused when present, so
# a rerun of this job after a failure in assembly does not resketch the cohort.
python "${PREPARE}" group \
    --cohort "${GF_COHORT_CSV}" \
    --fasta-root "${GF_FASTA_ROOT}" \
    --work-dir "${MASH_DIR}" \
    --output "${GROUPS_CSV}" \
    --distance-threshold "${GF_MASH_DISTANCE}" \
    --kmer-size "${GF_MASH_KMER}" \
    --sketch-size "${GF_MASH_SKETCH}"

# Group-safe split and canonical sparse dataset. Fails loudly if any AMRFinder result is
# missing rather than quietly training on a partial cohort.
python "${PREPARE}" assemble \
    --cohort "${GF_COHORT_CSV}" \
    --groups "${GROUPS_CSV}" \
    --amr-dir "${AMR_DIR}" \
    --output "${DATASET_DIR}" \
    --split-trials "${GF_SPLIT_TRIALS}" \
    --seed "${GF_SEED}" \
    --schema-version "${GF_SCHEMA_VERSION}"

echo "dataset written to ${DATASET_DIR}"
