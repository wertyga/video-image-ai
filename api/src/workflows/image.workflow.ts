import { chainLoras, LoraRef, Workflow } from './workflow';

/** У Qwen нет аниме-LoRA: стиль задаём текстом. */
export const ANIME_STYLE = 'Anime illustration, flat cel shading, bold clean outlines, vibrant colors.';
export const IMAGE_DECODE_NODE = '8';
export const IMAGE_SAVE_NODE = '9';

export interface ImageParams {
  prompt: string;
  negative?: string;
  /** Без размера: 1024×1024 из шаблона, в режиме edit — размер первой картинки. */
  width?: number;
  height?: number;
  seed: number;
  steps?: number;
  cfg?: number;
  /** Сила NSFW LoRA */
  lora?: number;
  loras?: LoraRef[];
  /** Картинки в ComfyUI для режима edit: <image1>, <image2>, ... */
  images?: string[];
}

/** Повторяет сборку workflow из scripts/generate.py (text-to-image и edit). */
export function buildImageWorkflow(template: Workflow, params: ImageParams): Workflow {
  const workflow: Workflow = structuredClone(template);
  const encoder = workflow['5'].inputs;
  const sampler = workflow['7'].inputs;
  encoder.prompt = params.prompt;
  if (params.negative !== undefined) encoder.negative_prompt = params.negative;
  if (params.lora !== undefined) workflow['2'].inputs.strength_model = params.lora;
  sampler.model = chainLoras(workflow, ['2', 0], params.loras ?? []);
  if (params.steps) sampler.steps = params.steps;
  if (params.cfg !== undefined) sampler.cfg = params.cfg;
  sampler.seed = params.seed;

  const images = params.images ?? [];
  images.forEach((image, i) => {
    const id = String(20 + i);
    workflow[id] = { class_type: 'LoadImage', inputs: { image } };
    encoder[`images.image_${i + 1}`] = [id, 0];
  });
  if (images.length) encoder.vae = ['4', 0];

  if (params.width && params.height) {
    Object.assign(workflow['6'].inputs, { width: params.width, height: params.height });
  } else if (images.length) {
    // латент размера <image1>, как в generate.py
    sampler.latent_image = ['5', 2];
    delete workflow['6'];
  }
  workflow[IMAGE_SAVE_NODE].inputs.filename_prefix = 'api/image';
  return workflow;
}
