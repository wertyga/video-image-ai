import { Injectable, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { AppConfig } from '../config';
import { Workflow } from './workflow';

export const WORKFLOWS_DIR = join(__dirname, '..', '..', '..', 'workflows');

/** Шаблоны из workflows/ под скачанные профили. */
@Injectable()
export class WorkflowTemplates implements OnModuleInit {
  video: Workflow;
  image: Workflow;

  constructor(private readonly config: ConfigService<AppConfig, true>) {}

  async onModuleInit() {
    const load = async (file: string) => JSON.parse(await readFile(join(WORKFLOWS_DIR, file), 'utf-8')) as Workflow;
    [this.video, this.image] = await Promise.all([
      load(`h3_nsfw_${this.config.get('COMFY_PROFILE', { infer: true })}.json`),
      load(`qwen21_nsfw_${this.config.get('COMFY_IMAGE_PROFILE', { infer: true })}.json`),
    ]);
  }
}
