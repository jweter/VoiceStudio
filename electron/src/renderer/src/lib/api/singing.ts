import { apiJson } from './client';

/** Singing Mode S5 (docs/projects/singing-mode.md): a dedicated door, never `/generate`. */

export interface SingingEngine {
  id: string;
  display_name: string;
  available: boolean;
  reason: string | null;
}

export interface F0FramePayload {
  time_seconds: number;
  frequency_hz: number | null;
  voiced: boolean;
}

export interface CentsDiffFramePayload {
  time_seconds: number;
  cents: number | null;
}

export interface SingingAnalyzeResult {
  project_id: string;
  guide_audio_url: string;
  guide_f0: F0FramePayload[];
  voiced_segments: { start_seconds: number; end_seconds: number }[];
  guide_duration_seconds: number;
  guide_duration_formatted: string;
  full_render_cap_usage_percent: number;
  full_render_max_seconds_formatted: string;
}

export interface SingingPreviewResult {
  project_id: string;
  guide_audio_url: string;
  preview_audio_url: string;
  guide_f0: F0FramePayload[];
  output_f0: F0FramePayload[];
  cents_diff: CentsDiffFramePayload[];
  duration_seconds: number;
  guide_duration_seconds: number;
  within_tolerance: boolean;
  engine_id: string;
  engine_version: string;
  provenance: Record<string, string> | null;
}

export async function listSingingEngines(signal?: AbortSignal): Promise<SingingEngine[]> {
  return apiJson<SingingEngine[]>('/singing/engines', { signal });
}

export async function analyzeGuideVocal(
  guideVocal: File,
  signal?: AbortSignal,
): Promise<SingingAnalyzeResult> {
  const body = new FormData();
  body.append('guide_vocal', guideVocal);
  return apiJson<SingingAnalyzeResult>('/singing/analyze', { method: 'POST', body, signal });
}

export async function renderSingingPreview(
  guideVocal: File,
  engineId: string,
  targetVoiceProfileId: string,
  signal?: AbortSignal,
): Promise<SingingPreviewResult> {
  const body = new FormData();
  body.append('guide_vocal', guideVocal);
  body.append('engine_id', engineId);
  body.append('target_voice_profile_id', targetVoiceProfileId);
  return apiJson<SingingPreviewResult>('/singing/preview', { method: 'POST', body, signal });
}

export interface SingingFullRenderResult {
  project_id: string;
  render_audio_url: string;
  duration_seconds: number;
  duration_formatted: string;
  guide_duration_seconds: number;
  within_tolerance: boolean;
  engine_id: string;
  engine_version: string;
  provenance: Record<string, string> | null;
}

export async function renderSingingFull(
  projectId: string,
  engineId: string,
  targetVoiceProfileId: string,
  signal?: AbortSignal,
): Promise<SingingFullRenderResult> {
  const body = new FormData();
  body.append('project_id', projectId);
  body.append('engine_id', engineId);
  body.append('target_voice_profile_id', targetVoiceProfileId);
  return apiJson<SingingFullRenderResult>('/singing/render', { method: 'POST', body, signal });
}

export type SingingExportFormat = 'wav' | 'm4a' | 'mp3' | 'flac';

/** Download path + a safe suggested filename for a project's finished full render. */
export function singingExportRequest(
  projectId: string,
  format: SingingExportFormat,
): { path: string; name: string } {
  return {
    path: `/singing/projects/${encodeURIComponent(projectId)}/export/${format}`,
    name: `voicestudio-singing-${projectId.replace(/[^a-zA-Z0-9_-]/g, '_')}.${format}`,
  };
}
