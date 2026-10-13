# ML

Model work for IndusMind: Phase 5 of [docs/upgrade-plan.md](../docs/upgrade-plan.md). The plan fine-tunes **Qwen3-4B-Instruct-2507** with QLoRA on the RTX 3050 (4 GB), then exports it to GGUF for Ollama.

| Path | Purpose |
|---|---|
| `setup/01_wsl_root_packages.sh` | Compilers and tools in WSL (runs as WSL root, no sudo password) |
| `setup/02_wsl_training_env.sh` | uv + Python 3.13 venv at `~/indusmind-ml/.venv` with Unsloth; writes `requirements-train.lock.txt` |
| `setup/03_download_models_data.sh` | Base 4-bit model, training datasets (`ml/data/raw/`), retrieval models (`data/models/fastembed/`) |
| `setup/04_build_llamacpp.sh` | CPU build of the llama.cpp tools used for GGUF export |
| `requirements-train.lock.txt` | Exact versions of the training environment |
| `data/` | Datasets and model caches (git-ignored); `data/legacy/` holds the retired Llama-3-8B adapter |

Run the setup scripts from the repository root:

```bat
wsl -d Ubuntu -u root -- bash ml/setup/01_wsl_root_packages.sh
wsl -d Ubuntu -- bash ml/setup/02_wsl_training_env.sh
wsl -d Ubuntu -- bash ml/setup/03_download_models_data.sh
wsl -d Ubuntu -- bash ml/setup/04_build_llamacpp.sh
```

The training, evaluation and export commands (`ml\ml.cmd`) arrive in Phase 5.
