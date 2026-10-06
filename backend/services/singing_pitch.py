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
