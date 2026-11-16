"""Видео-датасет для LoRA MiniMax H3: короткие ролики из картинок персонажа через H3 (первый кадр).

Берёт картинки и подписи из датасета картинок (подпись с триггером, как для Qwen), для каждой генерирует
ролик с простым движением через запущенный ComfyUI и кладёт рядом подпись в формате MiniMax T2V:
  python scripts/make_video_dataset.py datasets/nastiya/images_v3 datasets/nastiya/videos_h3 --limit 20
Готовые ролики пропускаются, так что прерванный запуск можно продолжить той же командой.
После генерации просмотреть ролики и удалить (mp4 + txt) те, где лицо уплыло от первого кадра.
"""
import argparse
import json
import random
import shutil
import sys
import time
import urllib.request
from pathlib import Path

from generate import ROOT, post, upload_image
from generate_video import frames_for, size_for

# Простые движения, которые H3 держит без искажений; лицо остаётся в кадре.
MOTIONS = [
    "slowly turns her head toward the camera and gives a soft smile",
    "laughs softly, her shoulders shaking slightly, then looks back into the lens",
    "lifts one hand and brushes her hair back from her face, then lowers it",
    "shifts her gaze from the side to the camera with a calm expression and blinks",
    "tilts her head slightly and smiles, breathing calmly",
    "takes a slow breath, glances down, then raises her eyes to the camera",
    "slowly turns her head to the side and back, looking around",
    "gives a small amused smile and raises her eyebrows slightly",
]


def scene_from_caption(caption, trigger):
    """Сцена для подписи (как в датасете картинок) и для генерации: всё после триггера,
    без слов кадрирования вроде 'Close-up portrait' (H3 воспринимает их как команду перекадрировать)."""
    text = caption.strip().rstrip(".")
    for word in ("photograph", "photo"):
        text = text.replace(f"{word} of {trigger}", f"video of {trigger}").replace(word.capitalize() + f" of {trigger}", f"Video of {trigger}")
    rest = text[text.index(trigger) + len(trigger):]
    return text, "<Subject 1>" + rest


def generation_prompt(scene, seconds):
    end = f"00:{int(seconds):02d}.{int(round(seconds % 1 * 1000)):03d}"
    return (
        "subject_definitions:\n"
        "<Subject 1> is the woman from <Picture 1>, with the same face, hair, outfit and pose.\n\n"
        "summary:\n"
        f"A {seconds:g}-second live-action video of a portrait of {scene}, as in <Picture 1>.\n\n"
        "retention_analysis:\n"
        "<Subject 1> (appears in [Shot 1]): fully_preserved - face, hair, body, outfit and setting retained "
        "from <Picture 1>.\n\n"
        "detailed_description:\n"
        "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.\n"
        "Live-action, raw realistic footage. Natural skin texture and pores. Deep depth-of-field. "
        "Static camera with subtle handheld micro-drift.\n"
        "[Shot 1] At 00:00.000, {motion} until " + end + ".\n\n"
        "overall_soundscape:\nQuiet ambient room tone.\n\n"
        "non_diegetic_music:\nN/A"
    )


def training_caption(scene, motion):
    return (
        f"integrated_multimodal_description: [Shot 1] Live-action, static shot with subtle handheld drift. "
        f"{scene}. She {motion}.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A\n"
    )


def wait_for_video(host, prompt_id):
    while True:
        time.sleep(5)
        with urllib.request.urlopen(f"{host}/history/{prompt_id}") as resp:
            history = json.load(resp).get(prompt_id)
        if not history:
            continue
        status = history.get("status", {})
        if status.get("status_str") == "error":
            raise RuntimeError(json.dumps(status.get("messages"), ensure_ascii=False)[:2000])
        for output in history.get("outputs", {}).values():
            for items in output.values():
                for item in items if isinstance(items, list) else []:
                    if isinstance(item, dict) and str(item.get("filename", "")).endswith(".mp4"):
                        return ROOT / "output" / item.get("subfolder", "") / item["filename"]
        raise RuntimeError("ComfyUI не вернул mp4")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("images", type=Path, help="папка с png + txt (подписи с триггером)")
    parser.add_argument("out", type=Path, help="куда класть mp4 + txt")
    parser.add_argument("--trigger", help="по умолчанию из trigger.txt рядом с папкой картинок")
    parser.add_argument("--limit", type=int, default=20, help="сколько картинок взять (равномерно по датасету)")
    parser.add_argument("--only", nargs="*", help="конкретные картинки, например 001 015 032")
    parser.add_argument("--seconds", type=float, default=3, help="коротко: лицо меньше уплывает")
    parser.add_argument("--area", type=int, default=768 * 1152, help="площадь кадра в пикселях")
    parser.add_argument("--profile", default="server", choices=["server", "server_bf16"])
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--host", default="http://127.0.0.1:8188")
    args = parser.parse_args()

    trigger = args.trigger or (args.images.parent / "trigger.txt").read_text(encoding="utf-8").strip()
    images = sorted(args.images.glob("*.png"))
    if args.only:
        images = [p for p in images if p.stem in set(args.only)]
    elif args.limit < len(images):
        step = len(images) / args.limit
        images = [images[int(i * step)] for i in range(args.limit)]
    args.out.mkdir(parents=True, exist_ok=True)
    base = json.loads((ROOT / "workflows" / f"h3_nsfw_{args.profile}.json").read_text(encoding="utf-8"))
    rng = random.Random(args.seed)

    for n, image in enumerate(images):
        motion = MOTIONS[n % len(MOTIONS)]
        target = args.out / f"{image.stem}.mp4"
        if target.exists():
            print("есть:", target.name)
            continue
        caption = image.with_suffix(".txt").read_text(encoding="utf-8")
        if trigger not in caption:
            print(f"пропуск {image.name}: нет триггера '{trigger}' в подписи")
            continue
        train_scene, gen_scene = scene_from_caption(caption, trigger)
        workflow = json.loads(json.dumps(base))
        width, height = size_for(image, area=args.area)
        video = workflow["7"]["inputs"]
        video.update(prompt=generation_prompt(gen_scene, args.seconds).replace("{motion}", f"<Subject 1> {motion}"),
                     width=width, height=height, length=frames_for(args.seconds))
        workflow["20"] = {"class_type": "LoadImage", "inputs": {"image": upload_image(args.host, image)}}
        video["first_frame"] = ["20", 0]
        workflow["8"]["inputs"]["noise_seed"] = rng.randrange(2**48)
        prompt_id = post(f"{args.host}/prompt", {"prompt": workflow})["prompt_id"]
        print(f"[{n + 1}/{len(images)}] {image.name}: {motion} ({width}x{height}, {video['length']} кадров)")
        try:
            result = wait_for_video(args.host, prompt_id)
        except RuntimeError as err:
            print("  ошибка:", err)
            continue
        shutil.copy2(result, target)
        target.with_suffix(".txt").write_text(training_caption(train_scene, motion), encoding="utf-8")
        print("  ->", target)


if __name__ == "__main__":
    main()
