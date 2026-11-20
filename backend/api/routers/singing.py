"""Singing workspace API (Singing Mode S5 UI, docs/projects/singing-mode.md).

Kept deliberately separate from ``/generate`` and every other speech endpoint (the project's
documented "API direction"): a speech synthesis call can never satisfy a singing request, and this
router never imports a speech backend or falls back to one. It is a thin HTTP wrapper around the
already-delivered ``services.singing_preview`` composition (S5 backend slice, #31) -- all pitch
analysis, bounded preview rendering and engine-eligibility checks happen there and in
``services.singing_conversion``; this module only moves bytes and translates errors into HTTP status
codes.

    GET  /singing/engines                        -> compatible singing-conversion engines
    POST /singing/analyze                        -> guide vocal F0 track + voiced segments
    POST /singing/preview                        -> bounded conversion preview + pitch comparison
    POST /singing/render                         -> full render within server-owned duration cap
    GET  /singing/projects/{project_id}/export/{format} -> offline finished vocal export
    GET  /singing/projects/{project_id}/audio/{which}  -> "guide" or "preview" WAV, for A/B playback
"""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from core.config import SINGING_DIR, SINGING_FULL_RENDER_MAX_SECONDS, VOICES_DIR
from core.http_headers import content_disposition
from core.db import db_conn
from core.path_security import UnsafePath, resolve_within
from services.singing_conversion import ConversionRequest, SingingConversionError
from services.singing_pitch import F0Track
from services.singing_export_format import SINGING_EXPORT_CODEC_ARGS, singing_export_codec_args
from services.singing_full_render import render_full_singing
from services.ffmpeg_utils import find_ffmpeg, run_ffmpeg
from services.singing_preview import analyze_guide_vocal, compatible_singing_engines, render_preview
from services.singing_project import create_singing_project, singing_project_paths

router = APIRouter(prefix="/singing", tags=["singing"])

# A guide vocal is a whole song, not a short reference clip: cap matches the other large-upload
# route (profiles.py replace_profile_audio) rather than the much smaller voice-reference limit.
_MAX_UPLOAD_BYTES = 128 * 1024 * 1024
_UPLOAD_CHUNK = 1024 * 1024


def _f0_payload(track: F0Track) -> list[dict]:
    return [
        {
            "time_seconds": frame.time_seconds,
            "frequency_hz": frame.frequency_hz,
            "voiced": frame.voiced,
        }
        for frame in track.frames
    ]


async def _save_upload(upload: UploadFile, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with open(dest, "wb") as handle:
        while chunk := await upload.read(_UPLOAD_CHUNK):
            total += len(chunk)
            if total > _MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Guide vocal is too large (limit 128 MB).")
            handle.write(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="Guide vocal upload was empty.")


def _new_project() -> tuple[str, dict]:
    project_id = uuid.uuid4().hex
    layout = create_singing_project(SINGING_DIR, project_id)
    if not layout:
        raise HTTPException(status_code=500, detail="Could not create a singing workspace project.")
    return project_id, layout


def _resolve_target_voice(target_voice_profile_id: str) -> str:
    """Absolute, VOICES_DIR-contained path of the chosen profile's reference audio."""
    with db_conn() as conn:
        row = conn.execute(
            "SELECT ref_audio_path, locked_audio_path FROM voice_profiles WHERE id = ?",
            (target_voice_profile_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Target voice was not found.")
    audio = row["locked_audio_path"] or row["ref_audio_path"]
    if not audio:
        raise HTTPException(status_code=400, detail="Target voice has no reference audio yet.")
    try:
        return str(resolve_within(VOICES_DIR, audio))
    except UnsafePath as exc:
        raise HTTPException(status_code=400, detail="Target voice reference is invalid.") from exc


def _resolve_engine(engine_id: str):
    """A compatible-singing-engine instance for ``engine_id``, or a 400 naming why it is refused.

    Eligibility is re-checked against the same catalogue the picker was built from (defense in
    depth: ``convert_singing`` itself refuses an ineligible engine too, but this gives a clearer,
    earlier message, matching the "missing or incompatible engine" acceptance criterion).
    """
    compatible_ids = {entry["id"] for entry in compatible_singing_engines()}
    if engine_id not in compatible_ids:
        raise HTTPException(
            status_code=400,
            detail=f"{engine_id!r} is not an installed engine that supports singing conversion.",
        )
    from services.tts_backend import get_backend_class

    try:
        engine_cls = get_backend_class(engine_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return engine_cls()


@router.get("/engines")
def list_singing_engines() -> list[dict]:
    """Engines eligible for singing conversion -- never a speech-only engine (S1 catalogue filtering)."""
    return compatible_singing_engines()


@router.post("/analyze")
async def analyze(guide_vocal: UploadFile = File(...)) -> dict:
    """F0 track + voiced segments of an uploaded guide vocal, for the workspace's "Analyze" step."""
    project_id, layout = _new_project()
    guide_path = Path(SINGING_DIR) / layout["source_dir"] / "guide_vocal.wav"
    await _save_upload(guide_vocal, guide_path)
    try:
        # Pitch extraction is CPU-bound for the whole song: keep it off the event loop so
        # /health and every other request stay served while it runs.
        result = await asyncio.to_thread(analyze_guide_vocal, guide_path)
    except SingingConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "project_id": project_id,
        "guide_audio_url": f"/singing/projects/{project_id}/audio/guide",
        "guide_f0": _f0_payload(result.f0_track),
        "voiced_segments": [
            {"start_seconds": start, "end_seconds": end} for start, end in result.voiced_segments
        ],
    }


@router.post("/preview")
async def preview(
    guide_vocal: UploadFile = File(...),
    engine_id: str = Form(...),
    target_voice_profile_id: str = Form(...),
) -> dict:
    """Render a bounded conversion preview and compare the guide's and the output's pitch."""
    engine = _resolve_engine(engine_id)
    target_voice = _resolve_target_voice(target_voice_profile_id)
    project_id, layout = _new_project()
    guide_path = Path(SINGING_DIR) / layout["source_dir"] / "guide_vocal.wav"
    await _save_upload(guide_vocal, guide_path)
    request = ConversionRequest(
        projects_root=Path(SINGING_DIR),
        project_id=project_id,
        guide_vocal=guide_path,
        target_voice=target_voice,
        output_name="preview.wav",
    )
    try:
        result = await asyncio.to_thread(render_preview, engine, request)
    except SingingConversionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "project_id": project_id,
        "guide_audio_url": f"/singing/projects/{project_id}/audio/guide",
        "preview_audio_url": f"/singing/projects/{project_id}/audio/preview",
        "guide_f0": _f0_payload(result.guide_f0),
        "output_f0": _f0_payload(result.output_f0),
        "cents_diff": [
            {"time_seconds": frame.time_seconds, "cents": frame.cents} for frame in result.cents_diff
        ],
        "duration_seconds": result.conversion.duration_seconds,
        "guide_duration_seconds": result.conversion.guide_duration_seconds,
        "within_tolerance": result.conversion.within_tolerance,
        "engine_id": result.conversion.engine_id,
        "engine_version": result.conversion.engine_version,
        "provenance": result.provenance,
    }


@router.post("/render")
async def render_full(
    project_id: str = Form(...),
    engine_id: str = Form(...),
    target_voice_profile_id: str = Form(...),
) -> dict:
    """Render the project's complete guide vocal with the S4 singing contract.

    The duration cap comes from server configuration, never the client. Existing
    project files and conversion outputs are never overwritten, and a missing
    singing engine cannot silently fall back to speech synthesis.
    """
    layout = singing_project_paths(project_id)
    if not layout:
        raise HTTPException(status_code=400, detail="Invalid singing project id.")
    guide_path = Path(SINGING_DIR) / layout["source_dir"] / "guide_vocal.wav"
    if not guide_path.is_file():
        raise HTTPException(status_code=404, detail="Guide vocal not found for this project.")
    engine = _resolve_engine(engine_id)
    target_voice = _resolve_target_voice(target_voice_profile_id)
    request = ConversionRequest(
        projects_root=Path(SINGING_DIR),
        project_id=project_id,
        guide_vocal=guide_path,
        target_voice=target_voice,
        output_name="vocal_full.wav",
    )
    try:
        result = await asyncio.to_thread(
            render_full_singing, engine, request, max_seconds=SINGING_FULL_RENDER_MAX_SECONDS,
        )
    except SingingConversionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "project_id": project_id,
        "render_audio_url": f"/singing/projects/{project_id}/audio/full",
        "duration_seconds": result.duration_seconds,
        "guide_duration_seconds": result.guide_duration_seconds,
        "within_tolerance": result.within_tolerance,
        "engine_id": result.engine_id,
        "engine_version": result.engine_version,
        "provenance": result.provenance,
    }


@router.get("/projects/{project_id}/audio/{which}")
def project_audio(project_id: str, which: str) -> FileResponse:
    if which not in ("guide", "preview", "full"):
        raise HTTPException(status_code=404, detail="Unknown singing workspace audio.")
    layout = singing_project_paths(project_id)
    if not layout:
        raise HTTPException(status_code=400, detail="Invalid singing project id.")
    relative = (f"{layout['source_dir']}/guide_vocal.wav" if which == "guide"
                else layout["vocal_full"] if which == "full" else layout["preview"])
    path = Path(SINGING_DIR) / relative
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio not found for this project.")
    return FileResponse(str(path), media_type="audio/wav")


_EXPORT_MIME = {
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
}


@router.get("/projects/{project_id}/export/{container_format}")
async def export_full_render(project_id: str, container_format: str) -> FileResponse:
    """Download a verified full singing render; transcode solely with local ffmpeg.

    Exact allowlisting occurs before paths, commands or filenames are formed.
    A per-project/per-format exclusive lock prevents duplicate transcodes;
    the exported file is published atomically only after ffmpeg succeeds.
    """
    fmt = container_format.lower()
    if fmt not in SINGING_EXPORT_CODEC_ARGS:
        raise HTTPException(status_code=400, detail="Export format must be wav, m4a, mp3 or flac.")
    layout = singing_project_paths(project_id)
    if not layout:
        raise HTTPException(status_code=400, detail="Invalid singing project id.")
    root = Path(SINGING_DIR)
    project = root / project_id
    renders = root / layout["renders_dir"]
    original = root / layout["vocal_full"]
    if project.is_symlink() or renders.is_symlink() or original.is_symlink():
        raise HTTPException(status_code=400, detail="Singing project contains an unsafe audio path.")
    if not original.is_file():
        raise HTTPException(status_code=404, detail="A verified full singing render is required before export.")
    name = f"vocal_full.{fmt}"
    if fmt == "wav":
        return FileResponse(
            str(original), media_type=_EXPORT_MIME[fmt],
            headers={"Content-Disposition": content_disposition(name)},
        )

    finished = renders / name
    if finished.is_symlink():
        raise HTTPException(status_code=400, detail="Export output path is not safe.")
    if finished.is_file():
        return FileResponse(
            str(finished), media_type=_EXPORT_MIME[fmt],
            headers={"Content-Disposition": content_disposition(name)},
        )
    lock = renders / f".{name}.export.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail="Export is already running for this format.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to reserve export output.") from exc
    os.close(fd)

    stage = renders / f".vocal_full.{uuid.uuid4().hex}.{fmt}"
    try:
        if finished.exists():
            raise HTTPException(status_code=409, detail="Export output already exists.")
        binary = find_ffmpeg()  # already-installed local binary; does not download models or media tools
        if not binary:
            raise HTTPException(status_code=503, detail="Local ffmpeg is not installed.")
        cmd = [
            binary, "-nostdin", "-hide_banner", "-loglevel", "error",
            "-i", str(original), "-vn",
            *singing_export_codec_args(fmt), str(stage),
        ]
        try:
            result, _stdout, _stderr = await run_ffmpeg(cmd, timeout=1800.0)
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Singing export timed out.") from exc
        except OSError as exc:
            raise HTTPException(status_code=502, detail="Local ffmpeg could not run.") from exc
        if result != 0 or not stage.is_file() or stage.stat().st_size == 0:
            raise HTTPException(status_code=502, detail="Local ffmpeg could not produce this format.")
        try:
            os.link(stage, finished)  # no-clobber publication only after successful encoding
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail="Export output already exists.") from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail="Unable to publish completed export.") from exc
    finally:
        try:
            stage.unlink(missing_ok=True)
        finally:
            lock.unlink(missing_ok=True)

    return FileResponse(
        str(finished), media_type=_EXPORT_MIME[fmt],
        headers={"Content-Disposition": content_disposition(name)},
    )
