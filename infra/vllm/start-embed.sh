#!/bin/bash
# Start vLLM for Qwen3.5 9B embedding model
# Run on DGX Spark A host only (not in Docker)
# Usage: bash infra/vllm/start-embed.sh

set -euo pipefail

MODEL="Qwen/Qwen3.5-9B"
PORT=8002

echo "Starting vLLM embedding for ${MODEL} on port ${PORT}..."

vllm serve "${MODEL}" \
  --port "${PORT}" \
  --task embed \
  --max-model-len 8192 \
  --served-model-name qwen-embed \
  --gpu-memory-utilization 0.08
