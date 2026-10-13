#!/usr/bin/env bash
# Downloads the base model, training datasets and CPU retrieval models listed in docs/upgrade-plan.md §7.
# Run as your normal WSL user:  wsl -d Ubuntu -- bash ml/setup/03_download_models_data.sh
# Safe to re-run: `hf download` resumes and skips files that are already complete.
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RAW="$PROJECT/ml/data/raw"
FASTEMBED_DIR="$PROJECT/data/models/fastembed"
TOOLS="$HOME/indusmind-tools/.venv"
export PATH="$HOME/.local/bin:$PATH"

# Small separate env so fastembed/onnxruntime never touch the training env.
# Python 3.12 + a version floor: on 3.13 uv resolved an ancient fastembed that needs Rust.
[ -x "$TOOLS/bin/python3.12" ] || { rm -rf "$TOOLS"; uv venv "$TOOLS" --python 3.12; }
# shellcheck disable=SC1091
source "$TOOLS/bin/activate"
uv pip install "huggingface_hub[cli]" "fastembed>=0.5"

mkdir -p "$RAW" "$FASTEMBED_DIR"

echo "[03] base model (4-bit, for QLoRA) -> WSL HF cache"
hf download unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit

echo "[03] datasets -> ml/data/raw"
hf download glaiveai/RAG-v1                 --repo-type dataset --local-dir "$RAW/glaive-rag-v1"
hf download neural-bridge/rag-dataset-12000 --repo-type dataset --local-dir "$RAW/neural-bridge-rag-12000"
hf download rajpurkar/squad_v2              --repo-type dataset --local-dir "$RAW/squad_v2"

if [ ! -f "$RAW/ai4i2020/ai4i2020.csv" ]; then
  curl -fL -o "$RAW/ai4i2020.zip" \
    "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
  unzip -o "$RAW/ai4i2020.zip" -d "$RAW/ai4i2020"
  rm -f "$RAW/ai4i2020.zip"
fi

echo "[03] retrieval models (ONNX, CPU) -> data/models/fastembed"
python - "$FASTEMBED_DIR" <<'EOF'
import sys
from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder

cache = sys.argv[1]
emb = TextEmbedding("BAAI/bge-small-en-v1.5", cache_dir=cache)
print("bge-small-en-v1.5 dim:", len(next(iter(emb.embed(["pump bearing vibration"])))))
docs = ["Bearing temperature: below 90 C", "Obtain an approved work permit."]
for name in ("BAAI/bge-reranker-base", "Xenova/ms-marco-MiniLM-L-6-v2"):
    scores = list(TextCrossEncoder(name, cache_dir=cache).rerank("bearing temperature limit", docs))
    print(f"{name} scores:", [round(s, 2) for s in scores])
EOF

echo "[03] downloads OK"
