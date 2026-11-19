"""Датасет персонажа из LoRA картинок (Qwen Image 2.1 + nastiya_v3) с подписями в формате MiniMax H3.

  python scripts/make_dataset_lora.py datasets/nastiya/shots_h3v2.txt datasets/nastiya/candidates_h3v2 --count 2

Строка списка: имя | nsfw | anatomy | v/h/s | сцена ("<кадр> of nst woman ..."), см. shots_h3v2.txt.
Кадры сохраняются как <имя>_<k>.png + .txt (подпись = сцена). Готовые пропускаются.
Отбор: scripts/face_score.py, затем лучшие копируются в images_*.
"""
import argparse
import json
import random
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZES = {"v": (832, 1216), "h": (1216, 832), "s": (1024, 1024)}
TAIL = ("Natural realistic skin texture with visible pores, fine skin details, slight imperfections, "
        "matte skin, candid photo.")
NEG = ("plastic skin, smooth skin, airbrushed, waxy skin, glossy skin, oily skin, retouched, cgi, 3d render, "
       "skinny, emaciated, visible ribs, fake breasts, implants, perfectly round breasts, blurry, lowres, "
       "deformed anatomy, extra fingers, watermark, text")
NEG_COVER = "exposed breasts, nipples, areola, topless, bra pulled down, see-through bra, "
NEG_ANATOMY = "penis, male genitalia, protruding labia, swollen genitals, malformed genitals, "
COVER = "Her breasts are fully covered by the bra: lined lace bra cups, nothing exposed."
CAPTION = ("integrated_multimodal_description: [Shot 1] Live-action, static shot. {scene}.\n\n"
           "overall_soundscape: N/A\n\nnon_diegetic_music: N/A")


def call(host, path, data=None):
    req = urllib.request.Request(host + path, json.dumps(data).encode() if data else None,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return r.read()


def parse(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            name, nsfw, anatomy, size, scene = (p.strip() for p in line.split("|", 4))
            yield name, float(nsfw), float(anatomy), SIZES[size], scene.rstrip(".")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("shots", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--only", help="имена через запятую")
    ap.add_argument("--lora", default="nastiya_v3.safetensors")
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    args = ap.parse_args()

    base = json.loads((ROOT / "workflows/qwen21_nastiya_server.json").read_text(encoding="utf-8"))
    for nid in ("40", "41", "42", "43", "44", "45"):  # апскейл не нужен
        base.pop(nid, None)
    args.out.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None

    jobs = {}
    for name, nsfw, anatomy, (w, h), scene in parse(args.shots):
        if only and name not in only:
            continue
        covered = nsfw == 0 and any(k in scene for k in ("lingerie", "bra", "panties"))
        prompt = f"{scene}."  # фигуру даёт LoRA: с описанием фигуры (бывший body.txt) Настя выходила полнее
        if covered:
            prompt += " " + COVER
        prompt += " " + TAIL
        neg = (NEG_COVER if covered else "") + (NEG_ANATOMY if anatomy else "") + NEG
        for k in range(1, args.count + 1):
            stem = f"{name}_{k}"
            if (args.out / f"{stem}.png").exists():
                continue
            wf = json.loads(json.dumps(base))
            wf["2"]["inputs"]["strength_model"] = nsfw
            wf["10"]["inputs"]["lora_name"] = args.lora
            wf["12"]["inputs"]["strength_model"] = anatomy
            wf["5"]["inputs"].update(prompt=prompt, negative_prompt=neg)
            wf["6"]["inputs"].update(width=w, height=h)
            wf["7"]["inputs"]["seed"] = random.randrange(2**48)
            wf["9"]["inputs"]["filename_prefix"] = f"dataset_h3v2/{stem}"
            pid = json.loads(call(args.host, "/prompt", {"prompt": wf}))["prompt_id"]
            jobs[pid] = (stem, scene)
    print(f"в очереди: {len(jobs)}", flush=True)

    t0, done = time.time(), 0
    while jobs:
        time.sleep(3)
        for pid in list(jobs):
            hist = json.loads(call(args.host, f"/history/{pid}")).get(pid)
            if not hist:
                continue
            stem, scene = jobs.pop(pid)
            done += 1
            if hist.get("status", {}).get("status_str") == "error":
                print(stem, "ошибка", json.dumps(hist["status"].get("messages"), ensure_ascii=False)[:800], flush=True)
                continue
            img = next(i for o in hist["outputs"].values() for i in o.get("images", []))
            q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": "output"})
            (args.out / f"{stem}.png").write_bytes(call(args.host, f"/view?{q}"))
            (args.out / f"{stem}.txt").write_text(CAPTION.format(scene=scene), encoding="utf-8")
            print(f"{done} {stem} {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
