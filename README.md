# AdUltAi

ComfyUI + Qwen Image 2.1 + [NSFW LoRA v2 by TheseAlpacas](https://civitai.com/models/2958918) для картинок,
MiniMax H3 + [NSFW Unlocked LoRA v2](https://civitai.com/models/2925727) для видео со звуком (только сервер).
Модели в репозиторий не входят: их скачивает `setup` под выбранный профиль.

## Профили

| Профиль | Для чего | Модель / энкодер | Скачать |
|---|---|---|---|
| `local-16gb` | RTX 4060 Ti 16GB, 32GB RAM | int8 / int8 | ~17 ГБ |
| `server` | 48GB+ VRAM (A6000, L40S, A100, H100) | bf16 / bf16 (максимальное качество) | ~33 ГБ |
| `h3-server` | видео, 48GB+ VRAM | H3 pruned int8 / Qwen3-VL 32B int8 | ~54 ГБ |
| `h3-server-bf16` | видео, 80GB VRAM (A100 80GB, H100) | H3 pruned bf16 / bf16 (максимальное качество) | ~100 ГБ |

Профили можно ставить вместе: `./scripts/setup.sh server h3-server`.

## Установка

1. `cp .env.example .env` и вписать `CIVITAI_TOKEN` (civitai.com → Account → API Keys).
2. Windows: `.\scripts\setup.ps1 -Profile local-16gb`
   Linux: `./scripts/setup.sh server`

Нужны git, Python 3.13 (на Linux подойдёт python3 ≥ 3.10) и драйвер NVIDIA с поддержкой CUDA 13.

## Запуск

- Windows: `.\scripts\run.ps1` → http://127.0.0.1:8188
- Linux: `./scripts/run.sh`, затем с локального компа `ssh -L 8188:127.0.0.1:8188 user@server` и открыть http://127.0.0.1:8188.
  Не запускайте с `--listen 0.0.0.0` на публичном IP: у ComfyUI нет авторизации.

То же через npm (из корня проекта, аргументы после `--`):

```
npm run comfy                                   # ComfyUI, http://127.0.0.1:8188
npm run studio                                  # LoRA-студия, http://127.0.0.1:8190
npm run dataset -- datasets/auburn_freckles     # make_dataset.py
npm run sheet -- datasets/auburn_freckles/images sheet.jpg
npm run generate -- -p "..." --count 4
npm run video -- -p "..." --seconds 5
npm run train -- training/auburn_freckles.yaml  # только Windows, на Linux ./scripts/train_lora.sh
npm run api                                     # api/ в режиме разработки
```

Кожа без «пластика»: LoRA [Glamour Realism](https://civitai.com/models/2986100) (ставится с профилями
`local-16gb` и `server`) на 0.5–0.7, `--cfg 2.5`, размер около 1 Мп, в промпте `natural skin texture, visible pores`,
в негативе `airbrushed, plastic skin, glossy skin`:
```
npm run generate -- --cfg 2.5 --extra-lora qwen21_glamour_realism_v1.safetensors:0.6 -p "..." -n "airbrushed, plastic skin, glossy skin, ..."
```

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
  Размер результата — в узле «Size» (по умолчанию 832×1216): картинка обрезается по центру и масштабируется
  под него. Чтобы оставить пропорции исходника, впишите размер с теми же пропорциями.

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

## Видео: MiniMax H3

Text-to-video и image-to-video (первый и/или последний кадр), ролик со звуком, 24 fps,
1344×768 по умолчанию. Только профили `h3-server*`: на 16 ГБ видеопамяти модель не помещается.

```
python scripts/generate_video.py -p "..." --seconds 5
python scripts/generate_video.py --first-frame start.png -p "..." --seconds 8
python scripts/generate_video.py --profile server_bf16 --first-frame a.png --last-frame b.png -p "..."
python scripts/generate_video.py -p "..." --style 1.0   # рисованный стиль
```

В интерфейсе: `workflows/h3_nsfw_server.json` (или `_server_bf16.json`). Для image-to-video добавить узел
Load Image и подключить к `first_frame` / `last_frame` узла «Prompt». Видео сохраняются в `output/video/`.

Настройки (turbo LoRA + рекомендации автора NSFW LoRA):

- 8 шагов с turbo LoRA, CFG нет (BasicGuider), sampler **euler_ancestral**, scheduler simple
- сила NSFW LoRA 0.3–1, по умолчанию 0.5
- длина: модель обучена на ~5–15 с; кадры округляются до сетки 17k+5 (5 с = 124 кадра)
- в промпте одним текстом описывать сцену, движения камеры и звук (реплики, шумы, музыку)
- триггеры автора: `nude`, `topless`, `naked`, `disrobing`, `slipping off robe`, `caressing`, `intimate kissing`

Рисованный стиль: [Digital Art Style LoRA v3](https://civitai.com/models/2930448), включается флагом `--style`
(третий LoraLoaderModelOnly после NSFW LoRA, триггер `flat cel shading, bold outlines, multi colors`
дописывается в начало промпта сам). В интерфейсе: `workflows/h3_digital_art_server.json` (или `_server_bf16.json`),
триггер там уже стоит в начале промпта. Сила 0.8–1.5: 0.8 мягкий graphic novel, выше — жёстче контуры и контраст.
Совместимость с pruned-моделью и NSFW LoRA автор не проверял: при `lora key not loaded` в логе ComfyUI
стиль применился не полностью — тогда пробовать bf16-профиль.

Модель использует pruned-версию H3: в ней все слои, которые меняют обе LoRA, совпадают с полной.
На реальном GPU эта связка ещё не запускалась.

## HTTP API (картинки, видео, персонажи)

NestJS-сервис в `api/` поверх ComfyUI: принимает задание, ставит в очередь и отдаёт png/mp4.
Базы нет — id задания это `prompt_id` ComfyUI, статус берётся из его очереди и истории
(после перезапуска ComfyUI старые id пропадают). Персонажи хранятся файлами в `api/data/characters/`.

На сервере (после `setup.sh`, ComfyUI запущен):
```
./scripts/setup_api.sh      # Node 22, сборка, api/.env со случайным API_TOKEN
./scripts/run_api.sh        # слушает PORT из api/.env (8000)
```
В `api/.env` `COMFY_URL` должен совпадать с портом ComfyUI (`run.sh --port 8189` → `http://127.0.0.1:8189`),
`COMFY_PROFILE` — со скачанным видео-профилем (`server` или `server_bf16`), `COMFY_IMAGE_PROFILE` — с профилем
картинок (`server` или `local`). Для видео с персонажем нужны оба: `./scripts/setup.sh server h3-server`.

Наружу открывать только API, не ComfyUI. На vast.ai: в шаблоне `-p 8000:8000`
(внешний порт виден в «IP Port Info»), либо HTTPS-адрес без открытия портов: `cloudflared tunnel --url http://localhost:8000`.
Без HTTPS токен идёт открытым текстом.

| Запрос | Ответ |
|---|---|
| `POST /characters` (multipart: `portrait` + поля) | персонаж |
| `GET /characters`, `GET /characters/:id`, `GET /characters/:id/portrait` | список, персонаж, портрет |
| `PATCH /characters/:id` (JSON) | персонаж с изменёнными полями |
| `DELETE /characters/:id` | `204` |
| `POST /images` (JSON или multipart) | `202 {id, status, url, seed}` |
| `POST /videos` (multipart или JSON) | `202 {id, status, url, seed, frames}` |
| `GET /jobs/:id` | `{id, status: queued\|running\|done\|error, url?, error?}` |
| `GET /jobs/:id/file` | png или mp4 (`409`, пока не готово) |
| `GET /health` | без токена: API и ComfyUI живы |

### Персонажи

Персонаж — это портрет (как в [docs/characters.md](docs/characters.md): по колено, в одежде, ровный свет)
и, по желанию, обученные LoRA. Поля: `id` (латиница, его передают в `character`), `subject` (как назвать
персонажа в промпте, по умолчанию `the person`, лучше `the woman` / `the man`), `image_lora` (Qwen),
`video_lora` (H3), `trigger`, `strength` (сила LoRA персонажа, 1).

В промпте место персонажа отмечается `{character}`:
- **без LoRA** картинка рисуется в режиме edit с портретом: `{character}` → `the woman from <image1>`.
  Без `width`/`height` размер берётся с портрета;
- **с `image_lora`** — обычная генерация, LoRA персонажа подключается после NSFW LoRA, `{character}` → триггер;
- **видео**: если не передан `first_frame`, первый кадр с персонажем рисует Qwen в том же задании
  (размером с видео, по `frame_prompt`, по умолчанию по `prompt`), дальше H3 оживляет его.
  С `video_lora` LoRA персонажа подключается и в H3, `{character}` → триггер, иначе → `subject`.

Без `{character}` ссылка на персонажа дописывается в начало промпта (в видео без LoRA не дописывается).

### Режимы

`mode`: `nsfw` (по умолчанию, реалистично) или `anime`. В видео `anime` включает Digital Art LoRA
(сила `style`, по умолчанию 1); у Qwen аниме-LoRA нет, стиль задаётся текстом в начале промпта.
NSFW LoRA работает в обоих режимах, её сила — `lora`.

Поля `POST /images`: `prompt` (обязательно), `negative`, `character`, `mode`, `width`, `height`, `steps`, `cfg`,
`lora`, `seed` — как у `generate.py`. Поля `POST /videos`: `prompt` (обязательно), `character`, `frame_prompt`,
`mode`, `seconds`, `width`, `height`, `steps`, `lora`, `style`, `seed` — как у `generate_video.py`;
картинки `first_frame`, `last_frame` (png/jpeg/webp до 20 МБ).

```
curl -H "Authorization: Bearer $TOKEN" -F id=anna -F subject="the woman" -F portrait=@characters/anna.png https://<host>/characters
curl -H "Authorization: Bearer $TOKEN" -F character=anna -F mode=anime -F prompt="{character} reading on a sunlit balcony" https://<host>/images
curl -H "Authorization: Bearer $TOKEN" -F character=anna -F seconds=6 \
     -F frame_prompt="{character} standing by the window in a bedroom, soft morning light" \
     -F prompt="The woman turns to the camera and smiles, slow push-in, quiet room tone" https://<host>/videos
curl -H "Authorization: Bearer $TOKEN" https://<host>/jobs/<id>
curl -H "Authorization: Bearer $TOKEN" -o out.mp4 https://<host>/jobs/<id>/file
# после обучения LoRA
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"image_lora":"anna_v1.safetensors","trigger":"ohwx woman"}' https://<host>/characters/anna
```

Тесты: `cd api && npm test`.

## Обучение LoRA персонажа (ai-toolkit)

Стабильное лицо без `<image1>`: LoRA учится на 20–30 картинках персонажа и включается триггер-словом.
Подробности про персонажей: [docs/characters.md](docs/characters.md).

1. Установить тренер (один раз, ставит Python 3.12 через uv, ~8 ГБ):
   `.\scripts\setup_trainer.ps1` / `./scripts/setup_trainer.sh`
2. Датасет: папка `datasets/<имя>/` с `ref.png` (опорный портрет), `trigger.txt` (например `ohwx woman`)
   и `prompts.txt` (сцена на строку, персонаж = `the woman from <image1>`). В каждой сцене указывать одежду,
   иначе модель переносит одежду с портрета и LoRA выучит её как часть персонажа. ComfyUI должен быть запущен:
   ```
   python scripts/make_dataset.py datasets/auburn_freckles
   python scripts/contact_sheet.py datasets/auburn_freckles/images sheet.jpg   # просмотреть и удалить неудачные (png + txt)
   ```
3. Обучение (ComfyUI остановить — нужна вся видеопамять). Модели берутся из `ComfyUI/models`:
   ```
   .\scripts\train_lora.ps1 training\auburn_freckles.yaml
   ```
   Промежуточные LoRA и тестовые картинки каждые 250 шагов: `ai-toolkit/output/<name>/`.
4. Выбранный `.safetensors` скопировать в `ComfyUI/models/loras` и подключить вторым LoraLoaderModelOnly
   (или вместо NSFW LoRA). В промпте писать триггер: `photo of ohwx woman ...`.

То же в браузере:
```
python scripts/lora_studio.py        # http://127.0.0.1:8190
```
Имя персонажа, ключевое слово, загрузка фото, «Сгенерировать фото» (сцены из `training/character_prompts.txt`),
у каждого фото правка промпта и «Перегенерировать», «Начать обучение» / «Остановить» с прогрессом, логом и
тестовыми картинками. ComfyUI для генерации запускается сам и останавливается перед обучением; запущенный вручную
нужно закрыть. Настройки обучения — `training/character_template.yaml`. Остановленное обучение продолжается
с последнего сохранения, после законченного следующий запуск создаёт `<имя>_v2`. Итог копируется в
`ComfyUI/models/loras/<имя>_v1.safetensors`. Блок «Генерация с LoRA» проверяет обученную LoRA (или промежуточное
сохранение, оно само копируется в `ComfyUI/models/loras`): промпт с ключевым словом, без `<image1>`, картинки
кладутся в `datasets/<имя>/generated/`.

Только вымышленные персонажи, вы сами или взрослые, которые на это согласились.
