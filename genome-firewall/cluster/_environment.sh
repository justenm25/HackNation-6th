#!/usr/bin/env bash
# Shared configuration loading for the Genome Firewall cluster jobs.
# Sourced by submit.sh on the login node and by both batch scripts on the compute nodes.

# Loads cluster.env, but lets variables already exported in the environment win. That makes
# one-off overrides work the way they read -- `GF_AMR_ARRAY_SIZE=25 ./submit.sh` submits a
# pilot slice -- without editing the committed configuration.
gf_load_config() {
    local config="${1:?config path required}"
    if [[ ! -f "${config}" ]]; then
        echo "Missing ${config}. Copy cluster.env.example to cluster.env and fill it in." >&2
        return 1
    fi
    local preset
    preset="$(env | grep '^GF_[A-Z0-9_]*=' || true)"
    # shellcheck disable=SC1090
    set -a; source "${config}"; set +a
    local entry
    while IFS= read -r entry; do
        [[ -n "${entry}" ]] || continue
        export "${entry?}"
    done <<< "${preset}"
}

gf_require() {
    local missing=()
    local name
    for name in "$@"; do
        [[ -n "${!name:-}" ]] || missing+=("${name}")
    done
    if (( ${#missing[@]} )); then
        printf 'Set these in cluster.env before submitting: %s\n' "${missing[*]}" >&2
        return 1
    fi
}

gf_require_dir() {
    local name="$1" path="${!1:-}"
    if [[ ! -d "${path}" ]]; then
        echo "${name}=${path} is not a directory on this filesystem." >&2
        return 1
    fi
}

# Activate the analysis environment. Every site-specific name comes from cluster.env so
# that this file contains no cluster-specific assumptions.
gf_activate_environment() {
    local module_name
    if [[ -n "${GF_CONDA_MODULE:-}" ]]; then
        module load "${GF_CONDA_MODULE}"
    fi
    for module_name in ${GF_EXTRA_MODULES:-}; do
        module load "${module_name}"
    done
    if ! command -v conda >/dev/null 2>&1; then
        echo "conda not found. Set GF_CONDA_MODULE in cluster.env to your site's module." >&2
        return 1
    fi
    eval "$(conda shell.bash hook)"
    conda activate "${GF_ENV_PREFIX}"
    local tool
    for tool in amrfinder mash python; do
        if ! command -v "${tool}" >/dev/null 2>&1; then
            echo "${tool} missing from ${GF_ENV_PREFIX}." >&2
            return 1
        fi
    done
}

# Number of data rows in the cohort CSV, which is also the number of array tasks.
gf_cohort_rows() {
    local cohort="${1:?cohort path required}"
    local total
    total=$(($(wc -l < "${cohort}") - 1))
    if (( total < 1 )); then
        echo "Cohort ${cohort} has no data rows." >&2
        return 1
    fi
    echo "${total}"
}
