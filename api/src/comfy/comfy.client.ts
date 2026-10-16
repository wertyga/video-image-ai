import { BadGatewayException, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { randomUUID } from 'node:crypto';
import { extname } from 'node:path';
import { Readable } from 'node:stream';
import { AppConfig } from '../config';

export interface ComfyFile {
  filename: string;
  subfolder: string;
  type: string;
}

export type UploadFile = Pick<Express.Multer.File, 'buffer' | 'mimetype' | 'originalname'>;

export interface ComfyHistoryEntry {
  status?: { status_str?: string; completed?: boolean; messages?: unknown[] };
  outputs?: Record<string, Record<string, unknown>>;
}

/** Тонкий клиент HTTP API ComfyUI: /prompt, /queue, /history, /upload/image, /view. */
@Injectable()
export class ComfyClient {
  private readonly logger = new Logger(ComfyClient.name);
  private readonly baseUrl: string;

  constructor(config: ConfigService<AppConfig, true>) {
    this.baseUrl = config.get('COMFY_URL', { infer: true });
  }

  async queuePrompt(workflow: object): Promise<string> {
    const result = await this.request<{ prompt_id: string }>('/prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: workflow }),
    });
    return result.prompt_id;
  }

  /**
   * Загружает картинку. Без `name` — под случайным именем, чтобы параллельные запросы не затирали друг друга;
   * с `name` — перезаписывает файл (портрет персонажа).
   */
  async uploadImage(file: UploadFile, name?: string): Promise<string> {
    const form = new FormData();
    const fileName = name ?? `api_${randomUUID()}${extname(file.originalname).toLowerCase() || '.png'}`;
    form.append('image', new Blob([new Uint8Array(file.buffer)], { type: file.mimetype }), fileName);
    if (name) form.append('overwrite', 'true');
    const result = await this.request<{ name: string; subfolder?: string }>('/upload/image', {
      method: 'POST',
      body: form,
    });
    return result.subfolder ? `${result.subfolder}/${result.name}` : result.name;
  }

  async getHistory(promptId: string): Promise<ComfyHistoryEntry | undefined> {
    const history = await this.request<Record<string, ComfyHistoryEntry>>(`/history/${encodeURIComponent(promptId)}`);
    return history[promptId];
  }

  /** Позиция в очереди: 'running', 'pending' или undefined, если задания там нет. */
  async getQueueState(promptId: string): Promise<'running' | 'pending' | undefined> {
    // элементы очереди: [номер, prompt_id, workflow, ...]
    const queue = await this.request<{ queue_running: unknown[][]; queue_pending: unknown[][] }>('/queue');
    if (queue.queue_running.some((item) => item[1] === promptId)) return 'running';
    if (queue.queue_pending.some((item) => item[1] === promptId)) return 'pending';
    return undefined;
  }

  async openFile(file: ComfyFile): Promise<{ stream: Readable; contentType: string; size?: number }> {
    const query = new URLSearchParams({ filename: file.filename, subfolder: file.subfolder, type: file.type });
    const response = await this.fetch(`/view?${query}`);
    if (!response.body) throw new BadGatewayException('ComfyUI вернул пустой файл');
    const size = Number(response.headers.get('content-length')) || undefined;
    return {
      stream: Readable.fromWeb(response.body as import('node:stream/web').ReadableStream),
      contentType: response.headers.get('content-type') ?? 'application/octet-stream',
      size,
    };
  }

  async isAlive(): Promise<boolean> {
    try {
      await this.request('/system_stats');
      return true;
    } catch {
      return false;
    }
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await this.fetch(path, init);
    return (await response.json()) as T;
  }

  private async fetch(path: string, init?: RequestInit): Promise<Response> {
    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, init);
    } catch (error) {
      this.logger.error(`ComfyUI недоступен: ${(error as Error).message}`);
      throw new BadGatewayException('ComfyUI недоступен');
    }
    if (!response.ok) {
      const text = await response.text();
      this.logger.error(`ComfyUI ${path}: ${response.status} ${text.slice(0, 2000)}`);
      throw new BadGatewayException({ message: 'ComfyUI отклонил запрос', status: response.status, detail: safeJson(text) });
    }
    return response;
  }
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text.slice(0, 2000);
  }
}
