"""Видео MiniMax H3 (со звуком) через запущенный ComfyUI.

Текст в видео:
  python scripts/generate_video.py -p "..." --seconds 5
Из картинки (первый кадр), можно добавить и последний:
  python scripts/generate_video.py --first-frame start.png [--last-frame end.png] -p "..."
Персонаж по референсам (ref2va, до 9 картинок, в промпте <Picture 1>, <Picture 2>...):
  python scripts/generate_video.py --ref face.png --ref body.png -p "..." [--turbo]
  + первый/последний кадр (экспериментально): --ref face.png --first-frame start.png
Подставить персонажа в чужое видео (до 3 видео, в промпте <Video 1>...):
  python scripts/generate_video.py --ref face.png --ref-video clip.mp4 --seconds 5 \
      -p "Replace the woman in <Video 1> with the woman from <Picture 1>, keep motion and camera of <Video 1>."
Рисованный стиль (Digital Art LoRA): добавить --style 1.0
Видео сохраняются в output/video/.
"""
import argparse
import json
import random
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from generate import ROOT, post, upload_image

FPS = 24
STYLE_LORA = "minimax_h3_digital_art_v3.safetensors"
STYLE_TRIGGER = "flat cel shading, bold outlines, multi colors"
REF_TURBO_LORA = "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"


def frames_for(seconds):
    """Модель принимает длину 17k+5 кадров: округляем вверх, как официальный шаблон."""
    n = max(5, round(seconds * FPS))
    return n + (5 - n % 17) % 17


def size_for(image_path, area=1344 * 768, step=32):
    """Размер видео с пропорциями картинки и площадью как у 1344x768, кратно 32."""
    from PIL import Image
    with Image.open(image_path) as img:
        w, h = img.size
    scale = (area / (w * h)) ** 0.5
    return max(step, round(w * scale / step) * step), max(step, round(h * scale / step) * step)


def video_size(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    w, h = (int(x) for x in out.strip().split(",")[:2])
    return w, h


def prepare_ref_video(path, seconds):
    """Референс-видео для ref2va: 24 fps, без звука, не длиннее ролика (модель берёт 2-15 с)."""
    out = Path(tempfile.gettempdir()) / f"ref_{path.stem}_24fps.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-t", str(min(seconds, 15)),
                    "-vf", "fps=24", "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(out)],
                   check=True)
    return out


def add_pose_control(workflow, video_name, strength):
    """Скелеты SDPose из видео ведут движение через Fun ControlNet-Union, как в официальном шаблоне.
    Точки лица не рисуем: они переносят геометрию лица исходного человека."""
    model = workflow["11"]["inputs"]["model"]
    workflow.update({
        "60": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "61": {"class_type": "GetVideoComponents", "inputs": {"video": ["60", 0]}},
        "62": {"class_type": "ResizeImageMaskNode", "inputs": {
            "input": ["61", 0], "resize_type": "scale longer dimension", "resize_type.longer_size": 1024,
            "scale_method": "lanczos"}},
        "63": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "rt_detr_v4-x-hgnet_fp16.safetensors", "weight_dtype": "default"}},
        "64": {"class_type": "RTDETR_detect", "inputs": {
            "model": ["63", 0], "image": ["62", 0], "threshold": 0.5, "class_name": "person", "max_detections": 1}},
        "65": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdpose_wholebody_fp16.safetensors"}},
        "66": {"class_type": "SDPoseKeypointExtractor", "inputs": {
            "model": ["65", 0], "vae": ["65", 2], "image": ["62", 0], "bboxes": ["64", 0], "batch_size": 16}},
        "67": {"class_type": "SDPoseDrawKeypoints", "inputs": {
            "keypoints": ["66", 0], "draw_body": True, "draw_hands": True, "draw_face": False, "draw_feet": True,
            "stick_width": 4, "face_point_size": 2, "score_threshold": 0.5, "draw_head": True}},
        "68": {"class_type": "ModelPatchLoader", "inputs": {
            "name": "minimax_h3_fun_controlnet_union_pruned_int8_convrot.safetensors"}},
        "69": {"class_type": "MiniMaxH3FunControlNetApply", "inputs": {
            "model": model, "model_patch": ["68", 0], "vae": ["5", 0], "control_video": ["67", 0],
            "strength": strength, "start_percent": 0.0, "end_percent": 1.0}},
        "70": {"class_type": "CreateVideo", "inputs": {"images": ["67", 0], "fps": FPS}},
        "71": {"class_type": "SaveVideo", "inputs": {
            "video": ["70", 0], "filename_prefix": "video/pose", "format": "auto", "format.codec": "auto"}},
    })
    workflow["10"]["inputs"]["model"] = workflow["11"]["inputs"]["model"] = ["69", 0]


def main():
    # консоль Windows может быть не в UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="server", choices=["server", "server_bf16", "local"],
                        help="local: RTX 4060 Ti 16GB, turbo 4 шага уже включён")
    parser.add_argument("-p", "--prompt", required=True, help="сцена, движение камеры и звук одним текстом")
    parser.add_argument("--first-frame", type=Path)
    parser.add_argument("--last-frame", type=Path)
    parser.add_argument("--ref", type=Path, action="append", default=[],
                        help="референс персонажа (ref2va), можно до 9 раз; в промпте <Picture 1>, <Picture 2>...")
    parser.add_argument("--ref-video", type=Path, action="append", default=[],
                        help="референс-видео (ref2va), до 3 раз; в промпте <Video 1>, <Video 2>...; звук не передаётся")
    parser.add_argument("--control-video", type=Path,
                        help="движение из видео: поза SDPose -> Fun ControlNet (профиль h3-control-server)")
    parser.add_argument("--control-strength", type=float, default=1.0, help="ниже 1 поза свободнее")
    parser.add_argument("--ref-size", choices=["match", "max"], default="match",
                        help="max: референсы до 2048 px, лицо точнее, но в разы медленнее")
    parser.add_argument("--turbo", action="store_true", help="ref2va: turbo LoRA на 4 шага вместо 20")
    parser.add_argument("--seconds", type=float, default=5, help="обучено на ~5-15 с")
    parser.add_argument("--width", type=int, help="по умолчанию 1344 или по пропорциям --first-frame")
    parser.add_argument("--height", type=int, help="по умолчанию 768 или по пропорциям --first-frame")
    parser.add_argument("--steps", type=int, help="8 с turbo LoRA (local: 4)")
    parser.add_argument("--lora", type=float, help="сила NSFW LoRA, автор советует 0.3-1, начинать с 0.5")
    parser.add_argument("--style", type=float, metavar="STRENGTH",
                        help="рисованный стиль Digital Art LoRA, автор советует 0.8-1.5, база 1.0")
    parser.add_argument("--char-lora", metavar="FILE[:STRENGTH]",
                        help="LoRA персонажа на fl2va, например nastiya_h3v2_000003000.safetensors:1.0; "
                             "в промпте триггер (nst woman), внешность не описывать")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, help="по умолчанию случайный")
    parser.add_argument("--host", default="http://127.0.0.1:8188")
    args = parser.parse_args()

    if len(args.ref) > 9:
        parser.error("ref2va принимает до 9 референсов")
    if len(args.ref_video) > 3:
        parser.error("ref2va принимает до 3 референс-видео")
    is_ref = bool(args.ref or args.ref_video)
    if args.turbo and not is_ref:
        parser.error("--turbo только для --ref; у fl2va turbo уже включён")
    if args.profile == "local":
        args.turbo = False  # в h3_*_local.json turbo LoRA уже стоит
    kind = "ref" if is_ref else "nsfw"
    workflow = json.loads((ROOT / "workflows" / f"h3_{kind}_{args.profile}.json").read_text(encoding="utf-8"))
    video = workflow["7"]["inputs"]
    prompt = args.prompt
    if args.style is not None:
        workflow["17"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["3", 0], "lora_name": STYLE_LORA, "strength_model": args.style}}
        workflow["10"]["inputs"]["model"] = workflow["11"]["inputs"]["model"] = ["17", 0]
        prompt = f"{STYLE_TRIGGER}. {prompt}"
    if args.width and args.height:
        width, height = args.width, args.height
    elif args.first_frame or args.last_frame:
        width, height = size_for(args.first_frame or args.last_frame)
    elif args.ref_video:
        w, h = video_size(args.ref_video[0])
        scale = (1344 * 768 / (w * h)) ** 0.5
        width, height = max(32, round(w * scale / 32) * 32), max(32, round(h * scale / 32) * 32)
    else:
        width, height = args.width or 1344, args.height or 768
    video.update(prompt=prompt, width=width, height=height, length=frames_for(args.seconds))
    if args.turbo:
        workflow["2"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["1", 0], "lora_name": REF_TURBO_LORA, "strength_model": 1.0}}
        workflow["3"]["inputs"]["model"] = ["2", 0]
        workflow["10"]["inputs"]["steps"] = 4
    if args.ref:
        video["ref_image_size"] = args.ref_size
        for i, path in enumerate(args.ref):
            workflow[f"3{i}"] = {"class_type": "LoadImage", "inputs": {"image": upload_image(args.host, path)}}
            video[f"ref_images.ref_image_{i}"] = [f"3{i}", 0]
    for i, path in enumerate(args.ref_video):
        name = upload_image(args.host, prepare_ref_video(path, args.seconds))
        workflow[f"4{i}"] = {"class_type": "LoadVideo", "inputs": {"file": name}}
        workflow[f"5{i}"] = {"class_type": "GetVideoComponents", "inputs": {"video": [f"4{i}", 0]}}
        video[f"ref_videos.ref_video_{i}"] = [f"5{i}", 0]
    if args.char_lora:
        name, _, strength = args.char_lora.partition(":")
        workflow["18"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": workflow["11"]["inputs"]["model"], "lora_name": name, "strength_model": float(strength or 1.0)}}
        workflow["10"]["inputs"]["model"] = workflow["11"]["inputs"]["model"] = ["18", 0]
    if args.control_video:
        add_pose_control(workflow, upload_image(args.host, prepare_ref_video(args.control_video, args.seconds)),
                         args.control_strength)
    if args.steps:
        workflow["10"]["inputs"]["steps"] = args.steps
    if args.lora is not None:
        workflow["3"]["inputs"]["strength_model"] = args.lora
    for key, node_id, path in (("first_frame", "20", args.first_frame), ("last_frame", "21", args.last_frame)):
        if path:
            workflow[node_id] = {"class_type": "LoadImage", "inputs": {"image": upload_image(args.host, path)}}
            if is_ref:
                # у ref2va нет входов first/last_frame: кадр закрепляется узлом Add Guide (экспериментально)
                guide_id = str(int(node_id) + 2)  # 22, 23
                workflow[guide_id] = {"class_type": "MiniMaxH3AddGuide", "inputs": {
                    "positive": workflow["11"]["inputs"]["conditioning"], "vae": ["5", 0], "latent": ["7", 1],
                    "image": [node_id, 0], "frame_idx": 0 if key == "first_frame" else -1}}
                workflow["11"]["inputs"]["conditioning"] = [guide_id, 0]
            else:
                video[key] = [node_id, 0]

    seed = args.seed if args.seed is not None else random.randrange(2**48)
    pending = set()
    for i in range(args.count):
        workflow["8"]["inputs"]["noise_seed"] = seed + i
        pending.add(post(f"{args.host}/prompt", {"prompt": workflow})["prompt_id"])
        print(f"в очереди: seed={seed + i}, {width}x{height}, кадров={video['length']}")

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
