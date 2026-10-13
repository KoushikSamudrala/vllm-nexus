#!/bin/bash

set -e
# Exit immediately if any command fails.
# This prevents the script from continuing if vLLM or Streamlit fails to start.

MODEL_ID="${MODEL_ID:-Qwen/Qwen2-1.5B-Instruct}"
# Set model name from environment variable if provided.
# If not provided, use the default model:Qwen/Qwen2-1.5B-Instruct

GPU_UTIL="${GPU_UTIL:-0.85}"
# Set GPU memory utilization from environment variable if provided.
# Default is 0.85 (85% of GPU memory usage target).

MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
# Set maximum model context length.
# Default is 2048 tokens.

echo "==> Starting vLLM server with model: $MODEL_ID"

python3 -m vllm.entrypoints.openai.api_server \
    --model $MODEL_ID \
    --max-model-len $MAX_MODEL_LEN \
    --gpu-memory-utilization $GPU_UTIL \
    --port 8000 \
    --host 0.0.0.0
    --dtype float16 \
    --trust-remote-code \
    --guided-decoding-backend lm-format-enforcer \
    --served-model-name $MODEL_ID &

echo "==> waiting for vLLM server to start..."
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
  echo "==> vLLM server is not up yet. Waiting..."
  sleep 5
done

echo "==> vLLM server is up and running."
exec streamlit run app.py --server.port 80 --server.address 0.0.0.0 --server.headless true