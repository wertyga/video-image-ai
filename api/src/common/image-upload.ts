import { BadRequestException } from '@nestjs/common';
import type { MulterOptions } from '@nestjs/platform-express/multer/interfaces/multer-options.interface';

const IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);

/** Картинки png/jpeg/webp до 20 МБ. */
export function imageUploadOptions(files: number): MulterOptions {
  return {
    limits: { fileSize: 20 * 1024 * 1024, files },
    fileFilter: (_req, file, callback) =>
      IMAGE_TYPES.has(file.mimetype)
        ? callback(null, true)
        : callback(new BadRequestException('Картинки только png, jpeg или webp'), false),
  };
}
