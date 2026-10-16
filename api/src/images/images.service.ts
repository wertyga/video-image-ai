import { BadRequestException, Injectable } from '@nestjs/common';
import { randomInt } from 'node:crypto';
import { CharactersService } from '../characters/characters.service';
import { JobsService } from '../jobs/jobs.service';
import { ANIME_STYLE, buildImageWorkflow } from '../workflows/image.workflow';
import { Workflow } from '../workflows/workflow';
import { WorkflowTemplates } from '../workflows/workflow.templates';
import { CreateImageDto } from './dto/create-image.dto';

export type ImageRequest = Omit<CreateImageDto, 'seed'> & { seed: number };

@Injectable()
export class ImagesService {
  constructor(
    private readonly characters: CharactersService,
    private readonly templates: WorkflowTemplates,
    private readonly jobs: JobsService,
  ) {}

  async create(dto: CreateImageDto) {
    const seed = dto.seed ?? randomInt(2 ** 47);
    const job = await this.jobs.queue(await this.workflow({ ...dto, seed }));
    return { ...job, seed };
  }

  /** Также нужен видео: первый кадр с персонажем. */
  async workflow(request: ImageRequest): Promise<Workflow> {
    if ((request.width === undefined) !== (request.height === undefined)) {
      throw new BadRequestException('width и height задаются вместе');
    }
    const { prompt, loras, images } = request.character
      ? await this.characters.forImage(request.character, request.prompt)
      : { prompt: request.prompt, loras: [], images: [] };
    return buildImageWorkflow(this.templates.image, {
      ...request,
      prompt: request.mode === 'anime' ? `${ANIME_STYLE} ${prompt}` : prompt,
      loras,
      images,
    });
  }
}
