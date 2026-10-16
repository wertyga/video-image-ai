#!/usr/bin/env bash
# Установка HTTP API для видео (Linux-сервер, после setup.sh): ./scripts/setup_api.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/api"

if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
fi

npm ci --no-audit --no-fund
npm run build

if [ ! -f .env ]; then
    cp .env.example .env
    sed -i "s/^API_TOKEN=.*/API_TOKEN=$(openssl rand -hex 32)/" .env
    echo "Создан api/.env с новым токеном:"
    grep '^API_TOKEN=' .env
fi
echo "Готово. Запуск: ./scripts/run_api.sh (ComfyUI должен быть запущен)"
