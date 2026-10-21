#!/usr/bin/env bash
# Обучение LoRA через ai-toolkit на моделях из ComfyUI/models.
# Использование: ./scripts/train_lora.sh training/auburn_freckles.yaml
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
export MODELS_PATH="$ROOT/ComfyUI/models"
cd "$ROOT/ai-toolkit"
venv/bin/python run.py "$CONFIG"
echo "LoRA: ai-toolkit/output/<name>/. Выбранный файл скопировать в ComfyUI/models/loras."
