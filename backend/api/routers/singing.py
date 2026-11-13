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
    GET  /singing/projects/{project_id}/audio/{which}  -> "guide" or "preview" WAV, for A/B playback
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from core.config import SINGING_DIR, VOICES_DIR
from core.db import db_conn
from core.path_security import UnsafePath, resolve_within
from services.singing_conversion import ConversionRequest, SingingConversionError
from services.singing_pitch import F0Track
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
        result = analyze_guide_vocal(guide_path)
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
        result = render_preview(engine, request)
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


@router.get("/projects/{project_id}/audio/{which}")
def project_audio(project_id: str, which: str) -> FileResponse:
    if which not in ("guide", "preview"):
        raise HTTPException(status_code=404, detail="Unknown singing workspace audio.")
    layout = singing_project_paths(project_id)
    if not layout:
        raise HTTPException(status_code=400, detail="Invalid singing project id.")
    relative = f"{layout['source_dir']}/guide_vocal.wav" if which == "guide" else layout["preview"]
    path = Path(SINGING_DIR) / relative
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio not found for this project.")
    return FileResponse(str(path), media_type="audio/wav")
