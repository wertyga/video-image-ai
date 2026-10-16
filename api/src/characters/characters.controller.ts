import {
  BadRequestException,
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Patch,
  Post,
  StreamableFile,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { imageUploadOptions } from '../common/image-upload';
import { CharactersService } from './characters.service';
import { CreateCharacterDto, UpdateCharacterDto } from './dto/character.dto';

@Controller('characters')
export class CharactersController {
  constructor(private readonly characters: CharactersService) {}

  /** multipart: портрет `portrait` + поля персонажа. */
  @Post()
  @UseInterceptors(FileInterceptor('portrait', imageUploadOptions(1)))
  create(@Body() dto: CreateCharacterDto, @UploadedFile() portrait?: Express.Multer.File) {
    if (!portrait) throw new BadRequestException('Нужна картинка portrait');
    return this.characters.create(dto, portrait);
  }

  @Get()
  list() {
    return this.characters.list();
  }

  @Get(':id')
  get(@Param('id') id: string) {
    return this.characters.get(id);
  }

  @Get(':id/portrait')
  async portrait(@Param('id') id: string) {
    const { buffer, type } = await this.characters.portrait(id);
    return new StreamableFile(buffer, { type });
  }

  /** Например, подключить обученную LoRA: {"image_lora": "...", "trigger": "ohwx woman"} */
  @Patch(':id')
  update(@Param('id') id: string, @Body() dto: UpdateCharacterDto) {
    return this.characters.update(id, dto);
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  remove(@Param('id') id: string) {
    return this.characters.remove(id);
  }
}
