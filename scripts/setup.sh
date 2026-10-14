#!/usr/bin/env bash
# Установка на Linux: ./scripts/setup.sh server [h3-server ...]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d ComfyUI ]; then
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git ComfyUI
else
    git -C ComfyUI pull --ff-only
fi

[ -d .venv ] || python3 -m venv .venv
PY="$ROOT/.venv/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu130
"$PY" -m pip install -r ComfyUI/requirements.txt

"$PY" scripts/download_models.py --profile "${@:-server}"
echo "Готово. Запуск: ./scripts/run.sh"
