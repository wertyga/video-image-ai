import { Body, Controller, HttpCode, HttpStatus, Post, UseInterceptors } from '@nestjs/common';
import { NoFilesInterceptor } from '@nestjs/platform-express';
import { CreateImageDto } from './dto/create-image.dto';
import { ImagesService } from './images.service';

@Controller('images')
export class ImagesController {
  constructor(private readonly images: ImagesService) {}

  /** Ставит картинку в очередь; готовность проверять через GET /jobs/:id. */
  @Post()
  @HttpCode(HttpStatus.ACCEPTED)
  @UseInterceptors(NoFilesInterceptor())
  create(@Body() dto: CreateImageDto) {
    return this.images.create(dto);
  }
}
