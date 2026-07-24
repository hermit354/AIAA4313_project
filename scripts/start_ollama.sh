#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-4}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-${ROOT_DIR}/.ollama/models}"
if command -v nvidia-smi >/dev/null 2>&1 && [[ -z "${OLLAMA_LLM_LIBRARY:-}" ]]; then
  if [[ -f "${ROOT_DIR}/.tools/ollama/lib/ollama/cuda_v13/libggml-cuda.so" ]]; then
    export OLLAMA_LLM_LIBRARY="cuda_v13"
    export OLLAMA_VULKAN="${OLLAMA_VULKAN:-false}"
  elif [[ -f "${ROOT_DIR}/.tools/ollama/lib/ollama/cuda_v12/libggml-cuda.so" ]]; then
    export OLLAMA_LLM_LIBRARY="cuda_v12"
    export OLLAMA_VULKAN="${OLLAMA_VULKAN:-false}"
  fi
fi
unset ALL_PROXY all_proxy
export NO_PROXY="${NO_PROXY:+${NO_PROXY},}127.0.0.1,localhost"
export no_proxy="${no_proxy:+${no_proxy},}127.0.0.1,localhost"

mkdir -p "${OLLAMA_MODELS}"
exec "${ROOT_DIR}/.tools/ollama/bin/ollama" serve
