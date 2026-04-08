#!/bin/bash
# Start vLLM for Qwen3.5 122B reasoning model
# Run on DGX Spark host (not in Docker)
# Usage: bash infra/vllm/start-122b.sh
#
# NOTE: --quantization fp8 uses vLLM's native FP8 quantization.
# If using a GGUF Q8_0 model file instead, remove --quantization
# and point MODEL to the GGUF path. Adjust as needed for your setup.

set -euo pipefail

MODEL="Qwen/Qwen3.5-122B-A10B"
PORT=8000

echo "Starting vLLM for ${MODEL} on port ${PORT}..."

vllm serve "${MODEL}" \
  --port "${PORT}" \
  --quantization fp8 \
  --tensor-parallel-size 1 \
  --max-model-len 131072 \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --served-model-name qwen-large \
  --gpu-memory-utilization 0.88 \
  --max-num-seqs 8
