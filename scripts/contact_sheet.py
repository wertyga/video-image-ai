"""Сводный лист превью картинок из папки (для отбора датасета).

  python scripts/contact_sheet.py datasets/auburn_freckles/images sheet.jpg
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

THUMB = 256
COLS = 6


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    files = sorted(src.glob("*.png"))
    rows = (len(files) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * THUMB, rows * THUMB), "white")
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(files):
        img = Image.open(path).convert("RGB")
        img.thumbnail((THUMB, THUMB))
        x, y = (i % COLS) * THUMB, (i // COLS) * THUMB
        sheet.paste(img, (x + (THUMB - img.width) // 2, y + (THUMB - img.height) // 2))
        draw.rectangle([x, y, x + 34, y + 18], fill="black")
        draw.text((x + 4, y + 3), path.stem, fill="white")
    sheet.save(dst, quality=90)


if __name__ == "__main__":
    main()
