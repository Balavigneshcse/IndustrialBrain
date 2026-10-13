#!/usr/bin/env bash
# Creates the Unsloth training environment on WSL's own ext4 disk (much faster than /mnt/c).
# Follows Unsloth's documented setup: uv + Python 3.13 + `--torch-backend=auto`.
# Run as your normal WSL user:  wsl -d Ubuntu -- bash ml/setup/02_wsl_training_env.sh
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ML_HOME="${ML_HOME:-$HOME/indusmind-ml}"
mkdir -p "$ML_HOME"

if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

[ -d "$ML_HOME/.venv" ] || uv venv "$ML_HOME/.venv" --python 3.13
# shellcheck disable=SC1091
source "$ML_HOME/.venv/bin/activate"

uv pip install unsloth --torch-backend=auto
# Extras: HF CLI, data tooling, logging, and GGUF conversion deps (installed individually so
# llama.cpp's own requirements file cannot swap our CUDA torch for a CPU build).
uv pip install "huggingface_hub[cli]" datasets pandas pyarrow pyyaml tensorboard gguf sentencepiece protobuf

# Importing unsloth writes ./unsloth_compiled_cache, so run the check from ML_HOME, not the repo.
cd "$ML_HOME"
python - <<'EOF'
import torch
print("torch", torch.__version__, "| cuda", torch.version.cuda, "| gpu available:", torch.cuda.is_available())
if torch.cuda.is_available():
    free, total = torch.cuda.mem_get_info()
    print("gpu", torch.cuda.get_device_name(0), f"| free {free/2**30:.2f} / {total/2**30:.2f} GiB")
import unsloth, transformers, trl, peft, bitsandbytes
print("unsloth", unsloth.__version__, "| transformers", transformers.__version__, "| trl", trl.__version__,
      "| peft", peft.__version__, "| bitsandbytes", bitsandbytes.__version__)
EOF

# Pin exactly what was installed, for reproducible training runs.
uv pip freeze > "$PROJECT/ml/requirements-train.lock.txt"
echo "[02] training env OK -> $ML_HOME/.venv (lock: ml/requirements-train.lock.txt)"
