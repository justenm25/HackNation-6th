#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="${GF_MODEL_BUNDLE:-${PROJECT_DIR}/models/ecoli-bundle}"
LOCAL_ENV="${PROJECT_DIR}/../../amrfinderplus-env/bin"

if [[ ! -f "${BUNDLE}/bundle_manifest.json" ]]; then
    echo "Model bundle not found: ${BUNDLE}" >&2
    exit 1
fi

if [[ -n "${GF_AMRFINDER:-}" ]]; then
    AMRFINDER="${GF_AMRFINDER}"
elif command -v amrfinder >/dev/null 2>&1; then
    AMRFINDER="$(command -v amrfinder)"
elif [[ -x "${LOCAL_ENV}/amrfinder" ]]; then
    AMRFINDER="${LOCAL_ENV}/amrfinder"
else
    echo "AMRFinderPlus was not found. Set GF_AMRFINDER=/absolute/path/to/amrfinder." >&2
    exit 1
fi

if [[ -n "${GF_STREAMLIT:-}" ]]; then
    STREAMLIT="${GF_STREAMLIT}"
elif command -v streamlit >/dev/null 2>&1; then
    STREAMLIT="$(command -v streamlit)"
elif [[ -x "${LOCAL_ENV}/streamlit" ]]; then
    STREAMLIT="${LOCAL_ENV}/streamlit"
else
    echo "Streamlit was not found. Install requirements.txt or set GF_STREAMLIT." >&2
    exit 1
fi

export GF_MODEL_BUNDLE="${BUNDLE}"
export GF_AMRFINDER="${AMRFINDER}"

cd "${PROJECT_DIR}"
exec "${STREAMLIT}" run app/streamlit_app.py "${@}"
