"""Веб-интерфейс для LoRA персонажа: фото -> датасет -> перегенерация неудачных -> обучение.

  python scripts/lora_studio.py                     # открыть http://127.0.0.1:8190
  python scripts/lora_studio.py --profile server

ComfyUI запускается сам для генерации и останавливается перед обучением (нужна вся видеопамять).
Если ComfyUI запущен вручную, перед обучением его надо закрыть.
Данные персонажа: datasets/<имя>/ (refs/ - фото лица, body/ - фото фигуры, images/ - датасет, prompts.txt, trigger.txt).
Сцены с <image2> в промпте получают вторым референсом фото фигуры и описание фигуры из body.txt (только для
генерации, в подпись не попадает), сцены с <image2> или nude/naked - NSFW LoRA (--nsfw-lora).
Фото фигуры можно сгенерировать в студии по шкалам из training/body_scales.txt и типажам из
training/body_types.txt (body_candidates/).
Обученную LoRA можно проверить в студии: картинки по промпту с триггером кладутся в generated/.
Только вымышленные персонажи, вы сами или взрослые, которые на это согласились.
"""
import argparse
import base64
import io
import json
import mimetypes
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from generate import ROOT, add_edit, add_img2img, post, upload_image

DATASETS = ROOT / "datasets"
AI_TOOLKIT = ROOT / "ai-toolkit"
TRAIN_OUTPUT = AI_TOOLKIT / "output"
LORAS = ROOT / "ComfyUI" / "models" / "loras"
SKIN_LORA = "qwen21_glamour_realism_v1.safetensors"  # кожа без «пластика», ставится с профилями local-16gb и server
SKIN_NEGATIVE = "airbrushed, plastic skin, glossy skin"
PAGE = Path(__file__).with_suffix(".html")
TEMPLATE_PROMPTS = ROOT / "training" / "character_prompts.txt"
TEMPLATE_CONFIG = ROOT / "training" / "character_template.yaml"
BODY_SCALES = ROOT / "training" / "body_scales.txt"  # [Шкала] ступень: фраза
BODY_TYPES = ROOT / "training" / "body_types.txt"    # Типаж: Шкала=ступень; ...
SCALE_LINE = re.compile(r"^\[([^\]]+)\]\s*([^:]+):\s*(.+)$")
BODY_FRONT = ("Photograph of a nude adult {subject}'s body from the neck down, standing straight facing the camera, "
              "arms relaxed slightly away from the sides, feet shoulder-width apart, {description}, "
              "plain light grey studio background, soft even studio lighting, sharp focus, full body from neck to feet, "
              "head out of frame.")
BODY_VIEW = ("Keep the exact same body shape as <image1>. The same nude body from <image1>, identical proportions "
             "and skin tone, {view}, full body from neck to feet, head out of frame, "
             "same plain grey background and soft studio lighting.")
BODY_VIEWS = ["standing in strict left profile, arms relaxed",
              "seen from directly behind, standing straight, arms relaxed",
              "three-quarter view turned to the right, weight on one leg"]
SUBJECT = re.compile(r"the (woman|man|person) from <image1>(?: with the body from <image2>)?", re.IGNORECASE)
NUDE = re.compile(r"\b(nude|naked|topless)\b", re.IGNORECASE)
BEHIND = re.compile(r"\b(from behind|back view|rear view)\b", re.IGNORECASE)
CLOTHED_PROMPT = "fully clothed, her clothes fully cover her chest"
CLOTHED_NEGATIVE ="nudity, nude, topless, exposed breasts, nipples, nip slip, see-through clothing"
NAME = re.compile(r"^[A-Za-z0-9_-]+$")
PROGRESS = re.compile(r"(\d+)/(\d+) \[")
MIN_IMAGES = 5
STEPS = 2000
SIZES = {(832, 1216), (1216, 832), (1024, 1024)}

args = None
lock = threading.Lock()
stop_event = threading.Event()
# при генерации step/total - готово картинок из поставленных, durations - сколько секунд шла каждая
job = {"kind": None, "name": None, "status": "", "error": "", "step": 0, "total": 0, "log": [], "started": 0, "durations": []}
queue = []          # (имя, номер) картинок на генерацию
body_queue = []     # (имя, промпт, исходная картинка или None) вариантов фигуры
lora_queue = []     # (имя, промпт, LoRA, сила, сила NSFW LoRA, сила LoRA кожи, ширина, высота, референс или None,
                    # denoise для img2img или None для edit) картинок с обученной LoRA
running_item = None
item_errors = {}    # (имя, номер) -> текст ошибки
comfy_proc = None   # ComfyUI, запущенный этим сервером
train_proc = None


class Project:
    def __init__(self, name):
        if not NAME.match(name or ""):
            raise ValueError("Имя персонажа: латиница, цифры, _ и -")
        self.name = name
        self.dir = DATASETS / name
        self.refs = self.dir / "refs"
        self.body = self.dir / "body"
        self.candidates = self.dir / "body_candidates"
        self.images = self.dir / "images"
        self.generated = self.dir / "generated"
        self.gen_refs = self.dir / "gen_refs"

    def ensure(self):
        self.refs.mkdir(parents=True, exist_ok=True)
        if not (self.dir / "prompts.txt").exists():
            self.save_prompts(self.prompts())

    def prompts(self):
        path = self.dir / "prompts.txt"
        if not path.exists():
            path = TEMPLATE_PROMPTS
        return [p.strip() for p in path.read_text(encoding="utf-8").splitlines() if p.strip()]

    def save_prompts(self, prompts):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "prompts.txt").write_text("\n".join(prompts) + "\n", encoding="utf-8")

    def trigger(self):
        path = self.dir / "trigger.txt"
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""

    def body_description(self):
        path = self.dir / "body.txt"
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""

    def photos(self):
        photos = sorted(self.refs.glob("*.png")) if self.refs.exists() else []
        legacy = self.dir / "ref.png"  # датасеты, собранные make_dataset.py
        return photos or ([legacy] if legacy.exists() else [])

    def body_photos(self):
        return sorted(self.body.glob("*.png")) if self.body.exists() else []

    def body_candidates(self):
        return sorted(self.candidates.glob("*.png")) if self.candidates.exists() else []

    def subject(self):
        prompts = self.prompts()
        return match[1].lower() if prompts and (match := SUBJECT.search(prompts[0])) else "woman"

    def generated_images(self):
        return sorted(self.generated.glob("*.png")) if self.generated.exists() else []

    def loras(self):
        """Готовые LoRA из ComfyUI и промежуточные сохранения обучения: имя -> файл."""
        found = {p.name: p for p in TRAIN_OUTPUT.glob(f"{self.name}_v*/{self.name}_v*.safetensors")}
        found.update((p.name, p) for p in LORAS.glob(f"{self.name}_v*.safetensors"))
        return dict(sorted(found.items()))

    def image(self, index):
        return self.images / f"{index:03d}.png"

    def done(self):
        return [i for i in range(1, len(self.prompts()) + 1) if self.image(i).exists()]


def file_url(path):
    return "/file?" + urllib.parse.urlencode({"path": path.relative_to(ROOT).as_posix(), "v": int(path.stat().st_mtime)})


def comfy_alive():
    try:
        with urllib.request.urlopen(f"{args.host}/system_stats", timeout=3):
            return True
    except OSError:
        return False


def ensure_comfy():
    global comfy_proc
    if comfy_alive():
        return
    set_status("Запуск ComfyUI...")
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    comfy_proc = subprocess.Popen([str(python), str(ROOT / "ComfyUI" / "main.py"), "--port", args.host.rsplit(":", 1)[-1],
                                   "--output-directory", str(ROOT / "output")])
    while not comfy_alive():
        if comfy_proc.poll() is not None:
            comfy_proc = None
            raise RuntimeError("ComfyUI не запустился, смотрите консоль сервера")
        if stop_event.is_set():
            raise RuntimeError("Остановлено")
        time.sleep(3)


def stop_comfy():
    global comfy_proc
    if comfy_proc:
        comfy_proc.terminate()
        try:
            comfy_proc.wait(30)
        except subprocess.TimeoutExpired:
            comfy_proc.kill()
        comfy_proc = None


def set_status(text):
    with lock:
        job["status"] = text


def wait_image(prompt_id):
    while True:
        if stop_event.is_set():
            raise RuntimeError("Остановлено")
        time.sleep(2)
        with urllib.request.urlopen(f"{args.host}/history/{prompt_id}") as resp:
            history = json.load(resp).get(prompt_id)
        if not history:
            continue
        if history.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(history["status"].get("messages"), ensure_ascii=False)[:500])
        for output in history.get("outputs", {}).values():
            for image in output.get("images", []):
                query = urllib.parse.urlencode({k: image[k] for k in ("filename", "subfolder", "type")})
                with urllib.request.urlopen(f"{args.host}/view?{query}") as resp:
                    return resp.read()
        raise RuntimeError("в ответе ComfyUI нет картинки")


def render(prompt, ref_names=()):
    """Картинка по промпту: с референсами - режим edit, без - текст в картинку 832x1216."""
    workflow = json.loads((ROOT / "workflows" / f"qwen21_nsfw_{args.profile}.json").read_text(encoding="utf-8"))
    workflow["5"]["inputs"]["prompt"] = prompt
    # базовая модель плохо рисует обнажённое тело, а без NSFW LoRA одетой рисует свою худую фигуру вместо <image2>;
    # на полной силе одетая сцена с голым фото фигуры выходит с открытой грудью - LoRA слабее и нагота в негативе
    if NUDE.search(prompt):
        strength = args.nsfw_lora
    elif "<image2>" in prompt:
        strength = args.clothed_lora
        workflow["5"]["inputs"]["negative_prompt"] += ", " + CLOTHED_NEGATIVE
    else:
        strength = args.lora
    workflow["2"]["inputs"]["strength_model"] = strength
    workflow["7"]["inputs"]["seed"] = random.randrange(2**48)
    if ref_names:
        add_edit(workflow, list(ref_names))
    else:
        workflow["6"]["inputs"].update(width=832, height=1216)
    return wait_image(post(f"{args.host}/prompt", {"prompt": workflow})["prompt_id"])


def generate_image(project, index, prompt, ref_names):
    save_image(project, index, render(prompt, ref_names))


def generate_body(name, prompt, source):
    project = Project(name)
    data = render(prompt, [upload_image(args.host, source)] if source else [])
    next_path(project.candidates, f"{name}_cand").write_bytes(data)


def generate_with_lora(name, prompt, lora, strength, nsfw, skin, width, height, ref, denoise):
    """Проверка обученной LoRA: LoRA персонажа после NSFW LoRA, с LoRA кожи - ещё она и CFG 2.5, как советует README.
    Без референса - текст в картинку. С референсом и denoise - img2img: лицо рисует LoRA, как при обучении;
    без denoise - режим edit (<image1>), модель видит референс и тянет с него и лицо. Размер - с референса."""
    project = Project(name)
    workflow = json.loads((ROOT / "workflows" / f"qwen21_nsfw_{args.profile}.json").read_text(encoding="utf-8"))
    seed = random.randrange(2**48)
    workflow["5"]["inputs"]["prompt"] = prompt
    workflow["2"]["inputs"]["strength_model"] = nsfw
    if ref and denoise is not None:
        add_img2img(workflow, upload_image(args.host, project.gen_refs / ref), denoise)
    elif ref:
        add_edit(workflow, [upload_image(args.host, project.gen_refs / ref)])
    else:
        workflow["6"]["inputs"].update(width=width, height=height)
    workflow["30"] = {"class_type": "LoraLoaderModelOnly", "_meta": {"title": "Character LoRA"},
                      "inputs": {"model": ["2", 0], "lora_name": lora, "strength_model": strength}}
    workflow["7"]["inputs"].update(model=["30", 0], seed=seed)
    if skin:
        workflow["31"] = {"class_type": "LoraLoaderModelOnly", "_meta": {"title": "Skin LoRA"},
                          "inputs": {"model": ["30", 0], "lora_name": SKIN_LORA, "strength_model": skin}}
        workflow["7"]["inputs"].update(model=["31", 0], cfg=2.5)
        workflow["5"]["inputs"]["negative_prompt"] += ", " + SKIN_NEGATIVE
    data = wait_image(post(f"{args.host}/prompt", {"prompt": workflow})["prompt_id"])
    path = next_path(project.generated, f"{name}_gen")
    path.write_bytes(data)
    info = {"prompt": prompt, "lora": lora, "strength": strength, "nsfw": nsfw, "skin": skin, "seed": seed, "ref": ref,
            "denoise": denoise}
    path.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")


def next_path(folder, prefix):
    folder.mkdir(parents=True, exist_ok=True)
    numbers = [int(m[1]) for p in folder.glob("*.png") if (m := re.search(r"_(\d+)\.png$", p.name))]
    return folder / f"{prefix}_{max(numbers, default=0) + 1:02d}.png"


def save_image(project, index, data):
    project.images.mkdir(parents=True, exist_ok=True)
    # кэш ai-toolkit привязан к имени файла, а не к содержимому: у новой картинки его надо сбросить
    for cache in ("_latent_cache", "_t_e_cache"):
        for old in (project.images / cache).glob(f"{index:03d}_*"):
            old.unlink()
    project.image(index).write_bytes(data)


def finish_item():
    with lock:
        job["step"] += 1
        job["durations"].append(time.time() - job["started"])


def generation_worker():
    global running_item
    uploaded = {}
    try:
        ensure_comfy()
        while not stop_event.is_set():
            with lock:
                if queue:
                    name, index = running_item = queue.pop(0)
                    job["status"] = f"Генерация фото {index}, в очереди ещё {len(queue)}"
                elif body_queue:
                    task = running_item = body_queue.pop(0)
                    name, index = task[0], None
                    run_task, error_key = generate_body, "body"
                    job["status"] = f"Генерация фигуры, в очереди ещё {len(body_queue)}"
                elif lora_queue:
                    task = running_item = lora_queue.pop(0)
                    name, index = task[0], None
                    run_task, error_key = generate_with_lora, "lora"
                    job["status"] = f"Генерация с LoRA, в очереди ещё {len(lora_queue)}"
                else:
                    break
                job["started"] = time.time()
            if index is None:
                try:
                    run_task(*task)
                    item_errors.pop((name, error_key), None)
                except Exception as e:
                    if stop_event.is_set():
                        break
                    item_errors[(name, error_key)] = str(e)
                finally:
                    running_item = None
                    finish_item()
                continue
            project = Project(name)
            try:
                if name not in uploaded:
                    uploaded[name] = ([upload_image(args.host, p) for p in project.photos()],
                                      [upload_image(args.host, p) for p in project.body_photos()])
                faces, bodies = uploaded[name]
                if not faces:
                    raise RuntimeError("Нет фото персонажа")
                # фото персонажа чередуются по сценам
                refs = [faces[(index - 1) % len(faces)]]
                prompt = project.prompts()[index - 1]
                if "<image2>" in prompt:
                    if not bodies:
                        raise RuntimeError("В промпте <image2>, а фото фигуры не загружены")
                    # первое фото фигуры - спереди, последнее - со спины: по кругу сцена спереди
                    # получала вид со спины, и модель придумывала грудь сама
                    refs.append(bodies[-1] if BEHIND.search(prompt) else bodies[0])
                    # фото фигуры плохо переносит пропорции на одетое тело и вид сбоку: помогает текст
                    # голое фото фигуры переносит наготу на одетую сцену, одного негатива мало
                    if not NUDE.search(prompt):
                        prompt = f"{prompt.rstrip('. ')}, {CLOTHED_PROMPT}"
                    if description := project.body_description():
                        prompt = f"{prompt.rstrip('. ')}, {description.rstrip('. ')}."
                generate_image(project, index, prompt, refs)
                item_errors.pop((name, index), None)
            except Exception as e:  # ошибка одной картинки не останавливает остальные
                if stop_event.is_set():
                    break
                item_errors[(name, index)] = str(e)
            finally:
                running_item = None
                finish_item()
        set_status("Остановлено" if stop_event.is_set() else "Фото готовы")
    except Exception as e:
        with lock:
            job["error"] = str(e)
    finally:
        with lock:
            queue.clear()
            body_queue.clear()
            lora_queue.clear()
            job["kind"] = None


def write_captions(project, trigger):
    for index, prompt in enumerate(project.prompts(), 1):
        if project.image(index).exists():
            caption = SUBJECT.sub(trigger, prompt).replace("<image1>", "").replace("<image2>", "").strip()
            project.image(index).with_suffix(".txt").write_text(caption, encoding="utf-8")


def run_name(name):
    # прерванный запуск продолжается (ai-toolkit берёт последнее сохранение), законченный - новая версия
    version = 1
    while (TRAIN_OUTPUT / f"{name}_v{version}" / f"{name}_v{version}.safetensors").exists():
        version += 1
    return f"{name}_v{version}"


def log_line(line):
    with lock:
        match = PROGRESS.search(line)
        if match:
            job["step"], job["total"] = int(match[1]), int(match[2])
            if job["log"] and PROGRESS.search(job["log"][-1]):
                job["log"][-1] = line  # прогресс-бар tqdm перерисовывает одну строку
                return
        job["log"] = (job["log"] + [line])[-300:]


def training_worker(project):
    global train_proc
    try:
        set_status("Остановка ComfyUI...")
        stop_comfy()
        if comfy_alive():
            raise RuntimeError(f"ComfyUI на {args.host} запущен вручную: закройте его, обучению нужна вся видеопамять")
        trigger = project.trigger()
        write_captions(project, trigger)
        run = run_name(project.name)
        config = ROOT / "training" / f"{run}.yaml"
        text = TEMPLATE_CONFIG.read_text(encoding="utf-8")
        text = text.replace("{run}", run).replace("{name}", project.name).replace("{trigger}", trigger)
        config.write_text(text.replace("{steps}", str(STEPS)), encoding="utf-8")

        set_status(f"Обучение {run}: загрузка моделей и кэширование датасета...")
        python = AI_TOOLKIT / ("venv/Scripts/python.exe" if os.name == "nt" else "venv/bin/python")
        env = {**os.environ, "MODELS_PATH": str(ROOT / "ComfyUI" / "models"), "PYTHONUNBUFFERED": "1"}
        group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        train_proc = subprocess.Popen([str(python), "run.py", str(config)], cwd=AI_TOOLKIT, env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **group)
        buffer = ""
        while chunk := train_proc.stdout.read1(4096):
            buffer += chunk.decode("utf-8", "replace")
            *lines, buffer = re.split(r"[\r\n]", buffer)
            for line in lines:
                if line.strip():
                    log_line(line)
                    if PROGRESS.search(line) and job["total"] == STEPS:
                        set_status(f"Обучение {run}")
        code = train_proc.wait()
        if stop_event.is_set():
            set_status("Обучение остановлено. «Начать обучение» продолжит с последнего сохранения (каждые 250 шагов)")
            return
        if code:
            raise RuntimeError(f"ai-toolkit завершился с кодом {code}, смотрите лог")
        lora = TRAIN_OUTPUT / run / f"{run}.safetensors"
        dst = ROOT / "ComfyUI" / "models" / "loras" / lora.name
        shutil.copy2(lora, dst)
        set_status(f"Готово: {dst.relative_to(ROOT).as_posix()}. В промпте: photo of {trigger} ...")
    except Exception as e:
        with lock:
            job["error"] = str(e)
    finally:
        train_proc = None
        with lock:
            job["kind"] = None


def start_job(kind, name, target, *target_args):
    with lock:
        if job["kind"]:
            raise RuntimeError("Уже идёт " + ("обучение" if job["kind"] == "train" else "генерация"))
        job.update(kind=kind, name=name, status="", error="")
        if kind == "train":
            job.update(step=0, total=0, log=[])
        stop_event.clear()
    threading.Thread(target=target, args=target_args, daemon=True).start()


def enqueue(project, indexes=(), body_tasks=(), lora_tasks=()):
    with lock:
        if job["kind"] == "train":
            raise RuntimeError("Идёт обучение: сначала остановите его")
        if job["kind"] == "generate" and job["name"] != project.name:
            raise RuntimeError(f"Идёт генерация для {job['name']}")
        busy = job["kind"] is not None
        if not busy:
            job.update(step=0, total=0, durations=[])
        for index in indexes:
            if (project.name, index) not in queue and running_item != (project.name, index):
                queue.append((project.name, index))
                job["total"] += 1
        body_queue.extend((project.name, *task) for task in body_tasks)
        lora_queue.extend((project.name, *task) for task in lora_tasks)
        job["total"] += len(body_tasks) + len(lora_tasks)
    if not busy:
        start_job("generate", project.name, generation_worker)


def stop():
    stop_event.set()
    with lock:
        queue.clear()
        body_queue.clear()
        lora_queue.clear()
        kind = job["kind"]
    if kind == "generate" and comfy_alive():
        urllib.request.urlopen(urllib.request.Request(f"{args.host}/interrupt", data=b"", method="POST")).close()
    proc = train_proc
    if proc and proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGTERM)


def read_lines(path):
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def body_scales():
    return [{"scale": m[1].strip(), "label": m[2].strip(), "phrase": m[3].strip()}
            for line in read_lines(BODY_SCALES) if (m := SCALE_LINE.match(line))]


def body_types():
    types = []
    for line in read_lines(BODY_TYPES):
        label, _, values = line.partition(":")
        pairs = (pair.split("=", 1) for pair in values.split(";") if "=" in pair)
        types.append({"label": label.strip(), "values": {k.strip(): v.strip() for k, v in pairs}})
    return types


def state(name):
    projects = sorted(p.name for p in DATASETS.iterdir() if p.is_dir()) if DATASETS.exists() else []
    with lock:
        durations = job["durations"]
        # первая картинка идёт дольше всех: ComfyUI загружает модели
        average = sum(durations[1:]) / (len(durations) - 1) if len(durations) > 1 else sum(durations)
        result = {"projects": projects, "body_scales": body_scales(), "body_types": body_types(),
                  "job": {**job, "log": job["log"][-40:], "durations": None, "average": average,
                          "elapsed": time.time() - job["started"] if job["kind"] == "generate" else 0}}
        queued, running = list(queue), running_item
        body_pending = sum(t[0] == name for t in body_queue) + (len(running or ()) == 3 and running[0] == name)
        lora_pending = sum(t[0] == name for t in lora_queue) + (len(running or ()) == 10 and running[0] == name)
    if not name:
        return result
    project = Project(name)
    items = []
    for index, prompt in enumerate(project.prompts(), 1):
        image = project.image(index)
        key = (name, index)
        status = ("running" if key == running else "queued" if key in queued else
                  "error" if key in item_errors else "done" if image.exists() else "empty")
        items.append({"index": index, "prompt": prompt, "status": status, "error": item_errors.get(key, ""),
                      "image": file_url(image) if image.exists() else None})
    runs = sorted(TRAIN_OUTPUT.glob(f"{name}_v*"), key=lambda p: p.stat().st_mtime) if TRAIN_OUTPUT.exists() else []
    samples = sorted((runs[-1] / "samples").glob("*.jpg"))[-6:] if runs else []
    loras = sorted(LORAS.glob(f"{name}_v*.safetensors"))
    generated = []
    for p in reversed(project.generated_images()[-48:]):
        info = p.with_suffix(".json")
        item = {"file": p.name, "url": file_url(p), **(json.loads(info.read_text(encoding="utf-8")) if info.exists() else {})}
        if item.get("ref") and (ref := project.gen_refs / item["ref"]).exists():
            item["ref_url"] = file_url(ref)
        generated.append(item)
    result.update(name=name, trigger=project.trigger(), body_description=project.body_description(), items=items,
                  photos=[{"file": p.name, "url": file_url(p)} for p in project.photos()],
                  body=[{"file": p.name, "url": file_url(p)} for p in project.body_photos()],
                  candidates=[{"file": p.name, "url": file_url(p)} for p in project.body_candidates()],
                  body_pending=body_pending, body_error=item_errors.get((name, "body"), ""),
                  samples=[file_url(p) for p in samples], loras=[p.name for p in loras],
                  all_loras=list(project.loras()), generated=generated, lora_pending=lora_pending,
                  lora_error=item_errors.get((name, "lora"), ""))
    return result


def set_prompt(project, index, prompt):
    prompt = " ".join(prompt.split())
    if not SUBJECT.search(prompt):
        raise ValueError("В промпте должен быть персонаж: the woman from <image1> (или man / person), "
                         "с фигурой: the woman from <image1> with the body from <image2>")
    prompts = project.prompts()
    if not 1 <= index <= len(prompts):
        raise ValueError("Нет такого номера")
    prompts[index - 1] = prompt
    project.save_prompts(prompts)


def decode_image(data_url):
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGB")


def add_photos(project, files, body=False):
    project.ensure()
    folder, prefix = (project.body, f"{project.name}_body") if body else (project.refs, project.name)
    for data_url in files:
        # имя уникально между персонажами: в ComfyUI все загрузки лежат в одной папке input/
        decode_image(data_url).save(next_path(folder, prefix))


def upload_dataset_images(project, files, index=None):
    """Свои картинки в датасет: с index - замена одной картинки, без - новые сцены в конец.
    Промпт сцены становится подписью для обучения."""
    project.ensure()
    with lock:
        if job["kind"] == "train":
            raise RuntimeError("Идёт обучение: сначала остановите его")
        if index is not None and ((project.name, index) == running_item or (project.name, index) in queue):
            raise RuntimeError("Эта картинка сейчас генерируется")
    prompts = project.prompts()
    if index is None:
        indexes = list(range(len(prompts) + 1, len(prompts) + len(files) + 1))
        project.save_prompts(prompts + [f"Photograph of the {project.subject()} from <image1>."] * len(files))
    elif 1 <= index <= len(prompts):
        indexes = [index]
        files = files[:1]
    else:
        raise ValueError("Нет такого номера")
    for i, data_url in zip(indexes, files):
        buffer = io.BytesIO()
        decode_image(data_url).save(buffer, "PNG")
        save_image(project, i, buffer.getvalue())
        item_errors.pop((project.name, i), None)


def handle_post(path, body):
    project = Project(body.get("name", "")) if path != "/api/stop" else None
    if path == "/api/photos":
        add_photos(project, body["files"], body.get("body", False))
    elif path == "/api/photos/delete":
        photo = (project.body if body.get("body") else project.refs) / Path(body["file"]).name
        if photo.exists():
            photo.unlink()
    elif path == "/api/upload":
        upload_dataset_images(project, body["files"], int(body["index"]) if body.get("index") else None)
    elif path == "/api/trigger":
        project.ensure()
        (project.dir / "trigger.txt").write_text(" ".join(body["trigger"].split()) + "\n", encoding="utf-8")
    elif path == "/api/body/description":
        project.ensure()
        (project.dir / "body.txt").write_text(" ".join(body["description"].split()) + "\n", encoding="utf-8")
    elif path == "/api/prompt":
        set_prompt(project, int(body["index"]), body["prompt"])
    elif path == "/api/regenerate":
        set_prompt(project, int(body["index"]), body["prompt"])
        if not project.photos():
            raise ValueError("Сначала загрузите фото персонажа")
        enqueue(project, [int(body["index"])])
    elif path == "/api/generate":
        if not project.photos():
            raise ValueError("Сначала загрузите фото персонажа")
        project.ensure()
        enqueue(project, [i for i in range(1, len(project.prompts()) + 1) if not project.image(i).exists()])
    elif path == "/api/train":
        if not project.trigger():
            raise ValueError("Введите ключевое слово для LoRA")
        if len(project.done()) < MIN_IMAGES:
            raise ValueError(f"Нужно хотя бы {MIN_IMAGES} готовых фото в датасете")
        start_job("train", project.name, training_worker, project)
    elif path == "/api/body/generate":
        description = " ".join(body["description"].split()).rstrip(".,")
        if not description:
            raise ValueError("Опишите фигуру")
        project.ensure()
        prompt = BODY_FRONT.format(subject=project.subject(), description=description)
        enqueue(project, body_tasks=[(prompt, None)] * min(int(body.get("count", 4)), 8))
    elif path == "/api/body/views":
        source = project.candidates / Path(body["file"]).name
        if not source.exists():
            raise LookupError(source.name)
        enqueue(project, body_tasks=[(BODY_VIEW.format(view=view), source) for view in BODY_VIEWS])
    elif path == "/api/body/use":
        shutil.copy2(project.candidates / Path(body["file"]).name, next_path(project.body, f"{project.name}_body"))
    elif path == "/api/body/delete":
        candidate = project.candidates / Path(body["file"]).name
        if candidate.exists():
            candidate.unlink()
    elif path == "/api/lora/generate":
        prompt = " ".join(body["prompt"].split())
        if not prompt:
            raise ValueError("Введите промпт")
        source = project.loras().get(body.get("lora", ""))
        if not source:
            raise ValueError("Выберите LoRA")
        size = (int(body["width"]), int(body["height"]))
        if size not in SIZES:
            raise ValueError("Недопустимый размер")
        if source.parent != LORAS:  # промежуточное сохранение обучения: ComfyUI видит только свою папку
            shutil.copy2(source, LORAS / source.name)
        nsfw = body.get("nsfw")
        if nsfw in (None, ""):
            nsfw = args.nsfw_lora if NUDE.search(prompt) else args.lora
        skin = float(body.get("skin") or 0)
        if skin and not (LORAS / SKIN_LORA).exists():
            raise ValueError(f"Нет LoRA кожи ComfyUI/models/loras/{SKIN_LORA}: скачайте профилем setup")
        ref = None
        if body.get("ref"):
            # имя уникально между персонажами: в ComfyUI все загрузки лежат в одной папке input/
            path = next_path(project.gen_refs, f"{project.name}_genref")
            decode_image(body["ref"]).save(path)
            ref = path.name
        denoise = None
        if ref and body.get("mode") != "edit":
            denoise = float(body.get("denoise") or 0.65)
            if not 0 < denoise <= 1:
                raise ValueError("Сила перерисовки: от 0 до 1")
        task = (prompt, source.name, float(body.get("strength", 1.0)), float(nsfw), skin, *size, ref, denoise)
        enqueue(project, lora_tasks=[task] * min(int(body.get("count", 1)), 8))
    elif path == "/api/lora/delete":
        image = project.generated / Path(body["file"]).name
        image.unlink(missing_ok=True)
        image.with_suffix(".json").unlink(missing_ok=True)
    elif path == "/api/stop":
        stop()
    else:
        raise LookupError(path)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, code, data, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj, code=200):
        self.send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def respond(self, action):
        try:
            action()
        except LookupError:
            self.send_json({"error": "не найдено"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 400)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = dict(urllib.parse.parse_qsl(url.query))
        if url.path == "/":
            self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/state":
            self.respond(lambda: self.send_json(state(query.get("name", "").strip())))
        elif url.path == "/file":
            self.respond(lambda: self.send_file(query.get("path", "")))
        else:
            self.send_json({"error": "не найдено"}, 404)

    def send_file(self, rel):
        path = (ROOT / rel).resolve()
        if not any(path.is_relative_to(d.resolve()) for d in (DATASETS, TRAIN_OUTPUT)) or not path.is_file():
            raise LookupError(rel)
        self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        self.respond(lambda: (handle_post(urllib.parse.urlparse(self.path).path, body), self.send_json({"ok": True})))


def main():
    global args
    # консоль Windows может быть не в UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="local", choices=["local", "server"])
    parser.add_argument("--lora", type=float, default=0.0, help="NSFW LoRA при генерации датасета, по умолчанию выключен")
    parser.add_argument("--nsfw-lora", type=float, default=0.9, help="NSFW LoRA для сцен с nude/naked в промпте")
    parser.add_argument("--clothed-lora", type=float, default=0.5, help="NSFW LoRA для одетых сцен с фото фигуры <image2>")
    parser.add_argument("--host", default="http://127.0.0.1:8188", help="адрес ComfyUI")
    parser.add_argument("--port", type=int, default=8190)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"LoRA studio: http://127.0.0.1:{args.port}  (Ctrl+C - выход)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop()
        stop_comfy()


if __name__ == "__main__":
    main()
