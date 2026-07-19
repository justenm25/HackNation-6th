#!/usr/bin/env bash
#SBATCH --job-name=gf-train
#SBATCH --nodes=1
#SBATCH --ntasks=1
# Resources and log paths come from submit.sh; see the note in amrfinder_array.sbatch.
# Submitted with --dependency=afterok on the assembly job, so it starts only once the
# canonical dataset exists.
#
# CPU-only. Logistic regression over a sparse binary matrix does not use a GPU; do not
# add a --gres=gpu request here.
set -euo pipefail

CLUSTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_environment.sh
source "${CLUSTER_DIR}/_environment.sh"
gf_load_config "${GF_CONFIG:-${CLUSTER_DIR}/cluster.env}"
gf_activate_environment

DATASET_DIR="${GF_WORK_ROOT}/dataset"
BUNDLE_DIR="${GF_BUNDLE_DIR:-${GF_WORK_ROOT}/bundle}"
EVAL_OUTPUT="${GF_EVAL_OUTPUT:-${GF_WORK_ROOT}/eval/hidden_test.json}"

if [[ ! -f "${DATASET_DIR}/feature_schema.json" ]]; then
    echo "No dataset at ${DATASET_DIR}. Run the assembly stage first." >&2
    exit 1
fi

# Training refuses to write into a non-empty bundle directory so that a frozen bundle is
# never silently replaced. Say so here rather than surfacing it as a traceback in a log.
if [[ -d "${BUNDLE_DIR}" ]] && [[ -n "$(ls -A "${BUNDLE_DIR}" 2>/dev/null)" ]]; then
    echo "Bundle ${BUNDLE_DIR} already exists and is not empty." >&2
    echo "Set GF_BUNDLE_DIR to a new path, or remove that directory to retrain." >&2
    exit 1
fi

cd "${GF_REPO_ROOT}/genome-firewall"

python -m genome_firewall.cli.train \
    --config "${GF_TRAIN_CONFIG}" \
    --dataset "${DATASET_DIR}" \
    --output "${BUNDLE_DIR}"

mkdir -p "$(dirname "${EVAL_OUTPUT}")"

python -m genome_firewall.cli.evaluate \
    --bundle "${BUNDLE_DIR}" \
    --dataset "${DATASET_DIR}" \
    --output "${EVAL_OUTPUT}"

echo "bundle written to ${BUNDLE_DIR}"
echo "hidden-test metrics written to ${EVAL_OUTPUT}"
