---
name: swap-prompt
description: Замена модели на фото персонажем с LoRA (Настия, nastiya_v3) на арендном сервере: пишет промпт, сам выбирает настройки LoRA и режим позы, запускает swap.py, скачивает и проверяет результат. Используй, когда пользователь присылает фото (одно или пачку) и просит промпт, замену модели, «сделай так же», «прогони эти», «сгенерируй по этим фото».
---

# Замена модели на фото персонажем (Qwen Image 2.1, сервер)

Персонаж по умолчанию: Настия, триггер `nst woman`, LoRA `nastiya_v3.safetensors`, фигура из `datasets/nastiya/body.txt`.
Пользователь ничего не подбирает вручную: настройки, промпт, запуск и проверку делаешь сам.
Если человек на фото выглядит несовершеннолетним, ничего не делай.

## Окружение

- ComfyUI работает на арендном сервере vast, у пользователя открыт SSH-туннель `-L 8189:localhost:8188`, поэтому `--host http://127.0.0.1:8189`.
- Проверка перед запуском: `curl -s -m 5 http://127.0.0.1:8189/system_stats`. Не отвечает: попроси переподключить туннель (`ssh -p <порт> root@<host> -L 8080:localhost:8080 -L 8189:localhost:8188`) и проверить `tmux attach -t comfy` на сервере.
- На сервере нужны LoRA: `nastiya_v3`, `nsfw_qwen21_thesealpacas_v2`, `krea2_film_texture_qwen21`, `qwen21_anatomy_v2` и апскейлер `4x-UltraSharpV2` в `upscale_models`. Нет файла: скачай на сервере через `ssh` + `wget` (токен Civitai в `/workspace/video-image-ai/.env`), не загружай с локальной машины: отсюда отдача очень медленная.
- Флоу: `workflows/qwen21_character_swap_server.json` (обычный) и `qwen21_character_swap_server_pose.json` (поза с фото, denoise 0.85). Для UI пользователя; скрипт берёт обычный и включает позу флагом.

## Цепочка LoRA во флоу (порядок не важен, важны силы)

| Узел | LoRA | Сила |
|---|---|---|
| NSFW LoRA | nsfw_qwen21_thesealpacas_v2 | 0 одета/бельё, 0.8 топлес и ню |
| Character LoRA | nastiya_v3 | 1.0 всегда (1.2 ничего не даёт) |
| Skin realism | krea2_film_texture_qwen21 | 0.5 всегда (убирает пластиковую кожу) |
| Anatomy LoRA | qwen21_anatomy_v2 | 0.8 только если видны гениталии, иначе 0 |

- Без Anatomy LoRA Qwen рисует гениталии уродливо (распухшие, бесформенные). 1.0 не лучше 0.8, а лицо хуже.
- NSFW 1.0 + Anatomy вместе сильно портят лицо: держи NSFW 0.8.
- Дублировать LoRA = поднять силу; две копии по 0.8 = 1.6, это перебор.
- Референсы лица и фигуры (`<image2>`, `<image3>`) не подавай: с v3 похожесть от них не растёт, а портрет тащит свой ракурс и свет.
- `qwen21_glamour_realism` не использовать: делает кожу гладкой.

## Настройки по кадру

| Кадр | `--nsfw` | `--anatomy` | Добавки |
|---|---|---|---|
| одета, бельё, купальник | 0 | 0 | COVER в промпт, NEG_COVER в негатив |
| топлес, ню, гениталии не видны | 0.8 | 0 | |
| видны гениталии | 0.8 | 0.8 | назвать в промпте, что видно |

Режим позы `--keep-pose 0.85` (генерация стартует с латента фото, руки и ноги совпадают точно) включай, если поза сложная: лёжа, ноги подняты или скрещены, съёмка сверху, руки за головой или закрывают лицо, необычный ракурс. Для простых поз (стоит, сидит фронтально) не нужен.
- 0.75 уже мало: проступает исходная модель (её волосы, лицо). Если на 0.85 проступает, подними до 0.9.
- При 0.85 модель иногда меняет мелкое: руки могут открыть лицо. Это описывай явно.

## Промпт

```
Replace the woman in <image1> with nst woman: <body.txt>. Keep everything else exactly as in <image1>: the same pose, body position, head position and angle, gaze direction and facial expression, the same clothing and accessories (or the same nudity), the same framing, camera angle, background and lighting. <ДОПОЛНЕНИЕ> Natural realistic skin texture with visible pores, fine skin details, slight imperfections, matte skin, candid amateur photo.
```

`<ДОПОЛНЕНИЕ>` — 1–3 предложения только о том, что модель сама не удержит:
1. **Состояние одежды, если она снята, спущена или сдвинута.** Фраза «same clothing» тут не работает: модель «одевает» обратно. Пиши конкретно и где именно вещь: `her lilac lace bra is pulled down below her breasts, both breasts and nipples fully exposed`, `her panties are already pulled down below her buttocks onto the backs of her thighs, rolled into a thin band held by her hands; her bare buttocks are fully exposed`. Полностью раздета: `She is completely naked`.
2. **Руки и ноги в необычном положении**: за головой, на окне, в трусиках, между ног, на груди, закрывают лицо; нога согнута, скрещена, на подлокотнике. Иначе на части seed они опускаются.
3. **Выражение лица, если оно особенное** (открытый рот, закрытые глаза, язык, улыбка, взгляд вниз): общая фраза выражение теряет чаще всего.
4. **Что видно из интимного**, если Anatomy 0.8: `her vulva and labia are visible between her spread thighs`.

COVER (одета в бельё, грудь должна быть закрыта): перед описанием добавь `Her breasts are fully covered by the bra: lined lace bra cups, nothing exposed.` Слово `sheer` не используй.

Нельзя: описывать лицо, волосы, глаза (их даёт LoRA); писать `keep her face`, `same face`. Фигуру бери дословно из `body.txt`.

## Негатив

```
plastic skin, smooth skin, airbrushed, waxy skin, glossy skin, oily skin, retouched, cgi, 3d render, skinny, emaciated, visible ribs, fake breasts, implants, perfectly round breasts, blurry, lowres, deformed anatomy, extra fingers, watermark, text
```
- NEG_COVER (одета в бельё) — в начало: `exposed breasts, nipples, areola, topless, bra pulled down, see-through bra, `
- Видны гениталии (Anatomy 0.8) — в начало: `penis, male genitalia, protruding labia, swollen genitals, malformed genitals, ` (без этого на части seed бывает выпирающий нарост).
- Если вещь спущена, а модель её «надевает» — в начало запрет на надетое состояние: `fabric covering buttocks, panties worn, panties on hips, ` / `bra covering breasts, `.

## Запуск

```
python scripts/swap.py --server --lora-only --host http://127.0.0.1:8189 --image "<фото>" --nsfw <0|0.8> --anatomy <0|0.8> [--keep-pose 0.85] --count 2 --tag <кадр> --out output/<папка> -p "<Prompt>" -n "<Негатив>"
```
- `--out` ждёт задания и скачивает картинки с сервера; без него файлы остаются только на сервере.
- `--size 1mp` по умолчанию (быстро, для проверки). `2k`, `4k` или `all` — финальные кадры, когда пользователь попросит (апскейл 4x-UltraSharpV2, пропорции сохраняются).
- Пачку фото запускай подряд в одном цикле; на каждое 2 seed.

## Проверка результата (обязательно)

1. Склей ряд: исходное фото + оба варианта (PIL, высота ~600), посмотри его сам.
2. Сравни с оригиналом: поза рук и ног, состояние одежды (что снято, спущено, видно), выражение лица, кадрирование, фон. Лицо должно быть Настии: короткая тёмная стрижка, оливковая кожа.
3. Похожесть лица (по желанию): `face_score.py` в scratchpad (YuNet + SFace к `datasets/nastiya/refs/nastiya_01.png`). Ориентиры: 0.55–0.76 хорошо; при лице меньше ~100 px, опущенном или закрытом лице метрика ненадёжна.
4. Нашёл расхождение — допиши `<ДОПОЛНЕНИЕ>` про конкретную ошибку (или включи `--keep-pose`) и перезапусти только этот кадр. Если подробное описание сделало хуже (бывает на сложных ракурсах сверху), оставь лучший из предыдущих вариантов.
5. Сложи итог в `output/<папка>` (картинки + ряды сравнения), открой папку пользователю и коротко отчитайся таблицей: кадр, настройки, что вышло, что поправлял.

## Известные особенности

- Фигура выходит немного полнее, чем у худых исходных моделей: так действует `body.txt`.
- С Anatomy LoRA кожа светлеет; если важно, допиши `olive skin, tanned skin`.
- Детейлер лица (кроп → перерисовка 1024 с denoise 0.85 → вклейка) даёт +0.04–0.07 к похожести; делается отдельным скриптом, по запросу.
