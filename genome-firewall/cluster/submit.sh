#!/usr/bin/env bash
# Submit the AMRFinder job array and the dependent aggregation job.
#
#   ./submit.sh              # array, then assembly after every task succeeds
#   ./submit.sh --amrfinder  # array only
#   ./submit.sh --assemble   # assembly only, when the array already finished
#   ./submit.sh --dry-run    # print the sbatch commands without submitting
#
# Resources and paths come from cluster.env; see cluster.env.example.
set -euo pipefail

CLUSTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_environment.sh
source "${CLUSTER_DIR}/_environment.sh"

STAGE=both
DRY_RUN=0
for argument in "$@"; do
    case "${argument}" in
        --amrfinder) STAGE=amrfinder ;;
        --assemble) STAGE=assemble ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "Unknown option: ${argument}" >&2; exit 2 ;;
    esac
done

CONFIG="${GF_CONFIG:-${CLUSTER_DIR}/cluster.env}"
gf_load_config "${CONFIG}"
gf_require GF_PARTITION GF_ENV_PREFIX GF_REPO_ROOT GF_COHORT_CSV GF_FASTA_ROOT GF_WORK_ROOT
gf_require_dir GF_ENV_PREFIX
gf_require_dir GF_REPO_ROOT
gf_require_dir GF_FASTA_ROOT
if [[ ! -f "${GF_COHORT_CSV}" ]]; then
    echo "GF_COHORT_CSV=${GF_COHORT_CSV} does not exist." >&2
    exit 1
fi

LOG_DIR="${GF_WORK_ROOT}/logs"
mkdir -p "${LOG_DIR}"

# Array indices are zero-based to match the CLI's --index, which addresses cohort rows
# directly. An explicit GF_AMR_ARRAY_SIZE submits a pilot slice of the cohort instead.
ROWS="$(gf_cohort_rows "${GF_COHORT_CSV}")"
COUNT="${GF_AMR_ARRAY_SIZE:-${ROWS}}"
if (( COUNT > ROWS )); then
    echo "GF_AMR_ARRAY_SIZE=${COUNT} exceeds the ${ROWS} cohort rows." >&2
    exit 1
fi
ARRAY_RANGE="0-$((COUNT - 1))%${GF_AMR_ARRAY_THROTTLE:-50}"

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
if [[ "${STAGE}" == "both" || "${STAGE}" == "amrfinder" ]]; then
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

if [[ "${STAGE}" == "both" || "${STAGE}" == "assemble" ]]; then
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

echo "logs: ${LOG_DIR}"
