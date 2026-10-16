import { Module } from '@nestjs/common';
import { CharactersModule } from '../characters/characters.module';
import { ComfyModule } from '../comfy/comfy.module';
import { ImagesModule } from '../images/images.module';
import { JobsModule } from '../jobs/jobs.module';
import { WorkflowsModule } from '../workflows/workflows.module';
import { VideosController } from './videos.controller';
import { VideosService } from './videos.service';

@Module({
  imports: [ComfyModule, CharactersModule, ImagesModule, JobsModule, WorkflowsModule],
  controllers: [VideosController],
  providers: [VideosService],
})
export class VideosModule {}
