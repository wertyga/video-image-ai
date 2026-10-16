import { Logger, ValidationPipe } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { AppConfig } from './config';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
  app.enableShutdownHooks();

  const port = app.get(ConfigService<AppConfig, true>).get('PORT', { infer: true });
  await app.listen(port, '0.0.0.0');
  Logger.log(`API слушает порт ${port}`, 'Bootstrap');
}

bootstrap();
