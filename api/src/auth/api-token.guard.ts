import { CanActivate, ExecutionContext, Injectable, SetMetadata, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Reflector } from '@nestjs/core';
import { createHash, timingSafeEqual } from 'node:crypto';
import type { Request } from 'express';
import { AppConfig } from '../config';

export const IS_PUBLIC = 'isPublic';
export const Public = () => SetMetadata(IS_PUBLIC, true);

const digest = (value: string) => createHash('sha256').update(value).digest();

/** Bearer-токен из API_TOKEN на всех маршрутах, кроме помеченных @Public(). */
@Injectable()
export class ApiTokenGuard implements CanActivate {
  private readonly expected: Buffer;

  constructor(
    private readonly reflector: Reflector,
    config: ConfigService<AppConfig, true>,
  ) {
    this.expected = digest(config.get('API_TOKEN', { infer: true }));
  }

  canActivate(context: ExecutionContext): boolean {
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC, [context.getHandler(), context.getClass()]);
    if (isPublic) return true;

    const header = context.switchToHttp().getRequest<Request>().headers.authorization ?? '';
    const [scheme, token] = header.split(' ');
    // сравниваем хэши одинаковой длины, чтобы время ответа не выдавало токен
    if (scheme !== 'Bearer' || !token || !timingSafeEqual(digest(token), this.expected)) {
      throw new UnauthorizedException();
    }
    return true;
  }
}
