# vllm-nexus

Self-hosted LLM chat interface using vLLM and Streamlit, packaged for NVIDIA GPU Docker deployment.

This README explains the project components, how the pieces fit together, and step-by-step instructions for getting a working instance running locally or on a GPU-capable server. It's written for beginners who want to run an open-weight model via vLLM with a simple Streamlit frontend.

---

## Table of Contents

- What this project does
- Requirements
- Quick start (Docker)
- Development / run locally (no Docker)
- Configuration and environment variables
- File-by-file explanation
- Architecture (high-level diagram)
- Troubleshooting
- Security and production notes
- Contributing
- License

---

## What this project does

vllm-nexus provides a small, opinionated example of running a vLLM OpenAI-compatible server together with a Streamlit-based web UI so you can interactively chat with a model served on your own hardware. The server (vLLM) handles model loading, inference, and a streaming OpenAI-like API. The Streamlit app (app.py) offers a user-friendly chat interface that connects to that API.

This is useful for experimenting with open-weight LLMs, prototyping private LLM tooling, or learning how vLLM integrates with web frontends.

---

## Requirements

- A machine with an NVIDIA GPU and recent drivers (recommended for real model inference).
- Docker + NVIDIA Container Toolkit (for --gpus capability). If you run locally without Docker you'll need Python 3.10+ and the libraries listed in requirements.txt.
- Enough disk space to download model artifacts (varies by model)
- Optional: an active internet connection to download models from Hugging Face if you reference remote model IDs

---

## Quick start (Docker)

Build the image (this image is based on an NVIDIA CUDA runtime and installs PyTorch and other dependencies):

```bash
# Build the Docker image (from repo root)
docker build -t vllm-nexus .

# Run the container, exposing Streamlit UI (80) and vLLM API (8000) to the host
# Use --gpus all to allow GPU access inside the container
docker run --gpus all -p 80:80 -p 8000:8000 \
  -e MODEL_ID=Qwen/Qwen2-1.5B-Instruct \
  -e GPU_UTIL=0.85 \
  vllm-nexus
```

Open http://localhost/ in your browser to access the Streamlit UI.

Notes:
- The default `MODEL_ID` is `Qwen/Qwen2-1.5B-Instruct`. Change it to any vLLM-compatible model name (Hugging Face ID or local path) that vLLM supports.
- The Dockerfile installs CUDA-enabled PyTorch wheels. If you want a CPU-only build, modify the Dockerfile accordingly.

---

## Development / run locally (no Docker)

If you prefer to run locally without Docker (developer mode):

1. Create and activate a virtual environment (Python 3.10+ recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start vLLM server directly (the entrypoint script demonstrates recommended flags):

```bash
# Example (adapt model id and flags as needed):
python3 -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2-1.5B-Instruct \
  --max-model-len 2048 \
  --gpu-memory-utilization 0.85 \
  --port 8000 \
  --host 0.0.0.0 \
  --dtype float16 \
  --trust-remote-code \
  --guided-decoding-backend lm-format-enforcer \
  --served-model-name Qwen/Qwen2-1.5B-Instruct
```

3. In a separate shell run the Streamlit app:

```bash
streamlit run app.py --server.port 80 --server.address 0.0.0.0 --server.headless true
```

The Streamlit UI expects the vLLM server on `http://localhost:8000` by default. Set the `VLLM_HOST` environment variable if your vLLM server runs elsewhere.

---

## Configuration and environment variables

The project supports a few environment variables (defaults shown in `entrypoint.sh` and `app.py`):

- MODEL_ID (default: `Qwen/Qwen2-1.5B-Instruct`) — model identifier passed to vLLM. Can be a Hugging Face repo ID or a local path if vLLM supports it.
- GPU_UTIL (default: `0.85`) — target GPU memory utilization passed to vLLM. Choose lower values on multi-tenant GPUs.
- MAX_MODEL_LEN (default: `2048`) — vLLM max context length.
- VLLM_HOST (default in app.py: `http://localhost:8000`) — where the Streamlit UI sends API requests.

When running the Docker container use `-e KEY=VALUE` to set these.

---

## File-by-file explanation

This section describes the key files and what they do so beginners can quickly find and modify relevant parts.

- README.md (this file): Guides beginners through setup and explains architecture.

- Dockerfile: Builds an NVIDIA CUDA runtime image, installs Python and CUDA-matched PyTorch wheels, pip-installs the requirements, and copies the app and entrypoint into the image. Exposes ports 80 (Streamlit UI) and 8000 (vLLM API).

- entrypoint.sh: Shell wrapper used by the Docker container. It:
  - Sets sensible defaults for MODEL_ID, GPU utilization, and context length.
  - Launches vLLM's OpenAI-compatible API server as a background process with recommended flags.
  - Polls the server's `/health` endpoint until ready.
  - Starts Streamlit pointing at `app.py` on port 80.

  Tip: Use this script as a reference for flags to pass when running vLLM locally.

- app.py: The Streamlit chat UI. Main responsibilities:
  - Check vLLM health at `/health` and list models from `/v1/models`.
  - Provide a chat interface that stores the session in `st.session_state`.
  - When a user sends a message, forward the chat to vLLM's `/v1/chat/completions` with `stream=True`.
  - Parse Server-Sent Event (SSE) style streaming responses and render them incrementally in the browser.

  Key functions:
  - `check_health()` — simple HTTP GET to the vLLM health endpoint.
  - `fetch_models()` — gets available served models.
  - `chat_stream()` — posts a streaming chat request.
  - `parse_stream()` — yields incremental content chunks from SSE data lines.

  Where to change behavior:
  - Adjust UI elements (temperature, top_p sliders) in the sidebar.
  - Customize parsing/rendering for richer UI (e.g., roles, attachments).

- requirements.txt: Python dependencies pinned for a working demo. Important packages include `vllm`, `transformers`, `streamlit`, `torch` (CUDA-matched), `xformers` (optional performance improvement), and `requests`.

- vllm-deployment-docker.pdf: A large PDF included in the repo — likely deployment notes or reference diagrams for setting up vLLM with Docker. Read it if you want more background on vLLM deployment patterns.

---

## Architecture (high-level diagram)

Below is a simple diagram showing the runtime components and the data flow between them. This is intended to help you reason about where to make changes.

```mermaid
flowchart LR
  A[User Browser] -->|HTTP (Streamlit)| B[Streamlit UI: app.py]
  B -->|HTTP (requests)| C[vLLM OpenAI-compatible API Server]
  C -->|GPU inference| D[NVIDIA GPU + Model Parameters]
  C -->|Model files| E[Hugging Face / Local Model Cache]
  B -->|Session state| F[Streamlit Session State (in-memory)]

  style D fill:#f9f,stroke:#333,stroke-width:1px
  style C fill:#bbf,stroke:#333,stroke-width:1px
  style B fill:#bfb,stroke:#333,stroke-width:1px
```

If you cannot render mermaid diagrams, a plain ASCII version:

```
[Browser] --HTTP--> [Streamlit app (app.py)] --HTTP--> [vLLM API server] --(uses GPU)--> [NVIDIA GPU + model files]
```

How streaming works:
- Streamlit calls the vLLM `/v1/chat/completions` endpoint using `stream=True`.
- vLLM responds with Server-Sent Events (SSE)-style lines containing JSON deltas.
- The Streamlit app reads those lines incrementally (`response.iter_lines()`), parses the JSON, and updates the UI as tokens arrive.

---

## Troubleshooting

Common issues and fixes:

- vLLM server fails to start or crashes:
  - Check the container logs and the `entrypoint.sh` output.
  - Ensure your model fits in GPU memory. Lower `GPU_UTIL` or choose a smaller model.
  - Remove `--trust-remote-code` if you have security concerns when loading untrusted model code.

- Streamlit shows "Server Offline" or "No models available":
  - Confirm the vLLM API is reachable at the value of `VLLM_HOST`.
  - Curl the health endpoint from inside the container: `curl -i http://localhost:8000/health`.

- Long model download times / disk usage:
  - Models from Hugging Face can be large. Downloading depends on your bandwidth and where caching is configured for vLLM.

- GPU memory OOMs:
  - Use a smaller model or reduce `--gpu-memory-utilization`.
  - Ensure drivers and CUDA versions match the container base image.

---

## Security and production notes

- This project is intended as an example and not production hardened.
- If you expose the vLLM API or Streamlit UI beyond a local/trusted network, add authentication and TLS (reverse proxy with nginx/Traefik + certs).
- Carefully consider `--trust-remote-code` (used to allow models with custom code). It can execute arbitrary python during model load. Avoid it in multi-tenant or untrusted environments.

---

## Contributing

Contributions and improvements are welcome. Suggestions:
- Add Docker Compose for easier multi-container setups.
- Add an authentication layer for the Streamlit UI.
- Persist chat history (e.g., SQLite or simple JSON storage) for multi-session demos.

When opening PRs, include small, focused changes and update this README where appropriate.

---

## License

(This repo currently has no license file. Add a LICENSE file to make reuse and contributions explicit.)
