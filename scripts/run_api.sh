#!/usr/bin/env bash
# Запуск HTTP API для видео. Настройки в api/.env, ComfyUI должен слушать COMFY_URL.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/api"
exec node dist/main
