import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { F0FramePayload } from '@/lib/api/singing';

const WIDTH = 640;
const HEIGHT = 160;
const PAD_X = 8;
const PAD_Y = 10;

/** Voiced-only (time, log2 Hz) points, as contiguous runs so unvoiced gaps never get an interpolated line. */
function voicedRuns(track: F0FramePayload[]): { x: number; y: number }[][] {
  const runs: { x: number; y: number }[][] = [];
  let current: { x: number; y: number }[] = [];
  for (const frame of track) {
    if (frame.voiced && frame.frequency_hz != null) {
      current.push({ x: frame.time_seconds, y: Math.log2(frame.frequency_hz) });
    } else if (current.length) {
      runs.push(current);
      current = [];
    }
  }
  if (current.length) runs.push(current);
  return runs;
}

function toPath(
  runs: { x: number; y: number }[][],
  scaleX: (x: number) => number,
  scaleY: (y: number) => number,
): string {
  return runs
    .map((run) => run.map((p, i) => `${i === 0 ? 'M' : 'L'}${scaleX(p.x)},${scaleY(p.y)}`).join(' '))
    .join(' ');
}

/** Guide F0 vs output F0 on one axis (docs/projects/singing-mode.md UI concept): the pitch trace
 * that shows whether a conversion preserved the melody instead of asking the user to trust it. */
export function PitchTraceChart({
  guideF0,
  outputF0,
}: {
  guideF0: F0FramePayload[];
  outputF0?: F0FramePayload[];
}) {
  const { t } = useTranslation();
  const { guidePath, outputPath, hasData } = useMemo(() => {
    const voicedHz = [...guideF0, ...(outputF0 ?? [])]
      .filter((f) => f.voiced && f.frequency_hz != null)
      .map((f) => Math.log2(f.frequency_hz as number));
    const maxTime = Math.max(
      1e-6,
      ...guideF0.map((f) => f.time_seconds),
      ...(outputF0 ?? []).map((f) => f.time_seconds),
    );
    if (!voicedHz.length) return { guidePath: '', outputPath: '', hasData: false };
    const minY = Math.min(...voicedHz);
    const maxY = Math.max(...voicedHz);
    const span = Math.max(maxY - minY, 1e-6);
    const scaleX = (x: number) => PAD_X + (x / maxTime) * (WIDTH - 2 * PAD_X);
    // Inverted: higher pitch draws nearer the top of the chart.
    const scaleY = (y: number) => HEIGHT - PAD_Y - ((y - minY) / span) * (HEIGHT - 2 * PAD_Y);
    return {
      guidePath: toPath(voicedRuns(guideF0), scaleX, scaleY),
      outputPath: outputF0 ? toPath(voicedRuns(outputF0), scaleX, scaleY) : '',
      hasData: true,
    };
  }, [guideF0, outputF0]);

  if (!hasData) {
    return <p className="text-sm text-muted-foreground">{t('singingWorkspace.pitch_trace_empty')}</p>;
  }

  return (
    <div className="space-y-2">
      <svg
        role="img"
        aria-label={t('singingWorkspace.pitch_trace_label')}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-40 w-full rounded-lg border border-border/60 bg-muted/20"
        preserveAspectRatio="none"
      >
        <path d={guidePath} fill="none" stroke="currentColor" strokeWidth={2} className="text-chart-1" />
        {outputPath && (
          <path
            d={outputPath}
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            className="text-chart-2"
          />
        )}
      </svg>
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-2 rounded-full bg-chart-1" aria-hidden="true" />
          {t('singingWorkspace.pitch_trace_guide')}
        </span>
        {outputPath && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block size-2 rounded-full bg-chart-2" aria-hidden="true" />
            {t('singingWorkspace.pitch_trace_output')}
          </span>
        )}
      </div>
    </div>
  );
}
