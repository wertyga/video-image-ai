import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { ApiTokenGuard } from './auth/api-token.guard';
import { CharactersModule } from './characters/characters.module';
import { ComfyModule } from './comfy/comfy.module';
import { validateConfig } from './config';
import { HealthController } from './health/health.controller';
import { ImagesModule } from './images/images.module';
import { JobsModule } from './jobs/jobs.module';
import { VideosModule } from './videos/videos.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true, validate: validateConfig }),
    // 60 запросов в минуту с одного IP: опрос статуса раз в 5 с укладывается с запасом
    ThrottlerModule.forRoot([{ ttl: 60_000, limit: 60 }]),
    ComfyModule,
    JobsModule,
    CharactersModule,
    ImagesModule,
    VideosModule,
  ],
  controllers: [HealthController],
  providers: [
    { provide: APP_GUARD, useClass: ThrottlerGuard },
    { provide: APP_GUARD, useClass: ApiTokenGuard },
  ],
})
export class AppModule {}
