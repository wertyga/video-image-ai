import { Type } from 'class-transformer';
import { IsIn, IsInt, IsNumber, IsOptional, IsString, Max, MaxLength, Min, MinLength } from 'class-validator';
import { Mode, MODES } from '../../workflows/workflow';

/** Поля JSON или multipart/form-data. Значения те же, что у scripts/generate.py. */
export class CreateImageDto {
  /** {character} — место персонажа в промпте */
  @IsString()
  @MinLength(1)
  @MaxLength(20000)
  prompt: string;

  @IsOptional()
  @IsString()
  @MaxLength(5000)
  negative?: string;

  /** id персонажа из /characters */
  @IsOptional()
  @IsString()
  character?: string;

  @IsOptional()
  @IsIn(MODES)
  mode: Mode = 'nsfw';

  /** Кратно 32, до 2048; без размера 1024×1024, а с персонажем без LoRA — размер портрета */
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(256)
  @Max(2048)
  width?: number;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(256)
  @Max(2048)
  height?: number;

  /** По умолчанию 30 */
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  steps?: number;

  /** По умолчанию 4, автор советует 3-6 */
  @IsOptional()
  @Type(() => Number)
  @IsNumber()
  @Min(0)
  @Max(20)
  cfg?: number;

  /** Сила NSFW LoRA, автор советует 0.8-1.0 */
  @IsOptional()
  @Type(() => Number)
  @IsNumber()
  @Min(0)
  @Max(2)
  lora?: number;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(0)
  @Max(2 ** 48)
  seed?: number;
}
