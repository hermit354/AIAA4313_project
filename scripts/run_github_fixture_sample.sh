#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLE_ROOT="${ROOT_DIR}/test_data/github_fixture_samples"

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <candidate_01..candidate_04> <clean|bio_injection|repo_injection>" >&2
  exit 2
fi

candidate="$1"
variant="$2"
pdf_path="${SAMPLE_ROOT}/resumes/${candidate}.pdf"
variant_dir="${SAMPLE_ROOT}/fixtures/${variant}"
clean_dir="${SAMPLE_ROOT}/fixtures/clean"
result_dir="${SAMPLE_ROOT}/results"

if [[ ! -f "${pdf_path}" ]]; then
  echo "Unknown candidate PDF: ${pdf_path}" >&2
  exit 2
fi

case "${variant}" in
  clean)
    unset GITHUB_FIXTURE_FALLBACK_DIR || true
    ;;
  bio_injection|repo_injection)
    export GITHUB_FIXTURE_FALLBACK_DIR="${clean_dir}"
    ;;
  *)
    echo "Unknown variant: ${variant}" >&2
    exit 2
    ;;
esac

export GITHUB_FIXTURE_DIR="${variant_dir}"
mkdir -p "${result_dir}"

"${ROOT_DIR}/scripts/score_resume.sh" "${pdf_path}" 2>&1 \
  | tee "${result_dir}/${candidate}_${variant}.log"
