# Постоянный персонаж в разных сценах

Как сделать одного и того же вымышленного человека в разных сценах так, чтобы лицо
не выглядело вклеенным. Используется режим редактирования (`--image`), см. README.

Только вымышленные персонажи, ваши собственные фото или фото взрослых, которые явно
согласились. Фото реальных людей (знаменитостей, знакомых) для NSFW не использовать.

## 1. Опорный портрет

Генерируется без LoRA, в одежде, при ровном свете, по колено или в полный рост,
лицо хорошо видно. Внешность описывается конкретно: волосы, глаза, кожа, телосложение.

```
python scripts/generate.py --lora 0 --seed 501 --count 2 --width 832 --height 1216 -p "Realistic photograph of a fictional woman in her late twenties standing in a softly lit studio, framed from the knees up. She has shoulder-length wavy auburn hair, light freckles across her nose and cheeks, green-hazel eyes, a slightly crooked friendly smile, and a slim athletic build. She wears a plain grey t-shirt and jeans. Even soft daylight from a large window on the left, neutral light-grey background, natural skin texture with visible pores, shot on a 50mm lens."
```

Лучший вариант сохранить в `characters/`, например `characters/auburn_freckles.png`.

## 2. Сцены с персонажем

```
python scripts/generate.py --image characters/auburn_freckles.png --count 2 -p "Realistic photograph of the woman from <image1>, nude, standing in a sunlit bedroom, full body, natural breasts and visible nipples, turned slightly toward the camera in a three-quarter view, relaxed confident pose with one hand in her hair, soft warm morning light from a window on the left casting gentle shadows across her body, white linen sheets on the bed behind her, natural skin texture, shallow depth of field."
```

Размер результата берётся с `<image1>`, поэтому вертикальный портрет даёт вертикальную сцену.

## Почему лицо «вклеивается» и как этого избежать

- **Не писать** `keep her face`, `same face`, `unchanged`: модель воспринимает это как
  команду скопировать пиксели вместе с исходным светом и ракурсом.
- **Ссылаться на человека целиком**: `the woman from <image1>`, а не `<image1>` посреди фразы.
- **Задавать новый ракурс, позу и выражение**: `three-quarter view`, `looking over her shoulder`,
  `one hand in her hair`, `laughing`. Иначе они переносятся с портрета.
- **Описывать свет на теле и лице**: `soft warm light from the left casting gentle shadows across her body`.
  Тогда модель переосвещает лицо под сцену.
- **Не брать крупный портрет** как опору для сцены в полный рост: лучше по колено или целиком.

## Если что-то не так

- **Лицо плывёт от сцены к сцене**: сделать второй портрет того же персонажа в другом ракурсе
  и передать оба: `--image a.png --image b.png -p "the woman from <image1> and <image2> ..."`.
- **Ошибки анатомии** (вытянутое тело, асимметрия): другой `--seed` или `--steps 40`.
- **Картинка пересвечена или «пластиковая»**: `--cfg 3`.
- **Мало NSFW**: описать сцену подробнее и явнее, сила LoRA `--lora 1.0`.

## Что проверено и не помогло

- Передавать картинки только в текстовый энкодер, без VAE-латентов: модель игнорирует промпт
  и повторяет исходник.
- Уменьшать референс (`resolution` у `TextEncodeQwenImage21` до 512/384): результат почти не меняется.
