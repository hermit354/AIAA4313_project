#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
runner="${ROOT_DIR}/scripts/run_visible_resume_injection_sample.sh"

variants=(
  visible_descriptive_single
  visible_instructive_single
  visible_descriptive_repeated
  visible_instructive_repeated
)

for variant in "${variants[@]}"; do
  "${runner}" "${variant}"
done
