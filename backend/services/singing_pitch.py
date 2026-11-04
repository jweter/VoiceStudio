from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from numbers import Real

import numpy as np

F0_SCHEMA_VERSION = 1


def _real(name: str, value: object, *, allow_none: bool = False) -> float | None:
    if allow_none and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class F0Frame:
    time_seconds: float
    frequency_hz: float | None
    voiced: bool
    confidence: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.time_seconds) or self.time_seconds < 0:
            raise ValueError("time_seconds must be finite and non-negative")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.voiced and (
            self.frequency_hz is None
            or not math.isfinite(self.frequency_hz)
            or self.frequency_hz <= 0
        ):
            raise ValueError("voiced frames require a positive finite frequency_hz")
        if not self.voiced and self.frequency_hz is not None:
            raise ValueError("unvoiced frames must not carry frequency_hz")


@dataclass(frozen=True)
class F0Track:
    sample_rate: int
    hop_samples: int
    frames: tuple[F0Frame, ...]

    def __post_init__(self) -> None:
        if type(self.sample_rate) is not int or type(self.hop_samples) is not int:
            raise ValueError("sample_rate and hop_samples must be integers")
        if self.sample_rate <= 0 or self.hop_samples <= 0:
            raise ValueError("sample_rate and hop_samples must be positive")
        times = [frame.time_seconds for frame in self.frames]
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError("F0 frame timestamps must be strictly increasing")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": F0_SCHEMA_VERSION,
            "sample_rate": self.sample_rate,
            "hop_samples": self.hop_samples,
            "frames": [asdict(frame) for frame in self.frames],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "F0Track":
        if type(payload.get("schema_version")) is not int or payload.get("schema_version") != F0_SCHEMA_VERSION:
            raise ValueError("unsupported F0 schema version")
        if set(payload) != {"schema_version", "sample_rate", "hop_samples", "frames"}:
            raise ValueError("F0 artifact contains missing or unsupported fields")
        if type(payload["sample_rate"]) is not int or type(payload["hop_samples"]) is not int:
            raise ValueError("sample_rate and hop_samples must be integers")
        raw_frames = payload["frames"]
        if not isinstance(raw_frames, list):
            raise ValueError("frames must be a list")
        frames: list[F0Frame] = []
        for raw in raw_frames:
            if not isinstance(raw, dict) or set(raw) != {
                "time_seconds", "frequency_hz", "voiced", "confidence"
            }:
                raise ValueError("invalid F0 frame")
            if type(raw["voiced"]) is not bool:
                raise ValueError("voiced must be a boolean")
            time_seconds = _real("time_seconds", raw["time_seconds"])
            frequency_hz = _real("frequency_hz", raw["frequency_hz"], allow_none=True)
            confidence = _real("confidence", raw["confidence"])
            assert time_seconds is not None and confidence is not None
            frames.append(F0Frame(time_seconds, frequency_hz, raw["voiced"], confidence))
        return cls(payload["sample_rate"], payload["hop_samples"], tuple(frames))


def extract_f0(
    samples: np.ndarray,
    sample_rate: int,
    *,
    hop_samples: int = 480,
    frame_samples: int = 2048,
    min_hz: float = 70.0,
    max_hz: float = 1000.0,
    voicing_threshold: float = 0.30,
) -> F0Track:
    """Deterministically extract a monophonic F0 track using normalized autocorrelation."""
    if type(sample_rate) is not int or type(hop_samples) is not int or type(frame_samples) is not int:
        raise ValueError("sample_rate, hop_samples, and frame_samples must be integers")
    if sample_rate <= 0 or hop_samples <= 0 or frame_samples <= 1:
        raise ValueError("sample_rate, hop_samples, and frame_samples must be positive")
    if not (0 < min_hz < max_hz <= sample_rate / 2):
        raise ValueError("invalid F0 frequency bounds")
    audio = np.asarray(samples, dtype=np.float64)
    if audio.ndim != 1:
        raise ValueError("samples must be mono")
    if not np.all(np.isfinite(audio)):
        raise ValueError("samples must be finite")
    if audio.size == 0:
        return F0Track(sample_rate, hop_samples, ())

    min_lag = max(1, int(sample_rate / max_hz))
    max_lag = min(frame_samples - 1, int(sample_rate / min_hz))
    frames: list[F0Frame] = []
    for start in range(0, audio.size, hop_samples):
        frame = audio[start : start + frame_samples]
        if frame.size < max_lag + 2:
            frame = np.pad(frame, (0, max_lag + 2 - frame.size))
        frame = frame - float(np.mean(frame))
        energy = float(np.dot(frame, frame))
        time_seconds = start / sample_rate
        if energy <= 1e-12:
            frames.append(F0Frame(time_seconds, None, False, 0.0))
            continue
        corr = np.correlate(frame, frame, mode="full")[frame.size - 1 :]
        lag_slice = corr[min_lag : max_lag + 1]
        lag = min_lag + int(np.argmax(lag_slice))
        confidence = float(corr[lag] / corr[0]) if corr[0] > 0 else 0.0
        confidence = max(0.0, min(1.0, confidence))
        if confidence < voicing_threshold:
            frames.append(F0Frame(time_seconds, None, False, confidence))
        else:
            frames.append(F0Frame(time_seconds, sample_rate / lag, True, confidence))
    return F0Track(sample_rate, hop_samples, tuple(frames))


# --- accuracy measurement (singing-mode S3: "F0 error in cents, voiced/unvoiced agreement, octave-error rate") ---------

@dataclass(frozen=True)
class ReferenceNote:
    """Ground truth for a golden fixture: ``frequency_hz`` of None means silence/unvoiced for the interval."""

    start_seconds: float
    end_seconds: float
    frequency_hz: float | None

    def __post_init__(self) -> None:
        if not (math.isfinite(self.start_seconds) and math.isfinite(self.end_seconds)) or not 0 <= self.start_seconds < self.end_seconds:
            raise ValueError("reference interval must be finite with 0 <= start < end")
        if self.frequency_hz is not None and (not math.isfinite(self.frequency_hz) or self.frequency_hz <= 0):
            raise ValueError("reference frequency_hz must be positive and finite, or None")


@dataclass(frozen=True)
class F0Evaluation:
    frames_evaluated: int
    voiced_agreement: float
    median_abs_cents: float | None
    p95_abs_cents: float | None
    octave_error_rate: float | None


def cents(measured_hz: float, reference_hz: float) -> float:
    """Signed pitch error in cents (+ = measured is sharp)."""
    if not (math.isfinite(measured_hz) and math.isfinite(reference_hz)) or measured_hz <= 0 or reference_hz <= 0:
        raise ValueError("frequencies must be positive and finite")
    return 1200.0 * math.log2(measured_hz / reference_hz)


def _reference_at(notes: tuple[ReferenceNote, ...], time_seconds: float) -> tuple[bool, ReferenceNote | None]:
    for note in notes:
        if note.start_seconds <= time_seconds < note.end_seconds:
            return True, note
    return False, None


def evaluate_f0(track: F0Track, reference: tuple[ReferenceNote, ...] | list[ReferenceNote], *,
                edge_guard_seconds: float = 0.0, octave_tolerance_cents: float = 100.0) -> F0Evaluation:
    """Score a track against known notes. Frames not covered by the reference, or within ``edge_guard_seconds``
    of a reference boundary (where any windowed analyzer is legitimately ambiguous), are not scored."""
    notes = tuple(reference)
    if not math.isfinite(edge_guard_seconds) or edge_guard_seconds < 0:
        raise ValueError("edge_guard_seconds must be finite and non-negative")
    agree = 0
    scored = 0
    errors: list[float] = []
    octave = 0
    for frame in track.frames:
        covered, note = _reference_at(notes, frame.time_seconds)
        if not covered or note is None:
            continue
        if min(frame.time_seconds - note.start_seconds, note.end_seconds - frame.time_seconds) < edge_guard_seconds:
            continue
        scored += 1
        expected_voiced = note.frequency_hz is not None
        agree += frame.voiced == expected_voiced
        if frame.voiced and expected_voiced and frame.frequency_hz is not None and note.frequency_hz is not None:
            error = cents(frame.frequency_hz, note.frequency_hz)
            errors.append(abs(error))
            octave += abs(abs(error) - 1200.0) <= octave_tolerance_cents
    if scored == 0:
        raise ValueError("no frames fall inside the reference")
    ordered = sorted(errors)
    return F0Evaluation(
        frames_evaluated=scored,
        voiced_agreement=agree / scored,
        median_abs_cents=float(np.median(ordered)) if ordered else None,
        p95_abs_cents=float(ordered[min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)]) if ordered else None,
        octave_error_rate=octave / len(ordered) if ordered else None,
    )


def voiced_segments(track: F0Track, *, min_frames: int = 1) -> tuple[tuple[float, float], ...]:
    """Contiguous voiced runs as (start_seconds, end_seconds); the end is the first non-voiced frame (or one hop past the last)."""
    if type(min_frames) is not int or min_frames < 1:
        raise ValueError("min_frames must be a positive integer")
    hop = track.hop_samples / track.sample_rate
    runs: list[tuple[float, float]] = []
    start: float | None = None
    count = 0
    for frame in track.frames:
        if frame.voiced:
            if start is None:
                start, count = frame.time_seconds, 0
            count += 1
            end = frame.time_seconds + hop
        elif start is not None:
            if count >= min_frames:
                runs.append((start, frame.time_seconds))
            start = None
    if start is not None and count >= min_frames:
        runs.append((start, end))
    return tuple(runs)
