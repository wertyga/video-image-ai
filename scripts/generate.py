"""Генерация без браузера: отправляет workflow в запущенный ComfyUI.

Текст в картинку:
  python scripts/generate.py -p "photo of ..." --count 4 --width 832 --height 1216
Редактирование (модель видит картинку и выполняет инструкцию, <image1> = исходная):
  python scripts/generate.py --image in.png -p "Change the outfit of the person in <image1> to a red dress, keep the face and pose"
Несколько картинок: <image1> редактируется, остальные - референсы:
  python scripts/generate.py --image person.png --image dress.png -p "The person in <image1> wearing the dress from <image2>"
Классический img2img (перерисовка с силой --denoise, 0.3 - лёгкая, 0.8 - сильная):
  python scripts/generate.py --image in.png --denoise 0.6 -p "photo of ..."
Картинки сохраняются в output/.
"""
import argparse
import json
import mimetypes
import random
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEGAPIXEL = 1024 * 1024


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def upload_image(host, path):
    boundary = uuid.uuid4().hex
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        path.read_bytes(),
        f"\r\n--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue',
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(f"{host}/upload/image", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req) as resp:
        result = json.load(resp)
    return f"{result['subfolder']}/{result['name']}" if result.get("subfolder") else result["name"]


def add_edit(workflow, image_names):
    """Картинки идут в текстовый энкодер как <image1>, <image2>, ...; латент берётся размера первой."""
    workflow["5"]["inputs"]["vae"] = ["4", 0]
    for i, image_name in enumerate(image_names, 1):
        node_id = str(19 + i)  # 20, 21, ...
        title = "Input image" if i == 1 else f"Reference image {i}"
        workflow[node_id] = {"class_type": "LoadImage", "_meta": {"title": title}, "inputs": {"image": image_name}}
        workflow["5"]["inputs"][f"images.image_{i}"] = [node_id, 0]
    workflow["7"]["inputs"]["latent_image"] = ["5", 2]
    del workflow["6"]


def add_img2img(workflow, image_name, denoise):
    """Картинка приводится к ~1 Мп и кодируется в латент, который частично перерисовывается."""
    workflow["10"] = {"class_type": "LoadImage", "_meta": {"title": "Input image"}, "inputs": {"image": image_name}}
    workflow["11"] = {"class_type": "ImageScaleToTotalPixels",
                      "inputs": {"image": ["10", 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 32}}
    workflow["12"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["11", 0], "vae": ["4", 0]}}
    workflow["7"]["inputs"].update(latent_image=["12", 0], denoise=denoise)
    del workflow["6"]


def main():
    # консоль Windows может быть не в UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="local", choices=["local", "server"])
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("-n", "--negative")
    parser.add_argument("--image", type=Path, action="append",
                        help="картинка для режима edit; можно несколько раз (<image1>, <image2>, ...); с --denoise - img2img")
    parser.add_argument("--denoise", type=float, help="сила перерисовки для img2img, 0..1")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, help="по умолчанию случайный")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--cfg", type=float)
    parser.add_argument("--lora", type=float, help="сила LoRA, автор советует 0.8-1.0")
    parser.add_argument("--host", default="http://127.0.0.1:8188")
    args = parser.parse_args()
    if args.denoise is not None and not args.image:
        parser.error("--denoise работает только вместе с --image")
    if args.denoise is not None and len(args.image) > 1:
        parser.error("img2img (--denoise) принимает одну картинку, несколько - только в режиме edit")
    if args.image and len(args.image) > 16:
        parser.error("не больше 16 картинок")

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
    if args.image:
        image_names = [upload_image(args.host, path) for path in args.image]
        if args.denoise is None:
            add_edit(workflow, image_names)
        else:
            add_img2img(workflow, image_names[0], args.denoise)

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
