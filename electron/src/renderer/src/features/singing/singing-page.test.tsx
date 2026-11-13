import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import '@/i18n';
import type { Profile } from '@/lib/api/types';
import type { SingingEngine, SingingAnalyzeResult, SingingPreviewResult } from '@/lib/api/singing';

const mock = vi.hoisted(() => ({
  listEngines: vi.fn<[], Promise<SingingEngine[]>>(),
  analyze: vi.fn<unknown[], Promise<SingingAnalyzeResult>>(),
  preview: vi.fn<unknown[], Promise<SingingPreviewResult>>(),
}));
vi.mock('@/lib/api/singing', () => ({
  listSingingEngines: mock.listEngines,
  analyzeGuideVocal: mock.analyze,
  renderSingingPreview: mock.preview,
}));
vi.mock('@/components/app-shell/workspace-header', () => ({
  WorkspaceHeader: ({ children }: { children: React.ReactNode }) => <header>{children}</header>,
}));
vi.mock('@/hooks/use-profiles', () => ({
  useProfiles: () => ({
    data: [
      { id: 'target-1', name: 'Target Voice', kind: 'clone', ref_audio_path: 'target-1.wav' },
      { id: 'no-audio', name: 'No Audio Yet', kind: 'design', ref_audio_path: null },
    ] as Profile[],
  }),
}));
vi.mock('@/components/audio-preview-button', () => ({
  AudioPreviewButton: ({ src, source }: { src: string; source: string }) => (
    <div data-testid={source}>{src}</div>
  ),
}));
// @ts-expect-error untyped test double matching the shared JSX component's props
vi.mock('@shared/components/VoiceSelector', () => ({
  default: ({ value, onChange, profiles, ariaLabel }: any) => (
    <select aria-label={ariaLabel} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="" />
      {profiles.map((p: Profile) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
    </select>
  ),
}));
// @ts-expect-error untyped test double matching the shared JSX component's props
vi.mock('@shared/components/SearchableSelect', () => ({
  default: ({ value, onChange, options, ariaLabel, disabled }: any) => (
    <select
      aria-label={ariaLabel}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="" />
      {options.map((o: { value: string; label: string }) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  ),
}));

import { SingingPage } from './singing-page';

const ENGINE: SingingEngine = {
  id: 'fake-engine',
  display_name: 'Fake Engine',
  available: true,
  reason: null,
};

function mount() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SingingPage />
    </QueryClientProvider>,
  );
}

function uploadGuideVocal(name = 'guide.wav') {
  fireEvent.change(screen.getByLabelText('Guide vocal', { selector: 'input' }), {
    target: { files: [new File(['guide audio'], name, { type: 'audio/wav' })] },
  });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mock.listEngines.mockReset();
  mock.analyze.mockReset();
  mock.preview.mockReset();
});

it('refuses to generate a preview when no engine supports singing conversion', async () => {
  mock.listEngines.mockResolvedValue([]);
  mount();
  await waitFor(() => expect(mock.listEngines).toHaveBeenCalled());
  expect(
    await screen.findByText(
      /no installed engine supports singing conversion yet/i,
    ),
  ).toBeInTheDocument();
  uploadGuideVocal();
  expect(screen.getByRole('button', { name: /generate preview/i })).toBeDisabled();
  expect(screen.getByRole('button', { name: /^analyze$/i })).toBeEnabled();
});

it('requires a guide vocal, a target voice, a compatible engine and consent before generating', async () => {
  mock.listEngines.mockResolvedValue([ENGINE]);
  mount();
  await waitFor(() => expect(mock.listEngines).toHaveBeenCalled());
  const generate = screen.getByRole('button', { name: /generate preview/i });
  expect(generate).toBeDisabled();

  uploadGuideVocal();
  expect(generate).toBeDisabled();

  fireEvent.change(screen.getByLabelText('Target voice', { selector: 'select' }), { target: { value: 'target-1' } });
  expect(generate).toBeDisabled();

  fireEvent.change(screen.getByLabelText('Engine', { selector: 'select' }), { target: { value: 'fake-engine' } });
  expect(generate).toBeDisabled(); // consent still unchecked

  fireEvent.click(screen.getByRole('checkbox'));
  expect(generate).toBeEnabled();

  expect(mock.preview).not.toHaveBeenCalled();
});

it('analyzes a guide vocal and renders its pitch trace', async () => {
  mock.listEngines.mockResolvedValue([ENGINE]);
  mock.analyze.mockResolvedValue({
    project_id: 'p1',
    guide_audio_url: '/singing/projects/p1/audio/guide',
    guide_f0: [
      { time_seconds: 0, frequency_hz: 220, voiced: true },
      { time_seconds: 0.1, frequency_hz: 224, voiced: true },
    ],
    voiced_segments: [{ start_seconds: 0, end_seconds: 0.1 }],
  });
  mount();
  await waitFor(() => expect(mock.listEngines).toHaveBeenCalled());
  uploadGuideVocal();

  await act(async () => fireEvent.click(screen.getByRole('button', { name: /^analyze$/i })));

  expect(mock.analyze).toHaveBeenCalledWith(expect.any(File));
  expect(await screen.findByRole('img', { name: /pitch/i })).toBeInTheDocument();
  expect(screen.getByText(/guide f0/i)).toBeInTheDocument();
  expect(screen.queryByText(/output f0/i)).not.toBeInTheDocument();
});

it('generates a preview and plays both the original and the converted take', async () => {
  mock.listEngines.mockResolvedValue([ENGINE]);
  mock.preview.mockResolvedValue({
    project_id: 'p1',
    guide_audio_url: '/singing/projects/p1/audio/guide',
    preview_audio_url: '/singing/projects/p1/audio/preview',
    guide_f0: [{ time_seconds: 0, frequency_hz: 220, voiced: true }],
    output_f0: [{ time_seconds: 0, frequency_hz: 221, voiced: true }],
    cents_diff: [{ time_seconds: 0, cents: 7.8 }],
    duration_seconds: 2,
    guide_duration_seconds: 2,
    within_tolerance: true,
    engine_id: 'fake-engine',
    engine_version: '0.0-test',
    provenance: null,
  });
  mount();
  await waitFor(() => expect(mock.listEngines).toHaveBeenCalled());
  uploadGuideVocal();
  fireEvent.change(screen.getByLabelText('Target voice', { selector: 'select' }), { target: { value: 'target-1' } });
  fireEvent.change(screen.getByLabelText('Engine', { selector: 'select' }), { target: { value: 'fake-engine' } });
  fireEvent.click(screen.getByRole('checkbox'));

  await act(async () =>
    fireEvent.click(screen.getByRole('button', { name: /generate preview/i })),
  );

  expect(mock.preview).toHaveBeenCalledWith(expect.any(File), 'fake-engine', 'target-1');
  expect(await screen.findByTestId('singing-converted')).toHaveTextContent(
    '/api/singing/projects/p1/audio/preview',
  );
  expect(screen.getByText(/output f0/i)).toBeInTheDocument();
});

it('shows the engine/consent-gated error when preview rendering fails', async () => {
  mock.listEngines.mockResolvedValue([ENGINE]);
  mock.preview.mockRejectedValue(new Error('engine does not declare singing_conversion'));
  mount();
  await waitFor(() => expect(mock.listEngines).toHaveBeenCalled());
  uploadGuideVocal();
  fireEvent.change(screen.getByLabelText('Target voice', { selector: 'select' }), { target: { value: 'target-1' } });
  fireEvent.change(screen.getByLabelText('Engine', { selector: 'select' }), { target: { value: 'fake-engine' } });
  fireEvent.click(screen.getByRole('checkbox'));

  await act(async () =>
    fireEvent.click(screen.getByRole('button', { name: /generate preview/i })),
  );

  expect(await screen.findByRole('alert')).toHaveTextContent(/singing_conversion/);
});
