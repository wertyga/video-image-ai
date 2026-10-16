import { Controller, Get, ServiceUnavailableException } from '@nestjs/common';
import { Public } from '../auth/api-token.guard';
import { ComfyClient } from '../comfy/comfy.client';

@Controller('health')
export class HealthController {
  constructor(private readonly comfy: ComfyClient) {}

  /** Без токена: API жив и ComfyUI отвечает. */
  @Public()
  @Get()
  async check() {
    if (!(await this.comfy.isAlive())) throw new ServiceUnavailableException({ comfy: 'down' });
    return { status: 'ok', comfy: 'up' };
  }
}
