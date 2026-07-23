#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
runner="${ROOT_DIR}/scripts/run_github_fixture_sample.sh"

if [[ $# -gt 1 ]]; then
  echo "Usage: $0 [candidate_01..candidate_04]" >&2
  exit 2
fi

if [[ $# -eq 1 ]]; then
  candidates=("$1")
else
  candidates=(candidate_01 candidate_02 candidate_03 candidate_04)
fi

for candidate in "${candidates[@]}"; do
  for variant in clean bio_injection repo_injection; do
    "${runner}" "${candidate}" "${variant}"
  done
done
