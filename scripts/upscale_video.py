"""Апскейл видео SeedVR2 3B (int8) через запущенный ComfyUI, звук сохраняется. Граф как в шаблоне
utility_seedvr2_3b_int8_upscale_video; модели: diffusion_models/seedvr2_3b_int8_convrot, vae/seedvr2_ema_vae_fp16.

  python scripts/upscale_video.py --video out.mp4 --scale 1.40625 --out output/upscaled
768x1344 * 1.40625 = 1080x1890; --scale 2 -> 1536x2688 (дольше).
"""
import argparse
import json
import random
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from generate import post, upload_image


def build(video_name, scale, seed, color, denoise):
    return {
        "1": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3": {"class_type": "ResizeImageMaskNode", "inputs": {
            "input": ["2", 0], "resize_type": "scale by multiplier", "resize_type.multiplier": scale,
            "scale_method": "lanczos"}},
        "4": {"class_type": "SeedVR2Preprocess", "inputs": {"resized_images": ["3", 0]}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": "seedvr2_ema_vae_fp16.safetensors"}},
        "6": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "seedvr2_3b_int8_convrot.safetensors", "weight_dtype": "default"}},
        "7": {"class_type": "VAEEncodeTiled", "inputs": {
            "pixels": ["4", 0], "vae": ["5", 0], "tile_size": 512, "overlap": 128,
            "temporal_size": 64, "temporal_overlap": 8}},
        # куски по времени подбираются под свободную VRAM, стыки сглаживаются перекрытием
        "8": {"class_type": "SeedVR2TemporalChunk", "inputs": {
            "latent": ["7", 0], "temporal_overlap": 1, "chunking_mode": "auto"}},
        "9": {"class_type": "SeedVR2Conditioning", "inputs": {"model": ["6", 0], "vae_conditioning": ["8", 0]}},
        "10": {"class_type": "KSampler", "inputs": {
            "model": ["6", 0], "positive": ["9", 0], "negative": ["9", 1], "latent_image": ["8", 0],
            "seed": seed, "steps": 1, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": denoise}},
        "11": {"class_type": "SeedVR2TemporalMerge", "inputs": {"latents": ["10", 0], "temporal_overlap": ["8", 1]}},
        "12": {"class_type": "VAEDecodeTiled", "inputs": {
            "samples": ["11", 0], "vae": ["5", 0], "tile_size": 512, "overlap": 128,
            "temporal_size": 64, "temporal_overlap": 8}},
        "13": {"class_type": "SeedVR2PostProcessing", "inputs": {
            "images": ["12", 0], "original_resized_images": ["3", 0], "color_correction_method": color}},
        "14": {"class_type": "CreateVideo", "inputs": {"images": ["13", 0], "audio": ["2", 1], "fps": ["2", 2]}},
        "15": {"class_type": "SaveVideo", "inputs": {
            "video": ["14", 0], "filename_prefix": "video/upscaled", "format": "auto", "format.codec": "auto"}},
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--scale", type=float, default=1.40625, help="1.40625: 768x1344 -> 1080x1890")
    parser.add_argument("--color", choices=["lab", "wavelet", "adain", "none"], default="lab",
                        help="подгонка цвета к оригиналу")
    parser.add_argument("--denoise", type=float, default=1.0,
                        help="меньше 1: меньше перерисовки и перешарпа, лицо ближе к оригиналу (0.4-0.7)")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--out", type=Path, default=Path("output/upscaled"))
    parser.add_argument("--host", default="http://127.0.0.1:8188")
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(2**48)
    workflow = build(upload_image(args.host, args.video), args.scale, seed, args.color, args.denoise)
    prompt_id = post(f"{args.host}/prompt", {"prompt": workflow})["prompt_id"]
    print(f"в очереди: {args.video.name} x{args.scale}")
    while True:
        time.sleep(5)
        with urllib.request.urlopen(f"{args.host}/history/{prompt_id}") as resp:
            history = json.load(resp).get(prompt_id)
        if history:
            break
    if history["status"].get("status_str") == "error":
        sys.exit("ошибка: " + json.dumps(history["status"].get("messages"), ensure_ascii=False)[-2000:])
    args.out.mkdir(parents=True, exist_ok=True)
    items = {(i["filename"], i["subfolder"], i["type"])
             for output in history["outputs"].values() for i in output.get("images", [])}
    for (filename, subfolder, kind) in items:
        q = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": kind})
        dst = args.out / f"{args.video.stem}_x{args.scale:g}_d{args.denoise:g}{Path(filename).suffix}"
        with urllib.request.urlopen(f"{args.host}/view?{q}") as resp:
            dst.write_bytes(resp.read())
        print("готово:", dst)


if __name__ == "__main__":
    main()
