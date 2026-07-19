#!/usr/bin/env bash
# Submit the Genome Firewall cluster pipeline: an AMRFinder job array, dataset assembly,
# then training and evaluation. Each stage waits on the previous one.
#
#   ./submit.sh                  # the full chain: array, assembly, train and evaluate
#   ./submit.sh --dataset-only   # stop after dataset assembly
#   ./submit.sh --amrfinder      # array only
#   ./submit.sh --assemble       # assembly only, when the array already finished
#   ./submit.sh --train          # training and evaluation only, from an existing dataset
#   ./submit.sh --dry-run        # print the sbatch commands without submitting
#
# Stage flags combine, so --assemble --train submits those two chained together.
# Resources and paths come from cluster.env; see cluster.env.example.
set -euo pipefail

CLUSTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_environment.sh
source "${CLUSTER_DIR}/_environment.sh"

RUN_AMRFINDER=0
RUN_ASSEMBLE=0
RUN_TRAIN=0
EXPLICIT_STAGE=0
DRY_RUN=0
for argument in "$@"; do
    case "${argument}" in
        --amrfinder) RUN_AMRFINDER=1; EXPLICIT_STAGE=1 ;;
        --assemble) RUN_ASSEMBLE=1; EXPLICIT_STAGE=1 ;;
        --train) RUN_TRAIN=1; EXPLICIT_STAGE=1 ;;
        # Preserved mode: everything up to and including dataset assembly, no training.
        --dataset-only) RUN_AMRFINDER=1; RUN_ASSEMBLE=1; EXPLICIT_STAGE=1 ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help) sed -n '2,13p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "Unknown option: ${argument}" >&2; exit 2 ;;
    esac
done
if (( ! EXPLICIT_STAGE )); then
    RUN_AMRFINDER=1; RUN_ASSEMBLE=1; RUN_TRAIN=1
fi

CONFIG="${GF_CONFIG:-${CLUSTER_DIR}/cluster.env}"
gf_load_config "${CONFIG}"
gf_require GF_PARTITION GF_ENV_PREFIX GF_REPO_ROOT GF_WORK_ROOT
gf_require_dir GF_ENV_PREFIX
gf_require_dir GF_REPO_ROOT

# Only the stages being submitted have their inputs checked, so training from an existing
# dataset does not demand a cohort that is no longer on this filesystem.
if (( RUN_AMRFINDER || RUN_ASSEMBLE )); then
    gf_require GF_COHORT_CSV GF_FASTA_ROOT
    gf_require_dir GF_FASTA_ROOT
    if [[ ! -f "${GF_COHORT_CSV}" ]]; then
        echo "GF_COHORT_CSV=${GF_COHORT_CSV} does not exist." >&2
        exit 1
    fi
fi
if (( RUN_TRAIN )); then
    gf_require GF_TRAIN_CONFIG
    if [[ ! -f "${GF_TRAIN_CONFIG}" ]]; then
        echo "GF_TRAIN_CONFIG=${GF_TRAIN_CONFIG} does not exist." >&2
        exit 1
    fi
fi

LOG_DIR="${GF_WORK_ROOT}/logs"
mkdir -p "${LOG_DIR}"

ARRAY_RANGE=""
if (( RUN_AMRFINDER )); then
    # Array indices are zero-based to match the CLI's --index, which addresses cohort rows
    # directly. An explicit GF_AMR_ARRAY_SIZE submits a pilot slice of the cohort instead.
    ROWS="$(gf_cohort_rows "${GF_COHORT_CSV}")"
    COUNT="${GF_AMR_ARRAY_SIZE:-${ROWS}}"
    if (( COUNT > ROWS )); then
        echo "GF_AMR_ARRAY_SIZE=${COUNT} exceeds the ${ROWS} cohort rows." >&2
        exit 1
    fi
    ARRAY_RANGE="0-$((COUNT - 1))%${GF_AMR_ARRAY_THROTTLE:-50}"
fi

common_options=(--parsable --partition "${GF_PARTITION}" --export "ALL,GF_CONFIG=${CONFIG}")
if [[ -n "${GF_ACCOUNT:-}" ]]; then common_options+=(--account "${GF_ACCOUNT}"); fi
if [[ -n "${GF_QOS:-}" ]]; then common_options+=(--qos "${GF_QOS}"); fi

# Emits the job id on stdout so the caller can chain a dependency on it. Under --dry-run
# the command goes to stderr and a placeholder id is returned, keeping stdout a job id in
# both modes.
run_sbatch() {
    if (( DRY_RUN )); then
        { printf 'sbatch'; printf ' %q' "$@"; printf '\n'; } >&2
        echo "DRY_RUN_JOB_ID"
        return 0
    fi
    sbatch "$@"
}

array_job_id=""
if (( RUN_AMRFINDER )); then
    array_job_id="$(run_sbatch "${common_options[@]}" \
        --job-name gf-amrfinder \
        --array "${ARRAY_RANGE}" \
        --time "${GF_AMR_TIME}" \
        --mem "${GF_AMR_MEM}" \
        --cpus-per-task "${GF_AMR_CPUS}" \
        --output "${LOG_DIR}/amrfinder-%A_%a.out" \
        --error "${LOG_DIR}/amrfinder-%A_%a.err" \
        "${CLUSTER_DIR}/amrfinder_array.sbatch")"
    echo "amrfinder array: ${array_job_id} (${ARRAY_RANGE} of ${ROWS} genomes)"
fi

assemble_job_id=""
if (( RUN_ASSEMBLE )); then
    dependency=()
    # afterok holds the assembly until every array task exits zero, so a partial cohort
    # never reaches dataset assembly.
    if [[ -n "${array_job_id}" ]]; then
        dependency=(--dependency "afterok:${array_job_id}")
    fi
    assemble_job_id="$(run_sbatch "${common_options[@]}" \
        --job-name gf-assemble \
        ${dependency[@]+"${dependency[@]}"} \
        --time "${GF_ASSEMBLE_TIME}" \
        --mem "${GF_ASSEMBLE_MEM}" \
        --cpus-per-task "${GF_ASSEMBLE_CPUS}" \
        --output "${LOG_DIR}/assemble-%j.out" \
        --error "${LOG_DIR}/assemble-%j.err" \
        "${CLUSTER_DIR}/assemble.sbatch")"
    echo "assemble job: ${assemble_job_id}${array_job_id:+ (waits on ${array_job_id})}"
fi

if (( RUN_TRAIN )); then
    dependency=()
    # Chains onto assembly when both were submitted; otherwise trains from the dataset
    # already on disk.
    if [[ -n "${assemble_job_id}" ]]; then
        dependency=(--dependency "afterok:${assemble_job_id}")
    fi
    train_job_id="$(run_sbatch "${common_options[@]}" \
        --job-name gf-train \
        ${dependency[@]+"${dependency[@]}"} \
        --time "${GF_TRAIN_TIME}" \
        --mem "${GF_TRAIN_MEM}" \
        --cpus-per-task "${GF_TRAIN_CPUS}" \
        --output "${LOG_DIR}/train-%j.out" \
        --error "${LOG_DIR}/train-%j.err" \
        "${CLUSTER_DIR}/train_evaluate.sbatch")"
    echo "train job: ${train_job_id}${assemble_job_id:+ (waits on ${assemble_job_id})}"
    echo "bundle: ${GF_BUNDLE_DIR:-${GF_WORK_ROOT}/bundle}"
fi

echo "logs: ${LOG_DIR}"
