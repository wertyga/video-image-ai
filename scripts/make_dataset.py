"""Собирает датасет для LoRA персонажа: каждая сцена из prompts.txt генерируется в режиме edit
из опорной картинки, рядом сохраняется подпись .txt для ai-toolkit.

  python scripts/make_dataset.py datasets/auburn_freckles

В папке датасета нужны:
  ref.png      - опорный портрет персонажа
  prompts.txt  - по сцене на строку, персонаж называется "the woman from <image1>" (или man/person)
  trigger.txt  - триггер-слово, например "ohwx woman"
Картинки и подписи кладутся в <папка>/images/. Уже готовые сцены пропускаются.
"""
import argparse
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from generate import ROOT, add_edit, post, upload_image

SUBJECT = re.compile(r"the (woman|man|person) from <image1>", re.IGNORECASE)


def wait_image(host, prompt_id):
    while True:
        time.sleep(2)
        with urllib.request.urlopen(f"{host}/history/{prompt_id}") as resp:
            history = json.load(resp).get(prompt_id)
        if not history:
            continue
        if history.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(history["status"].get("messages"), ensure_ascii=False)[:2000])
        for output in history.get("outputs", {}).values():
            for image in output.get("images", []):
                query = urllib.parse.urlencode({k: image[k] for k in ("filename", "subfolder", "type")})
                with urllib.request.urlopen(f"{host}/view?{query}") as resp:
                    return resp.read()
        raise RuntimeError("в ответе нет картинки")


def main():
    # консоль Windows может быть не в UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--profile", default="local", choices=["local", "server"])
    parser.add_argument("--lora", type=float, default=0.0, help="NSFW LoRA при сборке датасета, по умолчанию выключен")
    parser.add_argument("--host", default="http://127.0.0.1:8188")
    args = parser.parse_args()

    trigger = (args.dataset / "trigger.txt").read_text(encoding="utf-8").strip()
    prompts = [p.strip() for p in (args.dataset / "prompts.txt").read_text(encoding="utf-8").splitlines() if p.strip()]
    out = args.dataset / "images"
    out.mkdir(exist_ok=True)
    ref_name = upload_image(args.host, args.dataset / "ref.png")

    for i, prompt in enumerate(prompts, 1):
        image_path = out / f"{i:03d}.png"
        if image_path.exists():
            continue
        if not SUBJECT.search(prompt):
            sys.exit(f"строка {i}: нет 'the woman from <image1>': {prompt}")
        workflow = json.loads((ROOT / "workflows" / f"qwen21_nsfw_{args.profile}.json").read_text(encoding="utf-8"))
        workflow["5"]["inputs"]["prompt"] = prompt
        workflow["2"]["inputs"]["strength_model"] = args.lora
        workflow["7"]["inputs"]["seed"] = random.randrange(2**48)
        add_edit(workflow, [ref_name])
        image_path.write_bytes(wait_image(args.host, post(f"{args.host}/prompt", {"prompt": workflow})["prompt_id"]))
        caption = SUBJECT.sub(trigger, prompt).replace("<image1>", "").strip()
        image_path.with_suffix(".txt").write_text(caption, encoding="utf-8")
        print(f"{i}/{len(prompts)} {image_path.name}")
    print("Готово:", out)


if __name__ == "__main__":
    main()
