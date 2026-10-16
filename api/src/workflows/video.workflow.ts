import { IMAGE_DECODE_NODE, IMAGE_SAVE_NODE } from './image.workflow';
import { chainLoras, LoraRef, prefixNodes, Workflow } from './workflow';

export const FPS = 24;
export const STYLE_LORA = 'minimax_h3_digital_art_v3.safetensors';
export const STYLE_TRIGGER = 'flat cel shading, bold outlines, multi colors';
export const FRAME_PREFIX = 'frame_';

/** Модель принимает длину 17k+5 кадров: округляем вверх, как официальный шаблон. */
export function framesFor(seconds: number): number {
  const n = Math.max(5, Math.round(seconds * FPS));
  return n + ((((5 - (n % 17)) % 17) + 17) % 17);
}

export interface VideoParams {
  prompt: string;
  seconds: number;
  width: number;
  height: number;
  seed: number;
  steps?: number;
  /** Сила NSFW LoRA */
  lora?: number;
  /** Сила Digital Art LoRA; без поля стиль выключен */
  style?: number;
  /** Дополнительные LoRA (персонаж) между NSFW и стилевой */
  loras?: LoraRef[];
  firstFrame?: string;
  lastFrame?: string;
}

/** Повторяет сборку workflow из scripts/generate_video.py. */
export function buildVideoWorkflow(template: Workflow, params: VideoParams): Workflow {
  const workflow: Workflow = structuredClone(template);
  const video = workflow['7'].inputs;
  let prompt = params.prompt;
  const loras = [...(params.loras ?? [])];
  if (params.style !== undefined) {
    loras.push({ name: STYLE_LORA, strength: params.style });
    prompt = `${STYLE_TRIGGER}. ${prompt}`;
  }
  workflow['10'].inputs.model = workflow['11'].inputs.model = chainLoras(workflow, ['3', 0], loras);
  Object.assign(video, { prompt, width: params.width, height: params.height, length: framesFor(params.seconds) });
  if (params.steps) workflow['10'].inputs.steps = params.steps;
  if (params.lora !== undefined) workflow['3'].inputs.strength_model = params.lora;
  for (const [key, nodeId, image] of [
    ['first_frame', '20', params.firstFrame],
    ['last_frame', '21', params.lastFrame],
  ] as const) {
    if (image) {
      workflow[nodeId] = { class_type: 'LoadImage', inputs: { image } };
      video[key] = [nodeId, 0];
    }
  }
  workflow['8'].inputs.noise_seed = params.seed;
  workflow['16'].inputs.filename_prefix = 'video/api';
  return workflow;
}

/** Сливает workflow картинки с видео: сгенерированный кадр сразу идёт в first_frame, одно задание ComfyUI. */
export function withGeneratedFirstFrame(video: Workflow, image: Workflow): Workflow {
  const frame = prefixNodes(image, FRAME_PREFIX);
  delete frame[FRAME_PREFIX + IMAGE_SAVE_NODE];
  const workflow: Workflow = { ...structuredClone(video), ...frame };
  workflow['7'].inputs.first_frame = [FRAME_PREFIX + IMAGE_DECODE_NODE, 0];
  return workflow;
}
