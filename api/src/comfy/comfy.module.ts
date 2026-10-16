import { Module } from '@nestjs/common';
import { ComfyClient } from './comfy.client';

@Module({
  providers: [ComfyClient],
  exports: [ComfyClient],
})
export class ComfyModule {}
