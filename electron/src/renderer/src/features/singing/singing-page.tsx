import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { MicVocalIcon, PlayIcon, LoaderCircleIcon, PlayCircleIcon, AudioLinesIcon } from 'lucide-react';
import { WorkspaceHeader } from '@/components/app-shell/workspace-header';
import { Button } from '@/components/ui/button';
import { AudioPreviewButton } from '@/components/audio-preview-button';
import { SaveAudioButton } from '@/components/save-audio-button';
import { useProfiles } from '@/hooks/use-profiles';
import { apiPath, describeError } from '@/lib/api/client';
import { queryKeys } from '@/lib/query';
import {
  analyzeGuideVocal,
  listSingingEngines,
  renderSingingFull,
  renderSingingPreview,
  singingExportRequest,
  type SingingAnalyzeResult,
  type SingingExportFormat,
  type SingingFullRenderResult,
  type SingingPreviewResult,
} from '@/lib/api/singing';
import { PitchTraceChart } from './pitch-trace-chart';
// Shared application controls are JavaScript; keep their established voice/value contracts.
// @ts-expect-error shared JSX component has no declaration file
import VoiceSelector from '@shared/components/VoiceSelector';
// @ts-expect-error shared JSX component has no declaration file
import SearchableSelect from '@shared/components/SearchableSelect';

function isWavFile(file: File): boolean {
  return file.type === 'audio/wav' || file.type === 'audio/x-wav' || /\.wav$/i.test(file.name);
}

const EXPORT_FORMATS: SingingExportFormat[] = ['wav', 'm4a', 'mp3', 'flac'];

export function SingingPage() {
  const { t } = useTranslation();
  const profiles = useProfiles();
  const engines = useQuery({
    queryKey: queryKeys.singingEngines,
    queryFn: ({ signal }) => listSingingEngines(signal),
  });
  const targetVoices = (profiles.data ?? []).filter((profile) => profile.ref_audio_path);
  const compatibleEngines = engines.data ?? [];

  const [guideFile, setGuideFile] = useState<File | null>(null);
  const [guideObjectUrl, setGuideObjectUrl] = useState('');
  const [targetVoiceId, setTargetVoiceId] = useState('');
  const [engineId, setEngineId] = useState('');
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [analysis, setAnalysis] = useState<SingingAnalyzeResult | null>(null);
  const [preview, setPreview] = useState<SingingPreviewResult | null>(null);
  const [projectId, setProjectId] = useState('');
  const [fullRender, setFullRender] = useState<SingingFullRenderResult | null>(null);
  const [exportFormat, setExportFormat] = useState<SingingExportFormat>('wav');
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  // Bumped on every new guide vocal: a request started for an earlier guide must not
  // write its result (or its error) over the guide now on screen.
  const guideGeneration = useRef(0);

  const ingest = (file: File) => {
    if (!isWavFile(file)) {
      setError(t('singingWorkspace.unsupported_audio'));
      return;
    }
    guideGeneration.current += 1;
    setError('');
    setAnalysis(null);
    setPreview(null);
    setProjectId('');
    setFullRender(null);
    setGuideFile(file);
    setGuideObjectUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return URL.createObjectURL(file);
    });
  };

  const canAnalyze = Boolean(guideFile) && !analyzing && !generating;
  const canGenerate =
    Boolean(guideFile) &&
    Boolean(targetVoiceId) &&
    Boolean(engineId) &&
    compatibleEngines.some((entry) => entry.id === engineId) &&
    consentAccepted &&
    !analyzing &&
    !generating;
  const canRenderFull =
    Boolean(projectId) &&
    Boolean(targetVoiceId) &&
    Boolean(engineId) &&
    compatibleEngines.some((entry) => entry.id === engineId) &&
    consentAccepted &&
    !analyzing &&
    !generating &&
    !rendering;

  const runAnalyze = async () => {
    if (!guideFile || !canAnalyze) return;
    const generation = guideGeneration.current;
    setAnalyzing(true);
    setError('');
    try {
      const result = await analyzeGuideVocal(guideFile);
      if (generation === guideGeneration.current) {
        setAnalysis(result);
        setProjectId(result.project_id);
      }
    } catch (err) {
      if (generation === guideGeneration.current) setError(describeError(err));
    } finally {
      setAnalyzing(false);
    }
  };

  const runGenerate = async () => {
    if (!guideFile || !canGenerate) return;
    const generation = guideGeneration.current;
    setGenerating(true);
    setError('');
    try {
      const result = await renderSingingPreview(guideFile, engineId, targetVoiceId);
      if (generation === guideGeneration.current) {
        setPreview(result);
        setProjectId(result.project_id);
      }
    } catch (err) {
      if (generation === guideGeneration.current) setError(describeError(err));
    } finally {
      setGenerating(false);
    }
  };

  const runRenderFull = async () => {
    if (!projectId || !canRenderFull) return;
    const generation = guideGeneration.current;
    setRendering(true);
    setError('');
    try {
      const result = await renderSingingFull(projectId, engineId, targetVoiceId);
      if (generation === guideGeneration.current) setFullRender(result);
    } catch (err) {
      if (generation === guideGeneration.current) setError(describeError(err));
    } finally {
      setRendering(false);
    }
  };

  const guideF0 = preview?.guide_f0 ?? analysis?.guide_f0 ?? [];
  const backendGuideAudioUrl = preview?.guide_audio_url ?? analysis?.guide_audio_url ?? null;
  const guideAudioSrc = backendGuideAudioUrl ? apiPath(backendGuideAudioUrl) : guideObjectUrl;
  const exportRequest = fullRender
    ? singingExportRequest(fullRender.project_id, exportFormat)
    : null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <WorkspaceHeader>
        <h1 className="text-sm font-medium">{t('singingWorkspace.title')}</h1>
      </WorkspaceHeader>
      <div className="mx-auto w-full max-w-3xl flex-1 space-y-6 overflow-y-auto px-6 py-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <MicVocalIcon className="size-4 text-primary" aria-hidden="true" />
          <span className="font-medium text-foreground">
            {t('singingWorkspace.mode_convert')}
          </span>
          <span aria-hidden="true">·</span>
          <span className="opacity-60">{t('singingWorkspace.mode_synthesize_later')}</span>
        </div>

        <section className="space-y-3" aria-label={t('singingWorkspace.guide_vocal_kicker')}>
          <h3 className="text-sm font-medium">{t('singingWorkspace.guide_vocal_kicker')}</h3>
          <input
            ref={fileInput}
            type="file"
            accept="audio/wav,audio/x-wav,.wav"
            className="sr-only"
            aria-label={t('singingWorkspace.guide_vocal_kicker')}
            onChange={(event) => {
              const chosen = event.target.files?.[0];
              if (chosen) ingest(chosen);
              event.target.value = '';
            }}
          />
          <Button
            variant="outline"
            className="h-auto min-h-16 w-full whitespace-normal border-dashed p-4"
            onClick={() => fileInput.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              if (event.dataTransfer.files[0]) ingest(event.dataTransfer.files[0]);
            }}
          >
            {guideFile?.name ?? t('singingWorkspace.choose_guide_vocal')}
          </Button>
        </section>

        <section className="space-y-3" aria-label={t('convert.target_voice')}>
          <h3 className="text-sm font-medium">{t('convert.target_voice')}</h3>
          <VoiceSelector
            value={targetVoiceId}
            onChange={(voiceId: string) => setTargetVoiceId(voiceId)}
            profiles={targetVoices}
            gallery={false}
            presets={false}
            engineDefault={false}
            ariaLabel={t('convert.target_voice')}
            placeholder={t('convert.pick_voice')}
            menuPortal
          />
        </section>

        <section className="space-y-3" aria-label={t('singingWorkspace.engine_kicker')}>
          <h3 className="text-sm font-medium">{t('singingWorkspace.engine_kicker')}</h3>
          <SearchableSelect
            value={engineId}
            onChange={(value: string) => setEngineId(value)}
            options={compatibleEngines.map((entry) => ({ value: entry.id, label: entry.display_name }))}
            ariaLabel={t('singingWorkspace.engine_kicker')}
            placeholder={t('singingWorkspace.choose_engine')}
            disabled={!compatibleEngines.length}
            menuPortal
          />
          {!engines.isLoading && !compatibleEngines.length && (
            <p role="status" className="text-sm text-muted-foreground">
              {t('singingWorkspace.no_compatible_engine')}
            </p>
          )}
        </section>

        <section className="space-y-2 rounded-xl border border-border/60 bg-muted/20 p-3">
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={consentAccepted}
              onChange={(event) => setConsentAccepted(event.target.checked)}
              aria-describedby="singing-consent-text"
            />
            <span id="singing-consent-text">{t('singingWorkspace.consent_text')}</span>
          </label>
        </section>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="flex items-center gap-2">
          <Button variant="outline" disabled={!canAnalyze} onClick={() => void runAnalyze()}>
            {analyzing ? <LoaderCircleIcon className="animate-spin motion-reduce:animate-none" /> : null}
            {t('singingWorkspace.analyze')}
          </Button>
          <Button disabled={!canGenerate} onClick={() => void runGenerate()}>
            {generating ? (
              <LoaderCircleIcon className="animate-spin motion-reduce:animate-none" />
            ) : (
              <PlayIcon />
            )}
            {t('singingWorkspace.generate_preview')}
          </Button>
          <Button variant="outline" disabled={!canRenderFull} onClick={() => void runRenderFull()}>
            {rendering ? (
              <LoaderCircleIcon className="animate-spin motion-reduce:animate-none" />
            ) : (
              <AudioLinesIcon />
            )}
            {t('singingWorkspace.render_full')}
          </Button>
        </div>

        {(analysis || preview) && (
          <section className="space-y-4 border-t border-border/60 pt-4">
            <div className="space-y-2">
              <h3 className="text-sm font-medium">{t('singingWorkspace.ab_kicker')}</h3>
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-2 text-sm">
                  <AudioPreviewButton src={guideAudioSrc} source="singing-original" />
                  {t('singingWorkspace.original')}
                </span>
                <span className="flex items-center gap-2 text-sm">
                  {preview ? (
                    <AudioPreviewButton
                      src={apiPath(preview.preview_audio_url)}
                      source="singing-converted"
                    />
                  ) : (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled
                      aria-label={t('singingWorkspace.converted')}
                    >
                      <PlayCircleIcon />
                    </Button>
                  )}
                  {t('singingWorkspace.converted')}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-medium">{t('singingWorkspace.pitch_trace_kicker')}</h3>
              <PitchTraceChart guideF0={guideF0} outputF0={preview?.output_f0} />
            </div>
            {preview && (
              <p className="text-xs text-muted-foreground">
                {t('singingWorkspace.engine_provenance', {
                  engine: preview.engine_id,
                  version: preview.engine_version,
                })}
              </p>
            )}
          </section>
        )}

        {fullRender && (
          <section
            className="space-y-4 border-t border-border/60 pt-4"
            aria-label={t('singingWorkspace.full_render_kicker')}
          >
            <div className="space-y-2">
              <h3 className="text-sm font-medium">{t('singingWorkspace.full_render_kicker')}</h3>
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-2 text-sm">
                  <AudioPreviewButton
                    src={apiPath(fullRender.render_audio_url)}
                    source="singing-full-render"
                  />
                  {t('singingWorkspace.full_render_audio')}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('singingWorkspace.engine_provenance', {
                  engine: fullRender.engine_id,
                  version: fullRender.engine_version,
                })}
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-medium">{t('singingWorkspace.export_kicker')}</h3>
              <div
                className="flex flex-wrap gap-1"
                role="group"
                aria-label={t('singingWorkspace.export_format_label')}
              >
                {EXPORT_FORMATS.map((format) => (
                  <Button
                    key={format}
                    size="xs"
                    variant={exportFormat === format ? 'secondary' : 'ghost'}
                    aria-pressed={exportFormat === format}
                    onClick={() => setExportFormat(format)}
                  >
                    {format.toUpperCase()}
                  </Button>
                ))}
              </div>
              <SaveAudioButton
                url={exportRequest ? apiPath(exportRequest.path) : undefined}
                suggestedName={exportRequest?.name ?? ''}
              />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
