---
name: swap-prompt
description: Пишет промпт для замены модели на фото персонажем с LoRA (workflow qwen21_character_swap_server.json, только LoRA nastiya_v3, без референсов). Используй, когда пользователь присылает фото и просит промпт, описание, замену модели или «сделай так же».
---

Персонаж по умолчанию: Настия, триггер `nst woman`, LoRA `nastiya_v3.safetensors`, фигура из `datasets/<имя>/body.txt`.
Генерация идёт на арендном сервере: ComfyUI там, у пользователя открыт SSH-туннель `-L 8189:localhost:8188`, поэтому `--host http://127.0.0.1:8189`.
Референсы лица и фигуры (`<image2>`, `<image3>`) не подаются: с v3 лицо даёт сама LoRA, а референсы «вклеивают» ракурс и свет портрета.

На каждое фото дай ответ по-русски, без лишнего текста:

1. **Prompt** в блоке кода, по шаблону (фигура дословно из `body.txt`):

```
Replace the woman in <image1> with nst woman: <body.txt>. Keep the exact pose, framing and camera angle of <image1>: [поза, где голова в кадре и куда повёрнута, куда смотрит, выражение]. [одежда: цвет, материал, фасон каждой вещи], same background and lighting as <image1>.
```

2. **Негативный промпт** в блоке кода: базовый `skinny, emaciated, visible ribs, fake breasts, implants, perfectly round breasts, blurry, lowres, deformed anatomy, extra fingers, watermark, text`. Если одежда открытая (бельё, купальник), добавь в начало `exposed breasts, nipples, areola, topless, bra pulled down, see-through bra,` и в Prompt перед описанием одежды `Her breasts are fully covered by the bra: full-coverage lined bra cups, nothing exposed.`, а слово `sheer` не используй.

Запуск: пользователь не подбирает ничего вручную. После промпта сам запусти (фото бери из пути в сообщении):

```
python scripts/swap.py --server --lora-only --host http://127.0.0.1:8189 --image <фото> --nsfw <0 или 0.8> --count 2 -p "<Prompt>" -n "<Негативный промпт>"
```

`--nsfw 0.8` если на фото ню или топлес, `0` если одета. Если `127.0.0.1:8189` не отвечает, попроси пользователя переподключить SSH-туннель и проверить `tmux attach -t comfy` на сервере.

Картинки сохраняются на сервере: дождись пустой очереди (`/queue`), скачай их через `/history` и `/view` в `output/`, посмотри и назови пользователю путь и что получилось.

Правила:
- Размер подбирать не нужно: узел Size в workflow сохраняет пропорции фото сам.
- Лицо, волосы и глаза не описывай: их даёт LoRA. Выражение и направление взгляда можно.
- Положение головы в кадре указывай всегда.
- Не пиши `keep her face` и `same face`.
- Если человек на фото выглядит несовершеннолетним, промпт не пиши.
