"""Похожесть лиц на референс (YuNet + SFace), для отбора кадров в датасет.

  python scripts/face_score.py datasets/nastiya/candidates_h3v2 [--ref datasets/nastiya/refs/nastiya_01.png]

Пишет scores.tsv в папку: файл, похожесть (косинус), размер лица в px.
Ориентиры: 0.55+ хорошо; лицо меньше ~100 px или повёрнуто в профиль — метрика ненадёжна.
"""
import argparse
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "ComfyUI" / "models" / "facedetect"
ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models/"
FILES = {
    "face_detection_yunet_2023mar.onnx": ZOO + "face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": ZOO + "face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def model(name):
    path = MODELS / name
    if not path.exists():
        MODELS.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(FILES[name], path)
    return str(path)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--ref", type=Path, default=ROOT / "datasets/nastiya/refs/nastiya_01.png")
    args = ap.parse_args()

    det = cv2.FaceDetectorYN.create(model("face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.6)
    rec = cv2.FaceRecognizerSF.create(model("face_recognition_sface_2021dec.onnx"), "")

    def embed(path):
        img = cv2.imread(str(path))
        det.setInputSize((img.shape[1], img.shape[0]))
        _, faces = det.detect(img)
        if faces is None:
            return None, 0
        face = max(faces, key=lambda f: f[2] * f[3])
        return rec.feature(rec.alignCrop(img, face)), int(max(face[2], face[3]))

    ref, _ = embed(args.ref)
    rows = []
    for path in sorted(args.folder.glob("*.png")):
        feat, size = embed(path)
        score = rec.match(ref, feat, cv2.FaceRecognizerSF_FR_COSINE) if feat is not None else float("nan")
        rows.append((path.name, score, size))
    rows.sort(key=lambda r: -np.nan_to_num(r[1], nan=-1))
    out = "\n".join(f"{n}\t{s:.3f}\t{z}" for n, s, z in rows)
    (args.folder / "scores.tsv").write_text(out + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
