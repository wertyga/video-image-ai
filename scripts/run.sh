#!/usr/bin/env bash
# Запуск ComfyUI на Linux. По умолчанию слушает только localhost:
# заходите через SSH-туннель: ssh -L 8188:127.0.0.1:8188 user@server
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/.venv/bin/python" "$ROOT/ComfyUI/main.py" --output-directory "$ROOT/output" "$@"
