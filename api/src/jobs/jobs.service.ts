import { Injectable, NotFoundException } from '@nestjs/common';
import { ComfyClient, ComfyFile, ComfyHistoryEntry } from '../comfy/comfy.client';

export type JobStatus = 'queued' | 'running' | 'done' | 'error';

export interface Job {
  id: string;
  status: JobStatus;
  error?: unknown;
  file?: ComfyFile;
}

/** Задания хранит сам ComfyUI: id задания = prompt_id, статус берём из /queue и /history. */
@Injectable()
export class JobsService {
  constructor(private readonly comfy: ComfyClient) {}

  async queue(workflow: object): Promise<{ id: string; status: JobStatus; url: string }> {
    const id = await this.comfy.queuePrompt(workflow);
    return { id, status: 'queued', url: `/jobs/${id}` };
  }

  async get(id: string): Promise<Job> {
    const history = await this.comfy.getHistory(id);
    if (history) return toJob(id, history);
    const state = await this.comfy.getQueueState(id);
    if (state) return { id, status: state === 'running' ? 'running' : 'queued' };
    // задание могло завершиться между двумя запросами: перепроверяем историю
    const finished = await this.comfy.getHistory(id);
    if (finished) return toJob(id, finished);
    throw new NotFoundException('Задание не найдено');
  }

  open(file: ComfyFile) {
    return this.comfy.openFile(file);
  }
}

function toJob(id: string, history: ComfyHistoryEntry): Job {
  if (history.status?.status_str === 'error') {
    return { id, status: 'error', error: history.status.messages };
  }
  for (const output of Object.values(history.outputs ?? {})) {
    for (const items of Object.values(output)) {
      if (!Array.isArray(items)) continue;
      const file = items.find((item): item is ComfyFile => typeof item?.filename === 'string');
      if (file) return { id, status: 'done', file };
    }
  }
  return { id, status: 'error', error: 'ComfyUI завершил задание без файла' };
}
