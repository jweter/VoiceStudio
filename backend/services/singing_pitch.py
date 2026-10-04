"""Deterministic F0 data contracts for Singing Mode."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math

F0_SCHEMA_VERSION = 1


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
        if payload.get("schema_version") != F0_SCHEMA_VERSION:
            raise ValueError("unsupported F0 schema version")
        if set(payload) != {"schema_version", "sample_rate", "hop_samples", "frames"}:
            raise ValueError("F0 artifact contains missing or unsupported fields")
        raw_frames = payload["frames"]
        if not isinstance(raw_frames, list):
            raise ValueError("frames must be a list")
        frames = []
        for raw in raw_frames:
            if not isinstance(raw, dict) or set(raw) != {
                "time_seconds",
                "frequency_hz",
                "voiced",
                "confidence",
            }:
                raise ValueError("invalid F0 frame")
            frames.append(F0Frame(**raw))
        return cls(
            sample_rate=int(payload["sample_rate"]),
            hop_samples=int(payload["hop_samples"]),
            frames=tuple(frames),
        )
