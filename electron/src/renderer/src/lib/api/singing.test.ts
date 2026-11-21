import { expect, it } from 'vitest';
import { singingExportRequest } from './singing';

it('builds a project-scoped export path and a safe suggested filename per container format', () => {
  for (const format of ['wav', 'm4a', 'mp3', 'flac'] as const) {
    const request = singingExportRequest('p1', format);
    expect(request.path).toBe(`/singing/projects/p1/export/${format}`);
    expect(request.name).toBe(`voicestudio-singing-p1.${format}`);
  }
});

it('sanitizes an unsafe project id out of the suggested filename but keeps it in the path', () => {
  const request = singingExportRequest('../weird id/p1', 'wav');
  expect(request.path).toBe('/singing/projects/..%2Fweird%20id%2Fp1/export/wav');
  expect(request.name).toBe('voicestudio-singing-___weird_id_p1.wav');
});
