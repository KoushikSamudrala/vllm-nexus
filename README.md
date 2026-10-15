# vllm-nexus

Production-ready guide for running a self-hosted chat interface backed by vLLM and Streamlit, packaged for NVIDIA GPU Docker deployment.

vllm-nexus provides a minimal, audited example of serving an OpenAI-compatible inference API with vLLM and a lightweight Streamlit web UI that consumes that API. This README focuses on a production-oriented deployment using Docker + NVIDIA GPUs, and includes a dedicated guide for launching on AWS EC2 GPU instances.

---

https://github.com/user-attachments/assets/f33984a6-9ea0-4e05-9e55-4f97b743ea3d



---

## Key features

- Streamlit chat UI with streaming token updates
- vLLM OpenAI-compatible API server for model hosting and GPU inference
- Dockerfile tuned for CUDA + PyTorch wheels
- Simple entrypoint orchestration (vLLM -> health check -> Streamlit)

---

## Quick production checklist

1. Use a machine with a supported NVIDIA GPU and drivers matching your container CUDA version.
2. Secure the service behind a reverse proxy (nginx/Traefik) with TLS and authentication.
3. Avoid `--trust-remote-code` in untrusted environments.
4. Monitor GPU memory and expose metrics; use smaller models or sharding if needed.

---

## Minimal production run (recommended)

This example builds the container and exposes relevant ports for both LLM app and streamlit UI. For a single-host quick test you can still use docker run:

```bash
# Build image
docker build -t vllm-nexus .

# Run container (exposes 80 for UI and 8000 for vLLM inside container)
docker run --gpus all --rm \
  -p 127.0.0.1:80:80 \
  -e MODEL_ID=Qwen/Qwen2-1.5B-Instruct \
  -e GPU_UTIL=0.85 \
  -e VLLM_HOST=http://localhost:8000 \
  vllm-nexus
```

Production notes:
- Bind Streamlit to localhost (use a reverse proxy to expose externally).
- Use a reverse proxy (nginx / Traefik) to terminate TLS, add authentication, and optionally rate-limit.
- Run the service under a process manager (systemd) or inside a Docker Compose/Swarm/Kubernetes setup.

---

## Docker Compose (example)

Create a simple `docker-compose.yml` that places nginx in front of the single container or use Traefik for automatic LetsEncrypt. Compose is not included in this repo but recommended for production.

---

## AWS EC2 (GPU) deployment

A dedicated guide for launching and configuring an EC2 GPU instance is included in `g4-instance-setup.md`. It walks through choosing an instance type, installing NVIDIA drivers, Docker, and the NVIDIA Container Toolkit, and basic disk management tips.

Quick summary (follow `g4-instance-setup.md` for full steps):

1. Launch an Ubuntu 22.04 EC2 instance (example: `g4dn.xlarge` for a single T4 GPU).
2. Open inbound ports 22 (SSH), 80 (Streamlit UI / reverse proxy), and 8000 (vLLM - keep this private behind a proxy in production).
3. Install the NVIDIA driver and verify `nvidia-smi` shows the GPU.
4. Install Docker and the NVIDIA Container Toolkit so containers can access GPUs.
5. Clone this repo on the instance, build the image, and run with `--gpus all`.

Example commands on the EC2 host:

```bash
# clone and build
git clone https://github.com/KoushikSamudrala/vllm-nexus.git
cd vllm-nexus
docker build -t vllm-nexus .

# run (example)
docker run --gpus all -d --restart unless-stopped \
  -p 127.0.0.1:80:80 \
  -e MODEL_ID=Qwen/Qwen2-1.5B-Instruct \
  -e GPU_UTIL=0.85 \
  -e VLLM_HOST=http://localhost:8000 \
  vllm-nexus
```

Security note: In production, do NOT expose the vLLM API port (8000) publicly. Terminate TLS at a reverse proxy on port 443/80 and proxy requests to the container on the host network or via a private network interface.

See `g4-instance-setup.md` for a step-by-step walkthrough, command snippets, and troubleshooting tips specific to AWS EC2 GPU instances.

---

## Configuration / environment variables

- MODEL_ID (default: `Qwen/Qwen2-1.5B-Instruct`) — model identifier for vLLM
- GPU_UTIL (default: `0.85`) — target fraction of GPU memory to use
- MAX_MODEL_LEN (default: `2048`) — model context length
- VLLM_HOST (default in app.py: `http://localhost:8000`) — Streamlit client -> vLLM API endpoint

Set these with `-e` when running the container or export them in your process manager.

---

## Files and responsibilities

- Dockerfile — CUDA runtime base, installs CUDA-pinned PyTorch wheels and project requirements, copies app and entrypoint.
- entrypoint.sh — starts the vLLM server (background), polls `/health`, then launches Streamlit.
- app.py — Streamlit frontend:
  - Checks vLLM health and lists served models (`/v1/models`).
  - Sends streaming chat requests to `/v1/chat/completions` and renders SSE-style deltas incrementally.
  - Stores per-session chat history in Streamlit's in-memory session state.
- requirements.txt — pinned Python dependencies for the demo (vllm, transformers, streamlit, requests, torch/xformers).
- g4-instance-setup.md — step-by-step EC2 GPU instance setup and deployment notes for AWS (new).
- vllm-deployment-docker.pdf — reference/deployment notes (kept for documentation).

---

## Architecture (portable text diagram)



```
+-------------+           HTTP/WS            +-----------------------------+           +--------------------+
|  User       | <--------------------------> | Streamlit UI (app.py)       | <-------> | vLLM API Server    |
|  Browser    |                              | - session state (in-memory)  |           | - OpenAI-compatible|
+-------------+                              | - streaming client requests |           |   endpoints (/v1)  |
                                              +-----------------------------+           +---------+----------+
                                                                                                      |
                                                                                                      |  GPU inference
                                                                                                      v
                                                                                         +-------------------------------+
                                                                                         | NVIDIA GPU(s) + model files   |
                                                                                         +-------------------------------+
```

Streaming flow summary:
- Streamlit posts to `/v1/chat/completions` with `stream=True`.
- vLLM responds using SSE-like `data: ...` lines containing JSON deltas.
- app.py's `parse_stream()` reads `response.iter_lines()` and updates the UI as chunks arrive.

---

## Security & production hardening

- Authentication: add reverse-proxy authentication (HTTP basic, OAuth, or JWT). Streamlit itself is not an authentication server.
- TLS: terminate TLS at a reverse proxy. Do not expose the vLLM port (8000) publicly — only the reverse proxy should access it.
- Secrets: avoid embedding credentials or tokens in images; pass via environment or secret stores (Vault, Docker secrets).
- trust-remote-code: disable for untrusted models; enabling it runs arbitrary Python when loading a model.

---

## Observability

- Capture container logs (stdout/stderr) and GPU metrics (nvidia-smi, DCGM exporter).
- Instrument the reverse proxy with access logs and use Prometheus + Grafana for metrics where possible.

---

## Troubleshooting quick tips

- `Server Offline` in UI: from the container, curl http://localhost:8000/health. Confirm vLLM process started.
- OOM errors: switch to a smaller model or lower `GPU_UTIL`.
- Long model downloads: pre-pull model weights to a cache or local path used by vLLM.

---

## Notes and known issues

- entrypoint.sh: the `python3 -m vllm.entrypoints.openai.api_server` command in `entrypoint.sh` has a broken line break: the `--host 0.0.0.0` line is not escaped with a trailing backslash before the next `--dtype` option, which will cause a shell syntax/command error. You can fix it by joining the options on one line or adding backslashes at line ends. If you want, I can open a small PR to fix this in `entrypoint.sh`.

---

## Contributing & license

Contributions welcome. For production-readiness PRs consider:
- docker-compose or Kubernetes manifests

