"""Скачивает модели для выбранного профиля из models.json в ComfyUI/models.

Использование: python scripts/download_models.py --profile local-16gb|server
Поддерживает докачку: недокачанные файлы лежат рядом с суффиксом .part.
Токены берутся из переменных окружения или файла .env в корне репозитория.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHUNK = 8 * 1024 * 1024


def load_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def build_request(spec):
    url = spec["url"]
    headers = {}
    if spec.get("auth") == "civitai":
        token = os.environ.get("CIVITAI_TOKEN")
        if not token:
            sys.exit("Нужен CIVITAI_TOKEN в .env (civitai.com -> Account -> API Keys)")
        # Токен в query, а не в заголовке: Civitai редиректит на подписанный URL хранилища
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"token": token})
    elif "huggingface.co" in url and os.environ.get("HF_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["HF_TOKEN"]
    req = urllib.request.Request(url, headers={"User-Agent": "AdUltAi-downloader"})
    for key, value in headers.items():
        # не пересылаем токен на CDN после редиректа
        req.add_unredirected_header(key, value)
    return req


def file_name(spec):
    if "name" in spec:
        return spec["name"]
    return Path(urllib.parse.urlparse(spec["url"]).path).name


def download(spec, target):
    if target.exists():
        print(f"  уже есть: {target.name}")
        return
    part = target.with_name(target.name + ".part")
    offset = part.stat().st_size if part.exists() else 0
    req = build_request(spec)
    if offset:
        req.add_header("Range", f"bytes={offset}-")
    with urllib.request.urlopen(req, timeout=60) as resp:
        if offset and resp.status != 206:
            offset = 0  # сервер не поддержал докачку, начинаем заново
        total = resp.length + offset if resp.length else None
        done = offset
        started = time.time()
        with open(part, "ab" if offset else "wb") as f:
            while chunk := resp.read(CHUNK):
                f.write(chunk)
                done += len(chunk)
                speed = (done - offset) / max(time.time() - started, 1e-6) / 1e6
                pct = f"{done * 100 / total:5.1f}%" if total else ""
                print(f"\r  {target.name}: {done / 1e9:6.2f} GB {pct} {speed:6.1f} MB/s", end="", flush=True)
    print()
    part.replace(target)


def main():
    # консоль Windows может быть не в UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    config = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(config["profiles"]))
    parser.add_argument("--models-dir", default=str(ROOT / "ComfyUI" / "models"))
    args = parser.parse_args()

    load_env()
    profile = config["profiles"][args.profile]
    print(f"Профиль {args.profile}: {profile['description']}")
    for key in profile["files"]:
        spec = config["files"][key]
        target_dir = Path(args.models_dir) / spec["dir"]
        target_dir.mkdir(parents=True, exist_ok=True)
        name = file_name(spec)
        if not re.fullmatch(r"[\w.\-]+", name):
            sys.exit(f"Недопустимое имя файла: {name}")
        download(spec, target_dir / name)
    print("Готово.")


if __name__ == "__main__":
    main()
