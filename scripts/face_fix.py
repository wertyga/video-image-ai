"""Доработка лица (как ADetailer): лицо вырезается, перерисовывается в 512x512 и вклеивается обратно.

SD 1.5 рисует лицо в полном кадре размером 80-150 px и теряет черты персонажа; в кропе LoRA
рисует его крупно. Детектор: OpenCV YuNet (ComfyUI/models/facedetect, профиль lazymix).
Нужен opencv-python-headless в .venv.
"""
import json
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from generate import post, upload_image

ROOT = Path(__file__).resolve().parent.parent
YUNET = ROOT / "ComfyUI" / "models" / "facedetect" / "face_detection_yunet_2023mar.onnx"
CROP = 512


def find_face(img):
    """Самое крупное лицо: (x, y, w, h) или None."""
    if not YUNET.exists():
        raise SystemExit(f"нет {YUNET}: .\\scripts\\setup.ps1 lazymix")
    arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (arr.shape[1], arr.shape[0]), 0.6)
    _, faces = det.detect(arr)
    if faces is None:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])[:4]
    return float(x), float(y), float(w), float(h)


def crop_box(img, face, pad=2.2):
    """Квадрат вокруг лица с запасом (лоб, волосы, подбородок), не выходит за кадр."""
    x, y, w, h = face
    side = min(max(w, h) * pad, img.width, img.height)
    cx, cy = x + w / 2, y + h / 2 - h * 0.1  # чуть вверх: стрижка важна для узнаваемости
    left = int(min(max(cx - side / 2, 0), img.width - side))
    top = int(min(max(cy - side / 2, 0), img.height - side))
    return left, top, left + int(side), top + int(side)


def wait_image(host, prompt_id):
    while True:
        time.sleep(1)
        with urllib.request.urlopen(f"{host}/history/{prompt_id}") as resp:
            history = json.load(resp).get(prompt_id)
        if not history:
            continue
        if history.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(history["status"].get("messages"), ensure_ascii=False)[:2000])
        for output in history.get("outputs", {}).values():
            for image in output.get("images", []):
                return ROOT / "output" / image.get("subfolder", "") / image["filename"]


def face_workflow(base_wf, image_name, prompt, seed, denoise, steps):
    """img2img кропа лица теми же чекпойнтом, VAE, LoRA и негативом, что основной проход."""
    wf = {k: v for k, v in base_wf.items() if k in ("1", "2", "4") or v["class_type"] == "LoraLoader"}
    model = base_wf["6"]["inputs"]["model"]
    clip = base_wf["3"]["inputs"]["clip"]
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": prompt}}
    wf["40"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    wf["41"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["40", 0], "vae": ["2", 0]}}
    wf["42"] = {"class_type": "KSampler", "inputs": {
        "model": model, "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["41", 0],
        "seed": seed, "steps": steps, "cfg": base_wf["6"]["inputs"]["cfg"],
        "sampler_name": base_wf["6"]["inputs"]["sampler_name"], "scheduler": "karras", "denoise": denoise}}
    wf["43"] = {"class_type": "VAEDecode", "inputs": {"samples": ["42", 0], "vae": ["2", 0]}}
    wf["44"] = {"class_type": "SaveImage", "inputs": {"images": ["43", 0], "filename_prefix": "lazymix_facecrop"}}
    return wf


def fix_face(host, base_wf, image_path, prompt, seed, denoise=0.45, steps=30):
    """Возвращает путь к картинке с доработанным лицом (рядом с исходной, суффикс _face) или None."""
    img = Image.open(image_path).convert("RGB")
    face = find_face(img)
    if face is None:
        print("  лицо не найдено, доработка пропущена")
        return None
    box = crop_box(img, face)
    crop = img.crop(box).resize((CROP, CROP), Image.LANCZOS)
    tmp = ROOT / "output" / "_facecrop_in.png"
    crop.save(tmp)
    name = upload_image(host, tmp)
    wf = face_workflow(base_wf, name, prompt, seed, denoise, steps)
    out = wait_image(host, post(f"{host}/prompt", {"prompt": wf})["prompt_id"])
    new = Image.open(out).convert("RGB").resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS)
    # мягкая эллиптическая маска, чтобы не было шва
    side = new.width
    mask = Image.new("L", (side, side), 0)
    m = int(side * 0.12)
    ImageDraw.Draw(mask).ellipse([m, m, side - m, side - m], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(side * 0.06))
    img.paste(new, box[:2], mask)
    dst = Path(image_path).with_name(Path(image_path).stem + "_face.png")
    img.save(dst)
    tmp.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    return dst
