"""Model-independent Singing Mode contracts.

Singing is intentionally separate from speech TTS. Adapters must explicitly
implement supported operations; callers never fall back to TTS.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import torch

SingingOperation = Literal["conversion", "synthesis"]

@dataclass(frozen=True)
class SingingCapabilities:
    conversion: bool = False
    synthesis: bool = False
    pitch_conditioning: bool = False
    phoneme_timing: bool = False
    midi_input: bool = False
    musicxml_input: bool = False

@dataclass(frozen=True)
class SingingConversionRequest:
    guide_vocal: Path
    target_voice: Path
    preserve_pitch: bool = True
    preserve_timing: bool = True

    def validate(self) -> None:
        if not self.guide_vocal.is_file():
            raise ValueError("guide_vocal must be an existing file")
        if not self.target_voice.is_file():
            raise ValueError("target_voice must be an existing file")

@dataclass(frozen=True)
class SingingSynthesisRequest:
    lyrics: str
    melody: Path
    melody_format: Literal["midi", "musicxml"]
    target_voice: Path

    def validate(self) -> None:
        if not self.lyrics.strip():
            raise ValueError("lyrics must not be empty")
        if not self.melody.is_file():
            raise ValueError("melody must be an existing file")
        if not self.target_voice.is_file():
            raise ValueError("target_voice must be an existing file")

@dataclass(frozen=True)
class SingingRender:
    audio: torch.Tensor
    sample_rate: int
    engine_id: str
    operation: SingingOperation

class SingingBackend(ABC):
    """Base contract for singing engines; deliberately not a TTSBackend."""
    id: str = "base-singing"
    display_name: str = "Base Singing"
    capabilities = SingingCapabilities()

    @classmethod
    @abstractmethod
    def is_available(cls) -> tuple[bool, str]: ...

    def convert(self, request: SingingConversionRequest) -> SingingRender:
        if not self.capabilities.conversion:
            raise NotImplementedError(f"{self.id} does not support singing conversion")
        request.validate()
        return self._convert(request)

    def synthesize(self, request: SingingSynthesisRequest) -> SingingRender:
        if not self.capabilities.synthesis:
            raise NotImplementedError(f"{self.id} does not support singing synthesis")
        request.validate()
        return self._synthesize(request)

    def _convert(self, request: SingingConversionRequest) -> SingingRender:
        raise NotImplementedError

    def _synthesize(self, request: SingingSynthesisRequest) -> SingingRender:
        raise NotImplementedError

class DeterministicSingingBackend(SingingBackend):
    """Test harness only; proves routing/timing without claiming voice quality."""
    id = "deterministic-singing-test"
    display_name = "Deterministic Singing Test Harness"
    capabilities = SingingCapabilities(conversion=True, pitch_conditioning=True)

    def __init__(self, guide_audio: torch.Tensor, sample_rate: int = 24000):
        self._guide_audio = guide_audio.clone()
        self._sample_rate = sample_rate

    @classmethod
    def is_available(cls) -> tuple[bool, str]:
        return True, "test harness"

    def _convert(self, request: SingingConversionRequest) -> SingingRender:
        return SingingRender(
            audio=self._guide_audio.clone(),
            sample_rate=self._sample_rate,
            engine_id=self.id,
            operation="conversion",
        )
