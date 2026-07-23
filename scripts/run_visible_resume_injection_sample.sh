#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLE_ROOT="${ROOT_DIR}/test_data/github_fixture_samples"
RESULT_DIR="${SAMPLE_ROOT}/results"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <visible_descriptive_single|visible_instructive_single|visible_descriptive_repeated|visible_instructive_repeated|visible_mild_score_self_assessment_single|visible_mild_score_self_assessment_repeated|visible_mild_role_self_assessment_single|visible_mild_role_self_assessment_repeated|visible_mild_third_person_high_score_single>" >&2
  exit 2
fi

variant="$1"
case "${variant}" in
  visible_descriptive_single|visible_instructive_single|visible_descriptive_repeated|visible_instructive_repeated|visible_mild_score_self_assessment_single|visible_mild_score_self_assessment_repeated|visible_mild_role_self_assessment_single|visible_mild_role_self_assessment_repeated|visible_mild_third_person_high_score_single)
    ;;
  *)
    echo "Unknown visible injection variant: ${variant}" >&2
    exit 2
    ;;
esac

pdf_path="${SAMPLE_ROOT}/resumes/candidate_01_${variant}.pdf"
if [[ ! -f "${pdf_path}" ]]; then
  "${ROOT_DIR}/scripts/build_visible_resume_injection_samples.py"
fi

export GITHUB_FIXTURE_DIR="${SAMPLE_ROOT}/fixtures/clean"
unset GITHUB_FIXTURE_FALLBACK_DIR || true
mkdir -p "${RESULT_DIR}"

"${ROOT_DIR}/scripts/score_resume.sh" "${pdf_path}" 2>&1 \
  | tee "${RESULT_DIR}/candidate_01_${variant}.log"
