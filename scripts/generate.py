"""Генерация без браузера: отправляет workflow в запущенный ComfyUI.

Пример:
  python scripts/generate.py --profile server -p "photo of ..." --count 4 --width 832 --height 1216
Картинки сохраняются в output/.
"""
import argparse
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def main():
    # консоль Windows может быть не в UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="local", choices=["local", "server"])
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("-n", "--negative")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, help="по умолчанию случайный")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--cfg", type=float)
    parser.add_argument("--lora", type=float, help="сила LoRA, автор советует 0.8-1.0")
    parser.add_argument("--host", default="http://127.0.0.1:8188")
    args = parser.parse_args()

    workflow = json.loads((ROOT / "workflows" / f"qwen21_nsfw_{args.profile}.json").read_text(encoding="utf-8"))
    workflow["5"]["inputs"]["prompt"] = args.prompt
    if args.negative is not None:
        workflow["5"]["inputs"]["negative_prompt"] = args.negative
    workflow["6"]["inputs"].update(width=args.width, height=args.height)
    sampler = workflow["7"]["inputs"]
    if args.steps:
        sampler["steps"] = args.steps
    if args.cfg is not None:
        sampler["cfg"] = args.cfg
    if args.lora is not None:
        workflow["2"]["inputs"]["strength_model"] = args.lora

    seed = args.seed if args.seed is not None else random.randrange(2**48)
    ids = []
    for i in range(args.count):
        sampler["seed"] = seed + i
        ids.append(post(f"{args.host}/prompt", {"prompt": workflow})["prompt_id"])
        print(f"в очереди: seed={seed + i}")

    pending = set(ids)
    while pending:
        time.sleep(2)
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
                for image in output.get("images", []):
                    print("готово:", ROOT / "output" / image.get("subfolder", "") / image["filename"])


if __name__ == "__main__":
    main()
