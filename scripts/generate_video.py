"""Видео MiniMax H3 (со звуком) через запущенный ComfyUI.

Текст в видео:
  python scripts/generate_video.py -p "..." --seconds 5
Из картинки (первый кадр), можно добавить и последний:
  python scripts/generate_video.py --first-frame start.png [--last-frame end.png] -p "..."
Рисованный стиль (Digital Art LoRA): добавить --style 1.0
Видео сохраняются в output/video/.
"""
import argparse
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

from generate import ROOT, post, upload_image

FPS = 24
STYLE_LORA = "minimax_h3_digital_art_v3.safetensors"
STYLE_TRIGGER = "flat cel shading, bold outlines, multi colors"


def frames_for(seconds):
    """Модель принимает длину 17k+5 кадров: округляем вверх, как официальный шаблон."""
    n = max(5, round(seconds * FPS))
    return n + (5 - n % 17) % 17


def main():
    # консоль Windows может быть не в UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="server", choices=["server", "server_bf16"])
    parser.add_argument("-p", "--prompt", required=True, help="сцена, движение камеры и звук одним текстом")
    parser.add_argument("--first-frame", type=Path)
    parser.add_argument("--last-frame", type=Path)
    parser.add_argument("--seconds", type=float, default=5, help="обучено на ~5-15 с")
    parser.add_argument("--width", type=int, default=1344)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--steps", type=int, help="8 с turbo LoRA")
    parser.add_argument("--lora", type=float, help="сила NSFW LoRA, автор советует 0.3-1, начинать с 0.5")
    parser.add_argument("--style", type=float, metavar="STRENGTH",
                        help="рисованный стиль Digital Art LoRA, автор советует 0.8-1.5, база 1.0")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, help="по умолчанию случайный")
    parser.add_argument("--host", default="http://127.0.0.1:8188")
    args = parser.parse_args()

    workflow = json.loads((ROOT / "workflows" / f"h3_nsfw_{args.profile}.json").read_text(encoding="utf-8"))
    video = workflow["7"]["inputs"]
    prompt = args.prompt
    if args.style is not None:
        workflow["17"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["3", 0], "lora_name": STYLE_LORA, "strength_model": args.style}}
        workflow["10"]["inputs"]["model"] = workflow["11"]["inputs"]["model"] = ["17", 0]
        prompt = f"{STYLE_TRIGGER}. {prompt}"
    video.update(prompt=prompt, width=args.width, height=args.height, length=frames_for(args.seconds))
    if args.steps:
        workflow["10"]["inputs"]["steps"] = args.steps
    if args.lora is not None:
        workflow["3"]["inputs"]["strength_model"] = args.lora
    for key, node_id, path in (("first_frame", "20", args.first_frame), ("last_frame", "21", args.last_frame)):
        if path:
            workflow[node_id] = {"class_type": "LoadImage", "inputs": {"image": upload_image(args.host, path)}}
            video[key] = [node_id, 0]

    seed = args.seed if args.seed is not None else random.randrange(2**48)
    pending = set()
    for i in range(args.count):
        workflow["8"]["inputs"]["noise_seed"] = seed + i
        pending.add(post(f"{args.host}/prompt", {"prompt": workflow})["prompt_id"])
        print(f"в очереди: seed={seed + i}, кадров={video['length']}")

    while pending:
        time.sleep(5)
        for prompt_id in list(pending):
            with urllib.request.urlopen(f"{args.host}/history/{prompt_id}") as resp:
                history = json.load(resp).get(prompt_id)
            if not history:
                continue
            pending.discard(prompt_id)
            status = history.get("status", {})
            if status.get("status_str") == "error":
                print("ошибка:", json.dumps(status.get("messages"), ensure_ascii=False)[:2000])
            for output in history.get("outputs", {}).values():
                for items in output.values():
                    for item in items if isinstance(items, list) else []:
                        if isinstance(item, dict) and "filename" in item:
                            print("готово:", ROOT / "output" / item.get("subfolder", "") / item["filename"])


if __name__ == "__main__":
    main()
