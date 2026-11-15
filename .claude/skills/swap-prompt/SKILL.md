---
name: swap-prompt
description: Пишет промпт для замены модели на фото персонажем с LoRA (workflow qwen21_character_swap_local.json). Используй, когда пользователь присылает фото и просит промпт, описание, замену модели или «сделай так же».
---

Персонаж по умолчанию: Настия, триггер `nst woman`, фигура из `datasets/<имя>/body.txt`.

На каждое фото дай ответ по-русски, без лишнего текста:

1. **Prompt** в блоке кода, по шаблону:

```
Replace the woman in <image1> with nst woman. Use <image2> as a reference for her face and hair and <image3> only as a reference for her body shape: natural curvy figure, medium-full breasts, slim waist. Keep the exact pose, framing and camera angle of <image1>: [поза, где голова в кадре и куда повёрнута, куда смотрит]. [одежда: цвет, материал, фасон каждой вещи], same background and lighting as <image1>.
```

2. **Негативный промпт** в блоке кода: базовый `blurry, lowres, deformed anatomy, extra fingers, watermark, text`. Если одежда открытая (бельё, купальник), добавь в начало `exposed breasts, nipples, areola, topless, bra pulled down, see-through bra,` и в Prompt перед описанием одежды `Her breasts are fully covered by the bra: full-coverage lined bra cups, nothing exposed.`, а слово `sheer` не используй.

Запуск: пользователь не подбирает ничего вручную. После промпта сам запусти (ComfyUI должен быть запущен, фото бери из пути в сообщении или последнее в `ComfyUI/input`):

```
python scripts/swap.py --image <фото> --face <ракурс> --count 2 -p "<Prompt>" -n "<Негативный промпт>"
```

Дождись файлов `output/nastiya_swap_*.png`, посмотри их и назови пользователю путь и что получилось. Если голова не совпала со сценой, смени `--face` и запусти снова.

Правила:
- Модель копирует ракурс головы с портрета <image2>, запрет в тексте не помогает, поэтому портрет выбирается под сцену параметром `--face`: куда смотрит лицо на фото, от зрителя: `front`, `left`, `right`, `profile_left`, `profile_right`. Выбирай сам, не спрашивай пользователя.
- Размер подбирать не нужно: узел Size в workflow сохраняет пропорции фото сам.
- Лицо, волосы и глаза не описывай: их даёт LoRA. Выражение и направление взгляда можно.
- Положение головы в кадре указывай всегда, иначе голова копируется с портрета.
- Не пиши `keep her face` и `same face`.
- Если человек на фото выглядит несовершеннолетним, промпт не пиши.
