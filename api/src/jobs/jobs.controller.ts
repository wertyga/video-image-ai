import { ConflictException, Controller, Get, Param, StreamableFile } from '@nestjs/common';
import { JobsService } from './jobs.service';

/** Статус и результат любого задания: картинки или видео. */
@Controller('jobs')
export class JobsController {
  constructor(private readonly jobs: JobsService) {}

  @Get(':id')
  async get(@Param('id') id: string) {
    const { file, ...job } = await this.jobs.get(id);
    return file ? { ...job, url: `/jobs/${id}/file` } : job;
  }

  @Get(':id/file')
  async file(@Param('id') id: string): Promise<StreamableFile> {
    const job = await this.jobs.get(id);
    if (!job.file) throw new ConflictException({ message: 'Результат ещё не готов', status: job.status });
    const { stream, contentType, size } = await this.jobs.open(job.file);
    return new StreamableFile(stream, {
      type: contentType,
      length: size,
      disposition: `attachment; filename="${job.file.filename.replace(/"/g, '')}"`,
    });
  }
}
