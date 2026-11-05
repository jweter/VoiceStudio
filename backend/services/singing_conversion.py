"""Engine-independent contract for singing voice conversion (Singing Mode slice S4).

``convert_singing`` is the only door between a guide vocal and a conversion engine:

* the engine must declare ``singing_conversion`` through the S1 capability vocabulary
  (``tts_backend.singing_capabilities``); speech or speaker-clone support never qualifies and there is **no fallback
  to speech synthesis** -- an ineligible engine is refused before it is called, and this module never imports or
  calls a speech backend;
* the output must land in the S2 project's ``renders`` directory (``singing_project_paths``);
* the guide vocal stays the timing authority: the converted audio's measured duration is compared with the guide
  vocal's within a stated tolerance and the drift is reported (and refused by default when it exceeds it);
* the optional S3 ``F0Track`` of the guide vocal is handed to the engine unchanged.

Engines are plain objects with ``id``, ``version``, ``singing_capabilities`` and ``convert(request)``; the first real
adapter (RVC, see docs/projects/singing-engine-evaluation.md) is added behind this contract.  Only the standard
library is used here (WAV durations are read with ``wave``).
"""
from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from services.singing_project import singing_project_paths

if TYPE_CHECKING:  # pragma: no cover - typing only; keeps numpy out of the import path
    from services.singing_pitch import F0Track

CONVERSION_CAPABILITY = "singing_conversion"
# Converted audio may differ from the guide vocal by at most this much before it no longer lines up with the melody
# and timing the guide defines.  50 ms is below the 80 ms the S3 golden fixtures treat as one analysis frame pair.
DEFAULT_DURATION_TOLERANCE_SECONDS = 0.05


class SingingConversionError(ValueError):
    """Base class: every refusal of this contract is a ValueError with a human-readable reason."""


class EngineNotEligible(SingingConversionError):
    """The engine does not declare ``singing_conversion``; it is never called and nothing replaces it."""


class InvalidConversionRequest(SingingConversionError):
    """The request names a missing guide vocal, an unusable target voice or an output outside the project renders."""


class EngineOutputError(SingingConversionError):
    """The engine reported success but its output is missing, unreadable or inconsistent with its own report."""


class DurationDriftError(SingingConversionError):
    """Converted audio drifts from the guide vocal by more than the tolerance; ``result`` carries the evidence."""

    def __init__(self, message: str, result: "ConversionResult") -> None:
        super().__init__(message)
        self.result = result


@dataclass(frozen=True)
class ConversionRequest:
    """One conversion: a guide vocal, a target voice reference and where in the project the result goes."""

    projects_root: Path
    project_id: str
    guide_vocal: Path
    target_voice: str
    output_name: str
    f0_track: "F0Track | None" = None


@dataclass(frozen=True)
class EngineOutput:
    """What an engine says it wrote; the contract verifies it against the file, it does not trust it."""

    sample_rate: int
    duration_seconds: float


@dataclass(frozen=True)
class ConversionResult:
    output_path: Path
    sample_rate: int
    duration_seconds: float
    guide_duration_seconds: float
    drift_seconds: float
    tolerance_seconds: float
    within_tolerance: bool
    engine_id: str
    engine_version: str


class SingingConversionEngine(Protocol):
    id: str
    version: str
    singing_capabilities: frozenset[str]

    def convert(self, guide_vocal: Path, target_voice: str, output: Path, f0_track: "F0Track | None") -> EngineOutput:
        """Write a converted vocal to ``output`` (a ``.wav`` inside the project's renders directory)."""


def wav_duration_seconds(path: Path) -> tuple[float, int]:
    """(duration in seconds, sample rate) of a PCM WAV file; raises ``EngineOutputError``/``InvalidConversionRequest``."""
    try:
        with wave.open(str(path), "rb") as handle:
            rate, frames = handle.getframerate(), handle.getnframes()
    except (OSError, EOFError, wave.Error) as exc:
        raise InvalidConversionRequest(f"{path.name} is not a readable WAV file: {exc}") from exc
    if rate <= 0:
        raise InvalidConversionRequest(f"{path.name} has an invalid sample rate")
    return frames / rate, rate


def _declares_singing_conversion(engine: object) -> bool:
    """True only when the engine's S1 capability metadata is valid and lists ``singing_conversion``."""
    from services.tts_backend import _singing_capabilities_for  # S1 validation: invalid metadata fails closed

    return CONVERSION_CAPABILITY in _singing_capabilities_for(type(engine))


def _output_path(request: ConversionRequest) -> Path:
    layout = singing_project_paths(request.project_id)
    if not layout:
        raise InvalidConversionRequest("project_id is not a valid singing project id")
    name = request.output_name
    if (not isinstance(name, str) or not name.lower().endswith(".wav") or name != Path(name).name
            or name in {".wav"} or any(char in name for char in '/\\:*?"<>|\x00')):
        raise InvalidConversionRequest("output_name must be a plain file name ending in .wav")
    root = Path(request.projects_root)
    renders = root / layout["renders_dir"]
    if not renders.is_dir() or renders.is_symlink():
        raise InvalidConversionRequest("the project's renders directory does not exist (create the project first)")
    target = renders / name
    try:
        target.resolve(strict=False).relative_to(renders.resolve())
    except ValueError as exc:
        raise InvalidConversionRequest("output would leave the project's renders directory") from exc
    if target.is_symlink():
        raise InvalidConversionRequest("output must not be a symbolic link")
    return target


def convert_singing(engine: SingingConversionEngine, request: ConversionRequest, *,
                    tolerance_seconds: float = DEFAULT_DURATION_TOLERANCE_SECONDS,
                    allow_drift: bool = False) -> ConversionResult:
    """Run one conversion through ``engine`` and return verified evidence, or raise a ``SingingConversionError``."""
    if not _declares_singing_conversion(engine):
        raise EngineNotEligible(
            f"engine {getattr(engine, 'id', type(engine).__name__)!r} does not declare {CONVERSION_CAPABILITY}; "
            "speech synthesis is never used as a fallback")
    if not isinstance(request.target_voice, str) or not request.target_voice.strip():
        raise InvalidConversionRequest("target_voice must be a non-empty voice reference")
    guide = Path(request.guide_vocal)
    if not guide.is_file():
        raise InvalidConversionRequest("guide_vocal does not exist")
    if not tolerance_seconds >= 0:
        raise InvalidConversionRequest("tolerance_seconds must be non-negative")
    guide_duration, _ = wav_duration_seconds(guide)
    output = _output_path(request)
    if output.exists():  # never overwrite, and never mistake a leftover file for what the engine just produced
        raise InvalidConversionRequest(f"{output.name} already exists in the project's renders directory")

    produced = engine.convert(guide, request.target_voice, output, request.f0_track)

    if not output.is_file():
        raise EngineOutputError("the engine did not write its output file")
    measured, measured_rate = wav_duration_seconds(output)
    if produced.sample_rate != measured_rate:
        raise EngineOutputError(f"engine reported {produced.sample_rate} Hz but wrote {measured_rate} Hz")
    if abs(produced.duration_seconds - measured) > 1 / measured_rate:
        raise EngineOutputError(f"engine reported {produced.duration_seconds:.3f}s but wrote {measured:.3f}s")
    drift = measured - guide_duration
    result = ConversionResult(
        output_path=output, sample_rate=measured_rate, duration_seconds=measured, guide_duration_seconds=guide_duration,
        drift_seconds=drift, tolerance_seconds=tolerance_seconds, within_tolerance=abs(drift) <= tolerance_seconds,
        engine_id=str(engine.id), engine_version=str(engine.version))
    if not result.within_tolerance and not allow_drift:
        raise DurationDriftError(
            f"converted audio is {measured:.3f}s against a {guide_duration:.3f}s guide vocal "
            f"(drift {drift:+.3f}s, tolerance {tolerance_seconds:.3f}s)", result)
    return result
