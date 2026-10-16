import {
  BadRequestException,
  ConflictException,
  Injectable,
  NotFoundException,
  OnModuleInit,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { ComfyClient } from '../comfy/comfy.client';
import { AppConfig } from '../config';
import { insertCharacter, LoraRef } from '../workflows/workflow';
import { CreateCharacterDto, UpdateCharacterDto } from './dto/character.dto';

const EXTENSIONS: Record<string, string> = { 'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp' };

export interface Character {
  id: string;
  subject: string;
  image_lora?: string;
  video_lora?: string;
  trigger?: string;
  strength?: number;
  portrait: string;
  portrait_type: string;
  created_at: string;
}

/** Как персонаж попадает в workflow: LoRA с триггером или портрет в режиме edit. */
export interface CharacterInput {
  prompt: string;
  loras: LoraRef[];
  images: string[];
}

/** Персонажи лежат в DATA_DIR/characters: <id>.json и портрет рядом. */
@Injectable()
export class CharactersService implements OnModuleInit {
  private readonly dir: string;

  constructor(
    private readonly comfy: ComfyClient,
    config: ConfigService<AppConfig, true>,
  ) {
    this.dir = join(config.get('DATA_DIR', { infer: true }), 'characters');
  }

  async onModuleInit() {
    await mkdir(this.dir, { recursive: true });
  }

  async list(): Promise<Character[]> {
    const files = (await readdir(this.dir)).filter((file) => file.endsWith('.json'));
    return Promise.all(files.map((file) => this.get(file.slice(0, -'.json'.length))));
  }

  async get(id: string): Promise<Character> {
    try {
      return JSON.parse(await readFile(this.path(id), 'utf-8'));
    } catch {
      throw new NotFoundException(`Персонаж ${id} не найден`);
    }
  }

  async create(dto: CreateCharacterDto, portrait: Express.Multer.File): Promise<Character> {
    if (await this.exists(dto.id)) throw new ConflictException(`Персонаж ${dto.id} уже есть`);
    const character: Character = {
      subject: 'the person',
      ...defined(dto),
      id: dto.id,
      portrait: `${dto.id}${EXTENSIONS[portrait.mimetype]}`,
      portrait_type: portrait.mimetype,
      created_at: new Date().toISOString(),
    };
    validate(character);
    await writeFile(join(this.dir, character.portrait), portrait.buffer);
    await this.save(character);
    return character;
  }

  async update(id: string, dto: UpdateCharacterDto): Promise<Character> {
    const character = { ...(await this.get(id)), ...defined(dto) };
    validate(character);
    await this.save(character);
    return character;
  }

  async remove(id: string) {
    const character = await this.get(id);
    await Promise.all([rm(this.path(id)), rm(join(this.dir, character.portrait), { force: true })]);
  }

  async portrait(id: string) {
    const character = await this.get(id);
    return { buffer: await readFile(join(this.dir, character.portrait)), type: character.portrait_type };
  }

  /** Картинка: с LoRA — триггер в промпте, без неё — портрет как <image1> в режиме edit. */
  async forImage(id: string, prompt: string): Promise<CharacterInput> {
    const character = await this.get(id);
    if (character.image_lora) {
      return {
        prompt: insertCharacter(prompt, character.trigger!),
        loras: [{ name: character.image_lora, strength: character.strength ?? 1 }],
        images: [],
      };
    }
    const { buffer, type } = await this.portrait(id);
    // постоянное имя: повторная загрузка перезаписывает файл, а не копит копии
    const image = await this.comfy.uploadImage(
      { buffer, mimetype: type, originalname: character.portrait },
      `character_${character.portrait}`,
    );
    return { prompt: insertCharacter(prompt, `${character.subject} from <image1>`), loras: [], images: [image] };
  }

  /** Видео: с LoRA — триггер, без неё лицо задаёт первый кадр, а {character} заменяется на subject. */
  async forVideo(id: string, prompt: string): Promise<CharacterInput> {
    const character = await this.get(id);
    if (character.video_lora) {
      return {
        prompt: insertCharacter(prompt, character.trigger!),
        loras: [{ name: character.video_lora, strength: character.strength ?? 1 }],
        images: [],
      };
    }
    return { prompt: insertCharacter(prompt, character.subject, false), loras: [], images: [] };
  }

  private path(id: string) {
    if (!/^[a-z0-9_-]{1,64}$/.test(id)) throw new NotFoundException(`Персонаж ${id} не найден`);
    return join(this.dir, `${id}.json`);
  }

  private async exists(id: string) {
    return readFile(this.path(id)).then(
      () => true,
      () => false,
    );
  }

  private save(character: Character) {
    return writeFile(this.path(character.id), JSON.stringify(character, null, 2));
  }
}

/** Непереданные поля DTO приходят как undefined и затёрли бы сохранённые значения. */
function defined<T extends object>(dto: T): Partial<T> {
  return Object.fromEntries(Object.entries(dto).filter(([, value]) => value !== undefined)) as Partial<T>;
}

function validate(character: Character) {
  if ((character.image_lora || character.video_lora) && !character.trigger) {
    throw new BadRequestException('Для LoRA персонажа нужен trigger');
  }
}
