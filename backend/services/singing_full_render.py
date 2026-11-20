"""Full-length S5 singing render, with crash-safe, atomic public output.

Unlike render_preview, this service never truncates the guide. Its cap comes
from the caller's server-side policy and uses the existing S4 error contract.
The WAV becomes downloadable only after convert_singing has verified complete
output, duration drift, and synthetic-audio provenance. No cloud fallback.
"""
from __future__ import annotations

import os
from dataclasses import replace
from uuid import uuid4

from services.singing_conversion import (
    ConversionRequest,
    ConversionResult,
    EngineOutputError,
    InvalidConversionRequest,
    SingingConversionEngine,
    _output_path,
    convert_singing,
    wav_duration_seconds,
)
from services.singing_render_limits import full_render_duration_error


def render_full_singing(
    engine: SingingConversionEngine,
    request: ConversionRequest,
    *,
    max_seconds: object,
) -> ConversionResult:
    """Render a full guide WAV once per project, publishing only verified audio.

    A filesystem-exclusive lock coordinates worker threads and server processes
    using the same project directory. A crashed owner leaves a lock to be
    inspected during controlled maintenance; we never steal it based on age.
    Staged output is never served by the project's audio download endpoint.
    Publication is an atomic no-clobber hardlink within the renders directory:
    a pre-existing final render is never replaced or exposed while unfinished.
    """
    if request.output_name != "vocal_full.wav":
        raise InvalidConversionRequest(
            "full singing renders must write the project's vocal_full.wav"
        )
    guide_seconds, _sample_rate = wav_duration_seconds(request.guide_vocal)
    problem = full_render_duration_error(guide_seconds, max_seconds)
    if problem is not None:
        raise InvalidConversionRequest(problem)

    final = _output_path(request)  # retain S4 containment, traversal and symlink checks
    if final.exists():
        raise InvalidConversionRequest("vocal_full.wav already exists for this project")

    lock = final.with_name(".vocal_full.render.lock")
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise InvalidConversionRequest(
            "a full singing render is already in progress for this project"
        ) from exc
    except OSError as exc:
        raise EngineOutputError("could not reserve the project's full render") from exc
    os.close(fd)

    stage = final.with_name(f".vocal_full.{uuid4().hex}.wav")
    try:
        if final.exists():
            raise InvalidConversionRequest("vocal_full.wav already exists for this project")
        staged_request = replace(request, output_name=stage.name)
        result = convert_singing(engine, staged_request)  # S4 validation + provenance
        if result.output_path != stage:
            raise EngineOutputError("S4 conversion returned an unexpected staged path")
        try:
            os.link(stage, final)  # atomic publication, fails if the final file already exists
        except FileExistsError as exc:
            raise InvalidConversionRequest(
                "vocal_full.wav already exists for this project"
            ) from exc
        except OSError as exc:
            raise EngineOutputError("could not atomically publish the verified full render") from exc
        return replace(result, output_path=final)
    finally:
        try:
            stage.unlink(missing_ok=True)
        finally:
            lock.unlink(missing_ok=True)
