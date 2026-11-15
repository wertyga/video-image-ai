"""Генерация на SD 1.5 чекпойнте (LazyMix+) через запущенный ComfyUI, с hires fix.

  python scripts/generate_sd15.py -p "amateur photo of a 28 year old woman ..." --count 4
  python scripts/generate_sd15.py -p "..." --hires 0                      # без hires fix, 512x768
  python scripts/generate_sd15.py -p "..." --lora my_sd15_lora.safetensors:0.8
Промпт оборачивается тегами любительского стиля автора (STYLE), отключается --no-style.
SD 1.5 рисует в ~512x768, hires fix доводит до x1.5 (768x1152). LoRA нужны именно под SD 1.5.
Миксы на SD 1.5 тянут лица в юность: пишите возраст явно ("28 year old woman"), в негативе по умолчанию
стоит защита (child, teen, ...). Если задаёте свой -n, оставьте эти слова.
  python scripts/generate_sd15.py -p "photo of nst woman ..." --lora nastiya_sd15.safetensors:0.9 --face
--face перерисовывает кроп лица в 512x512 с той же LoRA и вклеивает (как ADetailer), похожесть заметно выше.
Картинки сохраняются в output/.
"""
import argparse
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

from generate import post

ROOT = Path(__file__).resolve().parent.parent
# стиль из примеров автора модели: без него LazyMix уходит в глянцевую студийную картинку
STYLE = ("analog style, instagram photo, RAW, real life photo, r/nude_selfie, reddit, "
         "medium quality, normal aesthetic, shot on iPhone, film grain")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("-n", "--negative")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, help="по умолчанию случайный")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--cfg", type=float)
    parser.add_argument("--hires", type=float, default=1.5, help="масштаб hires fix, 0 - выключить")
    parser.add_argument("--hires-denoise", type=float, default=0.4)
    parser.add_argument("--sampler", help="dpmpp_sde (по умолчанию) или dpmpp_2m_sde, оба с karras")
    parser.add_argument("--no-style", action="store_true", help="не добавлять теги любительского стиля автора")
    parser.add_argument("--lora", action="append", default=[], metavar="FILE[:STRENGTH]",
                        help="LoRA под SD 1.5 из ComfyUI/models/loras, можно несколько раз")
    parser.add_argument("--face", action="store_true",
                        help="доработать лицо: перерисовать кроп 512x512 с той же LoRA (как ADetailer)")
    parser.add_argument("--face-denoise", type=float, default=0.45,
                        help="сила перерисовки лица: 0.35 - бережно, 0.55 - сильнее к LoRA")
    parser.add_argument("--host", default="http://127.0.0.1:8188")
    args = parser.parse_args()

    wf = json.loads((ROOT / "workflows" / "lazymix_local.json").read_text(encoding="utf-8"))
    wf["3"]["inputs"]["text"] = args.prompt if args.no_style else f"amateur, {args.prompt}, {STYLE}"
    if args.negative is not None:
        wf["4"]["inputs"]["text"] = args.negative
    wf["5"]["inputs"].update(width=args.width, height=args.height)
    base, hires = wf["6"]["inputs"], wf["8"]["inputs"]
    if args.steps:
        base["steps"] = args.steps
    if args.cfg is not None:
        base["cfg"] = hires["cfg"] = args.cfg
    if args.sampler:
        base["sampler_name"] = hires["sampler_name"] = args.sampler

    model, clip = ["1", 0], ["1", 1]
    for i, spec in enumerate(args.lora):
        name, _, strength = spec.partition(":")
        node_id = str(30 + i)
        s = float(strength or 1.0)
        wf[node_id] = {"class_type": "LoraLoader", "_meta": {"title": f"LoRA {i + 1}"},
                       "inputs": {"model": model, "clip": clip, "lora_name": name,
                                  "strength_model": s, "strength_clip": s}}
        model, clip = [node_id, 0], [node_id, 1]
    base["model"] = hires["model"] = model
    wf["3"]["inputs"]["clip"] = wf["4"]["inputs"]["clip"] = clip

    if args.hires:
        wf["7"]["inputs"]["scale_by"] = args.hires
        hires["denoise"] = args.hires_denoise
    else:
        wf["9"]["inputs"]["samples"] = ["6", 0]
        del wf["7"], wf["8"]

    seed = args.seed if args.seed is not None else random.randrange(2**48)
    ids = {}
    for i in range(args.count):
        base["seed"] = seed + i
        if "8" in wf:
            hires["seed"] = seed + i
        ids[post(f"{args.host}/prompt", {"prompt": wf})["prompt_id"]] = seed + i
        print(f"в очереди: seed={seed + i}")

    pending = set(ids)
    while pending:
        time.sleep(1)
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
                    path = ROOT / "output" / image.get("subfolder", "") / image["filename"]
                    if args.face:
                        from face_fix import fix_face
                        face_prompt = "close-up photo of the face, detailed face, " + wf["3"]["inputs"]["text"]
                        fixed = fix_face(args.host, wf, path, face_prompt, ids[prompt_id], args.face_denoise)
                        if fixed:
                            print("  без доработки:", path)
                            path = fixed
                    print("готово:", path)


if __name__ == "__main__":
    main()
