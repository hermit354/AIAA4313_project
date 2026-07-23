#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLE_ROOT="${ROOT_DIR}/test_data/github_fixture_samples"
PDF_PATH="${SAMPLE_ROOT}/resumes/candidate_01_resume_injection.pdf"
RESULT_DIR="${SAMPLE_ROOT}/results"

if [[ ! -f "${PDF_PATH}" ]]; then
  "${ROOT_DIR}/scripts/build_resume_injection_sample.py"
fi

export GITHUB_FIXTURE_DIR="${SAMPLE_ROOT}/fixtures/clean"
unset GITHUB_FIXTURE_FALLBACK_DIR || true
mkdir -p "${RESULT_DIR}"

"${ROOT_DIR}/scripts/score_resume.sh" "${PDF_PATH}" 2>&1 \
  | tee "${RESULT_DIR}/candidate_01_resume_injection.log"
