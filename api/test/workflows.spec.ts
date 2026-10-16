import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { buildImageWorkflow } from '../src/workflows/image.workflow';
import {
  buildVideoWorkflow,
  framesFor,
  STYLE_LORA,
  STYLE_TRIGGER,
  withGeneratedFirstFrame,
} from '../src/workflows/video.workflow';
import { insertCharacter } from '../src/workflows/workflow';
import { WORKFLOWS_DIR } from '../src/workflows/workflow.templates';

const load = (file: string) => JSON.parse(readFileSync(join(WORKFLOWS_DIR, file), 'utf-8'));
const videoTemplate = load('h3_nsfw_server.json');
const imageTemplate = load('qwen21_nsfw_server.json');
const video = { prompt: 'a cat', seconds: 5, width: 768, height: 1344, seed: 42 };

describe('framesFor', () => {
  it('округляет вверх до сетки 17k+5', () => {
    expect(framesFor(5)).toBe(124);
    expect(framesFor(6)).toBe(158);
    expect(framesFor(8)).toBe(192);
    expect(framesFor(10)).toBe(243);
    expect(framesFor(0.1)).toBe(5);
  });
});

describe('buildVideoWorkflow', () => {
  it('подставляет промпт, размер, длину и seed, не трогая шаблон', () => {
    const workflow = buildVideoWorkflow(videoTemplate, video);
    expect(workflow['7'].inputs).toMatchObject({ prompt: 'a cat', width: 768, height: 1344, length: 124 });
    expect(workflow['8'].inputs.noise_seed).toBe(42);
    expect(workflow['10'].inputs.model).toEqual(['3', 0]);
    expect(videoTemplate['7'].inputs.prompt).toBe('');
    expect(workflow['7'].inputs.first_frame).toBeUndefined();
  });

  it('добавляет стилевую LoRA и триггер', () => {
    const workflow = buildVideoWorkflow(videoTemplate, { ...video, style: 1.2 });
    expect(workflow['30'].inputs).toMatchObject({ model: ['3', 0], lora_name: STYLE_LORA, strength_model: 1.2 });
    expect(workflow['10'].inputs.model).toEqual(['30', 0]);
    expect(workflow['11'].inputs.model).toEqual(['30', 0]);
    expect(workflow['7'].inputs.prompt).toBe(`${STYLE_TRIGGER}. a cat`);
  });

  it('ставит LoRA персонажа перед стилевой', () => {
    const workflow = buildVideoWorkflow(videoTemplate, { ...video, style: 1, loras: [{ name: 'me.safetensors', strength: 1 }] });
    expect(workflow['30'].inputs).toMatchObject({ model: ['3', 0], lora_name: 'me.safetensors' });
    expect(workflow['31'].inputs).toMatchObject({ model: ['30', 0], lora_name: STYLE_LORA });
    expect(workflow['11'].inputs.model).toEqual(['31', 0]);
  });

  it('подключает первый и последний кадр, LoRA и шаги', () => {
    const workflow = buildVideoWorkflow(videoTemplate, { ...video, firstFrame: 'a.png', lastFrame: 'b.png', lora: 0.8, steps: 12 });
    expect(workflow['20']).toEqual({ class_type: 'LoadImage', inputs: { image: 'a.png' } });
    expect(workflow['7'].inputs.first_frame).toEqual(['20', 0]);
    expect(workflow['7'].inputs.last_frame).toEqual(['21', 0]);
    expect(workflow['3'].inputs.strength_model).toBe(0.8);
    expect(workflow['10'].inputs.steps).toBe(12);
  });
});

describe('buildImageWorkflow', () => {
  it('text-to-image: промпт, размер, seed, LoRA персонажа после NSFW', () => {
    const workflow = buildImageWorkflow(imageTemplate, {
      prompt: 'ohwx woman',
      width: 832,
      height: 1216,
      seed: 7,
      loras: [{ name: 'me.safetensors', strength: 0.9 }],
    });
    expect(workflow['5'].inputs.prompt).toBe('ohwx woman');
    expect(workflow['6'].inputs).toMatchObject({ width: 832, height: 1216 });
    expect(workflow['30'].inputs).toMatchObject({ model: ['2', 0], lora_name: 'me.safetensors', strength_model: 0.9 });
    expect(workflow['7'].inputs).toMatchObject({ model: ['30', 0], seed: 7, latent_image: ['6', 0] });
    expect(workflow['5'].inputs.vae).toBeUndefined();
  });

  it('edit: портрет как <image1>, латент его размера', () => {
    const workflow = buildImageWorkflow(imageTemplate, { prompt: 'x', seed: 1, images: ['p.png'] });
    expect(workflow['20']).toEqual({ class_type: 'LoadImage', inputs: { image: 'p.png' } });
    expect(workflow['5'].inputs).toMatchObject({ vae: ['4', 0], 'images.image_1': ['20', 0] });
    expect(workflow['7'].inputs.latent_image).toEqual(['5', 2]);
    expect(workflow['6']).toBeUndefined();
  });

  it('edit с размером: пустой латент заданного размера', () => {
    const workflow = buildImageWorkflow(imageTemplate, { prompt: 'x', seed: 1, images: ['p.png'], width: 1344, height: 768 });
    expect(workflow['7'].inputs.latent_image).toEqual(['6', 0]);
    expect(workflow['6'].inputs).toMatchObject({ width: 1344, height: 768 });
  });
});

describe('withGeneratedFirstFrame', () => {
  it('сливает граф картинки в видео без конфликтов id', () => {
    const image = buildImageWorkflow(imageTemplate, { prompt: 'x', seed: 1, images: ['p.png'], width: 768, height: 1344 });
    const workflow = withGeneratedFirstFrame(buildVideoWorkflow(videoTemplate, video), image);
    expect(workflow['7'].inputs.first_frame).toEqual(['frame_8', 0]);
    expect(workflow['frame_9']).toBeUndefined();
    expect(workflow['frame_7'].inputs).toMatchObject({ model: ['frame_2', 0], positive: ['frame_5', 0] });
    expect(workflow['frame_5'].inputs['images.image_1']).toEqual(['frame_20', 0]);
    expect(workflow['3'].class_type).toBe('LoraLoaderModelOnly');
    // все ссылки ведут на существующие узлы
    for (const node of Object.values(workflow)) {
      for (const value of Object.values(node.inputs)) {
        if (Array.isArray(value) && typeof value[0] === 'string') expect(workflow[value[0]]).toBeDefined();
      }
    }
  });
});

describe('insertCharacter', () => {
  it('заменяет {character} или дописывает в начало', () => {
    expect(insertCharacter('photo of {character} in a cafe', 'ohwx woman')).toBe('photo of ohwx woman in a cafe');
    expect(insertCharacter('in a cafe', 'the woman from <image1>')).toBe('the woman from <image1>, in a cafe');
    expect(insertCharacter('she walks', 'the woman', false)).toBe('she walks');
  });
});
