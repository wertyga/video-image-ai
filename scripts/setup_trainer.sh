#!/usr/bin/env bash
# Установка ai-toolkit (обучение LoRA) в ./ai-toolkit с отдельным Python 3.12.
# Требует уже выполненный ./scripts/setup.sh (venv с ComfyUI и модели).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
"$ROOT/.venv/bin/python" -m pip install -q uv
UV="$ROOT/.venv/bin/uv"
[ -d ai-toolkit ] || git clone --depth 1 https://github.com/ostris/ai-toolkit.git ai-toolkit
cd ai-toolkit
[ -d venv ] || "$UV" venv --python 3.12 venv
"$UV" pip install --python venv/bin/python torch==2.13.0 torchvision==0.28.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130
"$UV" pip install --python venv/bin/python -r requirements.txt --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cu130
venv/bin/python -c "import torch; assert torch.cuda.is_available(); print('ai-toolkit ready, torch', torch.__version__)"
