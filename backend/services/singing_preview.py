"""Singing Mode S5: compose the delivered S1/S3/S4 pieces into one headless workspace service.

Two entry points, no UI:

* :func:`analyze_guide_vocal` -- run the S3 pitch analysis (``extract_f0`` / ``voiced_segments``) on a
  guide vocal, for the workspace's "Analyze" step.
* :func:`render_preview` -- convert a *bounded* excerpt of the guide through the S4 contract
  (``convert_singing``) and return the guide's and the output's F0 tracks plus a per-frame cents
  difference, for the "Generate preview" step and its pitch-trace comparison.

:func:`compatible_singing_engines` reuses the S1 capability catalogue (``tts_backend.list_backends``)
so a workspace only ever offers an engine that declares ``singing_conversion``; an engine that does not
is refused again, defensively, inside ``convert_singing`` itself.

Nothing here makes a network call, and nothing here imports or falls back to speech synthesis -- the only
door to a conversion engine is ``convert_singing``, exactly as the S4 contract requires. The RVC adapter is
optional and never imported by this module; every test uses the fake engine from the S4 contract tests.
"""
from __future__ import annotations

import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

from services.singing_conversion import (
    CONVERSION_CAPABILITY,
    ConversionRequest,
    ConversionResult,
    InvalidConversionRequest,
    SingingConversionEngine,
    _read_wav,
    convert_singing,
)
from services.singing_pitch import F0Track, cents, extract_f0, voiced_segments

# A preview exists to show whether an engine preserves the melody, not to render a whole song;
# 15 s keeps conversion fast enough to iterate on and is well above the golden fixtures' lengths.
MAX_PREVIEW_SECONDS = 15.0

# Shared analysis cadence (seconds), converted to samples per track's own sample rate so that frame
# index ``i`` means the same instant in time on the guide and the output even when an engine resamples.
_HOP_SECONDS = 0.01
_FRAME_SECONDS = 0.064


@dataclass(frozen=True)
class AnalysisResult:
    f0_track: F0Track
    voiced_segments: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class CentsDiffFrame:
    """One aligned instant: ``cents`` is None unless both the guide and the output are voiced there."""

    time_seconds: float
    cents: float | None


@dataclass(frozen=True)
class PreviewResult:
    conversion: ConversionResult
    guide_f0: F0Track
    output_f0: F0Track
    cents_diff: tuple[CentsDiffFrame, ...]
    provenance: Mapping[str, str] | None


def _load_mono_pcm16(path: Path) -> tuple[np.ndarray, int]:
    """(mono float64 samples in [-1, 1], sample_rate) of a 16-bit PCM WAV; raises ``InvalidConversionRequest``."""
    rate, channels, width, data = _read_wav(Path(path), InvalidConversionRequest)
    if width != 2:
        raise InvalidConversionRequest(f"{Path(path).name} must be 16-bit PCM WAV for pitch analysis")
    samples = np.frombuffer(data, dtype="<i2").astype(np.float64) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, rate


def _extract_f0(samples: np.ndarray, rate: int) -> F0Track:
    hop_samples = max(1, round(_HOP_SECONDS * rate))
    frame_samples = max(hop_samples + 1, round(_FRAME_SECONDS * rate))
    return extract_f0(samples, rate, hop_samples=hop_samples, frame_samples=frame_samples)


def _write_mono_pcm16(path: Path, samples: np.ndarray, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).round().astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())


def _cents_diff(guide: F0Track, output: F0Track) -> tuple[CentsDiffFrame, ...]:
    frames = []
    for guide_frame, output_frame in zip(guide.frames, output.frames):
        value = None
        if (
            guide_frame.voiced and output_frame.voiced
            and guide_frame.frequency_hz is not None and output_frame.frequency_hz is not None
        ):
            value = cents(output_frame.frequency_hz, guide_frame.frequency_hz)
        frames.append(CentsDiffFrame(guide_frame.time_seconds, value))
    return tuple(frames)


def analyze_guide_vocal(guide_vocal: Path, *, min_voiced_frames: int = 1) -> AnalysisResult:
    """F0 track and voiced segments of ``guide_vocal``; refuses an unreadable or non-WAV file."""
    samples, rate = _load_mono_pcm16(guide_vocal)
    track = _extract_f0(samples, rate)
    return AnalysisResult(track, voiced_segments(track, min_frames=min_voiced_frames))


def compatible_singing_engines() -> list[dict]:
    """Engine catalogue entries that declare ``singing_conversion`` (S1 filtering) -- never an ineligible one."""
    # Local import: keep this module importable without tts_backend's heavier dependency chain.
    from services.tts_backend import list_backends

    return list_backends(singing_capability=CONVERSION_CAPABILITY)


def render_preview(
    engine: SingingConversionEngine,
    request: ConversionRequest,
    *,
    max_preview_seconds: float = MAX_PREVIEW_SECONDS,
) -> PreviewResult:
    """Convert a bounded excerpt of ``request.guide_vocal`` through ``engine`` and compare guide/output pitch.

    ``request.guide_vocal`` is truncated to at most ``max_preview_seconds`` before anything is sent to the
    engine, so a long song never pays for a full render just to preview it. An engine that does not declare
    ``singing_conversion`` is refused by ``convert_singing`` itself before it is ever called.
    """
    if not (max_preview_seconds > 0):
        raise InvalidConversionRequest("max_preview_seconds must be positive")
    samples, rate = _load_mono_pcm16(request.guide_vocal)
    bound = min(samples.size, round(max_preview_seconds * rate))
    excerpt = samples[:bound]
    guide_f0 = _extract_f0(excerpt, rate)

    with tempfile.TemporaryDirectory(prefix="voicestudio-singing-preview-") as scratch:
        excerpt_path = Path(scratch) / "excerpt.wav"
        _write_mono_pcm16(excerpt_path, excerpt, rate)
        bounded_request = ConversionRequest(
            projects_root=request.projects_root,
            project_id=request.project_id,
            guide_vocal=excerpt_path,
            target_voice=request.target_voice,
            output_name=request.output_name,
            f0_track=guide_f0,
        )
        result = convert_singing(engine, bounded_request)

    output_samples, output_rate = _load_mono_pcm16(result.output_path)
    output_f0 = _extract_f0(output_samples, output_rate)
    return PreviewResult(
        conversion=result,
        guide_f0=guide_f0,
        output_f0=output_f0,
        cents_diff=_cents_diff(guide_f0, output_f0),
        provenance=result.provenance,
    )
