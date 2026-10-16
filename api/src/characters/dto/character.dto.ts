import { Type } from 'class-transformer';
import { IsNumber, IsOptional, IsString, Matches, Max, MaxLength, Min, MinLength } from 'class-validator';

const LORA_FILE = /^(?!.*\.\.)[\w.\-/]+\.safetensors$/;

/** Поля персонажа (multipart вместе с картинкой `portrait`, при изменении — JSON). */
export class UpdateCharacterDto {
  /** Как назвать персонажа в промпте без LoRA: «the woman» → «the woman from <image1>» */
  @IsOptional()
  @IsString()
  @MinLength(1)
  @MaxLength(100)
  subject?: string;

  /** LoRA персонажа для Qwen (картинки) из ComfyUI/models/loras */
  @IsOptional()
  @Matches(LORA_FILE, { message: 'image_lora: имя .safetensors из ComfyUI/models/loras' })
  image_lora?: string;

  /** LoRA персонажа для MiniMax H3 (видео) из ComfyUI/models/loras */
  @IsOptional()
  @Matches(LORA_FILE, { message: 'video_lora: имя .safetensors из ComfyUI/models/loras' })
  video_lora?: string;

  /** Триггер-слово LoRA, например «ohwx woman» */
  @IsOptional()
  @IsString()
  @MinLength(1)
  @MaxLength(100)
  trigger?: string;

  /** Сила LoRA персонажа, по умолчанию 1 */
  @IsOptional()
  @Type(() => Number)
  @IsNumber()
  @Min(0)
  @Max(2)
  strength?: number;
}

export class CreateCharacterDto extends UpdateCharacterDto {
  /** id персонажа, его передают в поле `character` */
  @Matches(/^[a-z0-9_-]{1,64}$/, { message: 'id: латиница в нижнем регистре, цифры, _ и -, до 64 символов' })
  id: string;
}
