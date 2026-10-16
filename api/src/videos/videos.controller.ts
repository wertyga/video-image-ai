import { Body, Controller, HttpCode, HttpStatus, Post, UploadedFiles, UseInterceptors } from '@nestjs/common';
import { FileFieldsInterceptor } from '@nestjs/platform-express';
import { imageUploadOptions } from '../common/image-upload';
import { CreateVideoDto } from './dto/create-video.dto';
import { VideosService } from './videos.service';

@Controller('videos')
export class VideosController {
  constructor(private readonly videos: VideosService) {}

  /** Ставит видео в очередь и сразу отвечает id; готовность проверять через GET /jobs/:id. */
  @Post()
  @HttpCode(HttpStatus.ACCEPTED)
  @UseInterceptors(
    FileFieldsInterceptor(
      [
        { name: 'first_frame', maxCount: 1 },
        { name: 'last_frame', maxCount: 1 },
      ],
      imageUploadOptions(2),
    ),
  )
  create(
    @Body() dto: CreateVideoDto,
    @UploadedFiles() files: { first_frame?: Express.Multer.File[]; last_frame?: Express.Multer.File[] } = {},
  ) {
    return this.videos.create(dto, { firstFrame: files.first_frame?.[0], lastFrame: files.last_frame?.[0] });
  }
}
