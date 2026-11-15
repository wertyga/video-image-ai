"""Замена модели на фото персонажем с LoRA: workflow qwen21_character_swap_local.json через запущенный ComfyUI.
Модель копирует ракурс головы с портрета, поэтому портрет выбирается под сцену (--face), размер берётся с фото.

  python scripts/swap.py --image scene.jpg --face right --count 2 -p "Replace the woman in <image1> ..." -n "..."
С --lora-only портрет и фигура не подаются, лицо даёт только LoRA, фигура задаётся текстом.
"""
import argparse
import json
import random
import sys
from pathlib import Path

from generate import ROOT, post, upload_image

FACES = ["front", "left", "right", "profile_left", "profile_right"]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, type=Path, help="фото сцены")
    parser.add_argument("--face", choices=FACES, help="куда смотрит лицо на сцене, от зрителя")
    parser.add_argument("--lora-only", action="store_true", help="без портрета и референса фигуры")
    parser.add_argument("--character", default="nastiya")
    parser.add_argument("--body", default="nastiya_body_03.png")
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("-n", "--negative")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, help="по умолчанию случайный")
    parser.add_argument("--host", default="http://127.0.0.1:8188")
    parser.add_argument("--server", action="store_true",
                        help="bf16-флоу qwen21_character_swap_server.json (ComfyUI на сервере, через туннель --host)")
    parser.add_argument("--lora", help="LoRA персонажа вместо указанной во флоу, например nastiya_v3_000002500.safetensors")
    parser.add_argument("--nsfw", type=float, help="сила NSFW LoRA (по умолчанию 0)")
    parser.add_argument("--keep-pose", type=float, metavar="DENOISE",
                        help="начать с латента фото (img2img): руки и ноги как на фото. 0.85; 0.9 если проступает исходная модель")
    parser.add_argument("--anatomy", type=float, help="сила Anatomy LoRA (серверный флоу, по умолчанию 0; 0.8 если видны гениталии)")
    args = parser.parse_args()
    if not args.lora_only and args.face is None:
        parser.error("нужен --face или --lora-only")

    dataset = ROOT / "datasets" / args.character
    workflow = json.loads((ROOT / "workflows" / f"qwen21_character_swap_{'server' if args.server else 'local'}.json").read_text(encoding="utf-8"))
    workflow["20"]["inputs"]["image"] = upload_image(args.host, args.image)
    if args.server and not args.lora_only:
        parser.error("серверный флоу без референсов: используйте --lora-only")
    if args.lora_only:
        for node in ("21", "22", "23", "24"):
            workflow.pop(node, None)
        workflow["5"]["inputs"].pop("images.image_2", None)
        workflow["5"]["inputs"].pop("images.image_3", None)
    else:
        workflow["21"]["inputs"]["image"] = upload_image(args.host, dataset / "faces" / f"{args.face}.png")
        workflow["23"]["inputs"]["image"] = upload_image(args.host, dataset / "body" / args.body)
    if args.lora:
        workflow["30"]["inputs"]["lora_name"] = args.lora
    if args.keep_pose:
        workflow["12"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["6", 0], "vae": ["4", 0]}}
        workflow["7"]["inputs"].update(latent_image=["12", 0], denoise=args.keep_pose)
    if args.anatomy is not None:
        workflow["32"]["inputs"]["strength_model"] = args.anatomy
    if args.nsfw is not None:
        workflow["2"]["inputs"]["strength_model"] = args.nsfw
    workflow["5"]["inputs"]["prompt"] = args.prompt
    if args.negative is not None:
        workflow["5"]["inputs"]["negative_prompt"] = args.negative
    seed = args.seed if args.seed is not None else random.randrange(2**48)
    for i in range(args.count):
        workflow["7"]["inputs"]["seed"] = seed + i
        post(f"{args.host}/prompt", {"prompt": workflow})
        print(f"в очереди: seed={seed + i}")


if __name__ == "__main__":
    main()
