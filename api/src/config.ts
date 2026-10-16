import { join } from 'node:path';

export interface AppConfig {
  API_TOKEN: string;
  PORT: number;
  COMFY_URL: string;
  COMFY_PROFILE: 'server' | 'server_bf16';
  COMFY_IMAGE_PROFILE: 'server' | 'local';
  DATA_DIR: string;
}

/** Проверка .env при старте: без токена API не запускается. */
export function validateConfig(env: Record<string, unknown>): AppConfig {
  const token = String(env.API_TOKEN ?? '');
  if (token.length < 32) {
    throw new Error('API_TOKEN должен быть не короче 32 символов (openssl rand -hex 32)');
  }
  const profile = String(env.COMFY_PROFILE ?? 'server');
  if (profile !== 'server' && profile !== 'server_bf16') {
    throw new Error('COMFY_PROFILE: server или server_bf16');
  }
  const imageProfile = String(env.COMFY_IMAGE_PROFILE ?? 'server');
  if (imageProfile !== 'server' && imageProfile !== 'local') {
    throw new Error('COMFY_IMAGE_PROFILE: server или local');
  }
  return {
    API_TOKEN: token,
    PORT: Number(env.PORT ?? 8000),
    COMFY_URL: String(env.COMFY_URL ?? 'http://127.0.0.1:8189').replace(/\/$/, ''),
    COMFY_PROFILE: profile,
    COMFY_IMAGE_PROFILE: imageProfile,
    // по умолчанию api/data
    DATA_DIR: String(env.DATA_DIR || join(__dirname, '..', 'data')),
  };
}
