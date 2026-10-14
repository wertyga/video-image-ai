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

## Image-to-image

Два режима, оба с LoRA:

- **Редактирование** (родной режим Qwen Image 2.1). Модель видит картинку и выполняет инструкцию;
  лицо, поза и фон сохраняются. В промпте исходная картинка называется `<image1>`.
  ```
  python scripts/generate.py --image in.png -p "Change the outfit of the person in <image1> to a red dress, keep the face and pose unchanged."
  ```
  В интерфейсе: `workflows/qwen21_nsfw_edit_local.json` (или `_server.json`), картинку выбрать в узле «Input image».

  До 16 картинок: `<image1>` редактируется (и задаёт размер результата), остальные служат образцами.
  ```
  python scripts/generate.py --image person.png --image dress.png -p "The person in <image1> wearing the dress from <image2>, keep the face from <image1>."
  ```
  В интерфейсе: `workflows/qwen21_nsfw_edit2_local.json`, вторая картинка в узле «Reference image 2».
- **Классический img2img**: картинка частично зашумляется и перерисовывается по промпту.
  `--denoise` задаёт силу: до ~0.6 почти ничего не меняется, 0.7–0.85 даёт заметные изменения с сохранением композиции.
  ```
  python scripts/generate.py --image in.png --denoise 0.75 -p "realistic photograph of ..."
  ```

Один и тот же вымышленный персонаж в разных сценах, без эффекта вклеенного лица: [docs/characters.md](docs/characters.md).

Не используйте фотографии реальных людей без их согласия: создание интимных изображений
реальных людей без согласия во многих странах уголовно наказуемо.

## Настройки (рекомендации автора LoRA)

- 25+ шагов (по умолчанию 30), CFG 3–6 (по умолчанию 4)
- сила LoRA 0.8–1.0 (по умолчанию 0.9)
- sampler **er_sde** (на euler результат плохой), scheduler **beta**
- триггер-слов нет; обучен в основном на откровенных сценах, лучше работают явные описания
- разрешение кратно 32; модель поддерживает до 2048×2048
