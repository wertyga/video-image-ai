import { Type } from 'class-transformer';
import { IsIn, IsInt, IsNumber, IsOptional, IsString, Max, MaxLength, Min, MinLength } from 'class-validator';
import { Mode, MODES } from '../../workflows/workflow';

/** Поля multipart/form-data (или JSON без картинок). Значения те же, что у scripts/generate_video.py. */
export class CreateVideoDto {
  @IsString()
  @MinLength(1)
  @MaxLength(20000)
  prompt: string;

  /** id персонажа из /characters; без first_frame первый кадр с ним рисует Qwen */
  @IsOptional()
  @IsString()
  character?: string;

  /** Промпт для первого кадра с персонажем; по умолчанию prompt */
  @IsOptional()
  @IsString()
  @MinLength(1)
  @MaxLength(20000)
  frame_prompt?: string;

  /** anime включает Digital Art LoRA с силой style (по умолчанию 1) */
  @IsOptional()
  @IsIn(MODES)
  mode: Mode = 'nsfw';

  /** Модель обучена на ~5-15 с */
  @IsOptional()
  @Type(() => Number)
  @IsNumber()
  @Min(1)
  @Max(20)
  seconds: number = 5;

  /** Кратно 32 */
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(256)
  @Max(1920)
  width: number = 1344;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(256)
  @Max(1920)
  height: number = 768;

  /** 8 с turbo LoRA */
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(50)
  steps?: number;

  /** Сила NSFW LoRA, автор советует 0.3-1 */
  @IsOptional()
  @Type(() => Number)
  @IsNumber()
  @Min(0)
  @Max(2)
  lora?: number;

  /** Сила Digital Art LoRA (рисованный стиль), 0.8-1.5; без поля стиль выключен (в режиме anime — 1) */
  @IsOptional()
  @Type(() => Number)
  @IsNumber()
  @Min(0)
  @Max(2)
  style?: number;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(0)
  @Max(2 ** 48)
  seed?: number;
}
