import { Injectable } from '@nestjs/common';
import { randomInt } from 'node:crypto';
import { CharactersService } from '../characters/characters.service';
import { ComfyClient } from '../comfy/comfy.client';
import { ImagesService } from '../images/images.service';
import { JobsService } from '../jobs/jobs.service';
import { buildVideoWorkflow, framesFor, withGeneratedFirstFrame } from '../workflows/video.workflow';
import { WorkflowTemplates } from '../workflows/workflow.templates';
import { CreateVideoDto } from './dto/create-video.dto';

export interface VideoFrames {
  firstFrame?: Express.Multer.File;
  lastFrame?: Express.Multer.File;
}

@Injectable()
export class VideosService {
  constructor(
    private readonly comfy: ComfyClient,
    private readonly characters: CharactersService,
    private readonly images: ImagesService,
    private readonly templates: WorkflowTemplates,
    private readonly jobs: JobsService,
  ) {}

  async create(dto: CreateVideoDto, frames: VideoFrames) {
    const seed = dto.seed ?? randomInt(2 ** 47);
    const { prompt, loras } = dto.character
      ? await this.characters.forVideo(dto.character, dto.prompt)
      : { prompt: dto.prompt, loras: [] };
    const [firstFrame, lastFrame] = await Promise.all([
      frames.firstFrame && this.comfy.uploadImage(frames.firstFrame),
      frames.lastFrame && this.comfy.uploadImage(frames.lastFrame),
    ]);
    let workflow = buildVideoWorkflow(this.templates.video, {
      ...dto,
      prompt,
      loras,
      style: dto.style ?? (dto.mode === 'anime' ? 1 : undefined),
      seed,
      firstFrame,
      lastFrame,
    });
    if (dto.character && !firstFrame) {
      // первый кадр рисует Qwen в том же задании, размером с видео
      const frame = await this.images.workflow({
        prompt: dto.frame_prompt ?? dto.prompt,
        character: dto.character,
        mode: dto.mode,
        width: dto.width,
        height: dto.height,
        seed,
      });
      workflow = withGeneratedFirstFrame(workflow, frame);
    }
    const job = await this.jobs.queue(workflow);
    return { ...job, seed, frames: framesFor(dto.seconds) };
  }
}
