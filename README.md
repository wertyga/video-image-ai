# AdUltAi

ComfyUI + Qwen Image 2.1 + [NSFW LoRA v2 by TheseAlpacas](https://civitai.com/models/2958918).
Модели в репозиторий не входят: их скачивает `setup` под выбранный профиль.

## Профили

| Профиль | Для чего | Модель / энкодер | Скачать |
|---|---|---|---|
| `local-16gb` | RTX 4060 Ti 16GB, 32GB RAM | int8 / int8 | ~17 ГБ |
| `server` | 48GB+ VRAM (A6000, L40S, A100, H100) | bf16 / bf16 (максимальное качество) | ~33 ГБ |

LoRA и VAE одинаковые для обоих профилей.

## Установка

1. `cp .env.example .env` и вписать `CIVITAI_TOKEN` (civitai.com → Account → API Keys).
2. Windows: `.\scripts\setup.ps1 -Profile local-16gb`
   Linux: `./scripts/setup.sh server`

Нужны git, Python 3.13 (на Linux подойдёт python3 ≥ 3.10) и драйвер NVIDIA с поддержкой CUDA 13.

## Запуск

- Windows: `.\scripts\run.ps1` → http://127.0.0.1:8188
- Linux: `./scripts/run.sh`, затем с локального компа `ssh -L 8188:127.0.0.1:8188 user@server` и открыть http://127.0.0.1:8188.
  Не запускайте с `--listen 0.0.0.0` на публичном IP: у ComfyUI нет авторизации.

В интерфейсе: перетащить `workflows/qwen21_nsfw_local.json` (или `_server.json`) в окно ComfyUI.

Без браузера (ComfyUI должен быть запущен):

```
python scripts/generate.py --profile server -p "..." --count 4 --width 832 --height 1216
```

## Настройки (рекомендации автора LoRA)

- 25+ шагов (по умолчанию 30), CFG 3–6 (по умолчанию 4)
- сила LoRA 0.8–1.0 (по умолчанию 0.9)
- sampler **er_sde** (на euler результат плохой), scheduler **beta**
- триггер-слов нет; обучен в основном на откровенных сценах, лучше работают явные описания
- разрешение кратно 32; модель поддерживает до 2048×2048
