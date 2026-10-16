import { Module } from '@nestjs/common';
import { CharactersModule } from '../characters/characters.module';
import { JobsModule } from '../jobs/jobs.module';
import { WorkflowsModule } from '../workflows/workflows.module';
import { ImagesController } from './images.controller';
import { ImagesService } from './images.service';

@Module({
  imports: [CharactersModule, JobsModule, WorkflowsModule],
  controllers: [ImagesController],
  providers: [ImagesService],
  exports: [ImagesService],
})
export class ImagesModule {}
