"""API contract tests for the Singing workspace router (``api.routers.singing``).

Mounts only the singing router on a bare FastAPI app (no ``main`` import, no torch at collection),
following the pattern of ``backend/tests/test_personas_api.py`` / ``test_archetypes_api.py``.
``conftest.py`` points ``OMNIVOICE_DATA_DIR`` at a throwaway tmpdir before the router imports
``SINGING_DIR`` / ``VOICES_DIR`` from the real ``core.config``.

A fake engine is registered directly into ``services.tts_backend._REGISTRY`` with
``singing_capabilities = {"singing_conversion"}`` -- the exact mechanism ``compatible_singing_engines``
and ``get_backend_class`` already use (see ``services/singing_preview.py`` and its own tests) -- so
nothing here needs RVC, or any other real engine, installed.
"""
from __future__ import annotations

import asyncio
import io
import time
import uuid
import wave

import numpy as np
import pytest

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.config import VOICES_DIR  # noqa: E402
from core.db import db_conn, init_db  # noqa: E402
from services.singing_conversion import EngineOutput, wav_duration_seconds  # noqa: E402
from api.routers import singing as singing_router  # noqa: E402

init_db()


def _wav_bytes(frequency: float = 220.0, seconds: float = 2.0, rate: int = 8000) -> bytes:
    t = np.arange(int(rate * seconds)) / rate
    samples = (0.5 * np.sin(2 * np.pi * frequency * t) * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())
    return buf.getvalue()


class _FakeSingingEngine:
    """Same shape as services/singing_preview's own test fake; registered as a real TTS backend id
    so the router's catalogue + ``get_backend_class`` lookup exercise the real resolution path."""

    id = "fake-singing-engine"
    display_name = "Fake Singing Engine"
    version = "0.0-test"
    singing_capabilities = frozenset({"singing_conversion"})

    @property
    def sample_rate(self) -> int:
        return 8000

    @property
    def supported_languages(self) -> list[str]:
        return ["en"]

    @classmethod
    def is_available(cls):
        return True, "ready"

    def convert(self, guide_vocal, target_voice, output, f0_track):
        from services import singing_preview as sp

        seconds, rate = wav_duration_seconds(guide_vocal)
        samples, _ = sp._load_mono_pcm16(guide_vocal)
        sp._write_mono_pcm16(output, samples, rate)
        return EngineOutput(rate, seconds, provenance={"engine": self.id, "target_voice": target_voice})


class _SpeechOnlyEngine(_FakeSingingEngine):
    id = "fake-speech-only"
    display_name = "Fake Speech-Only Engine"
    singing_capabilities = frozenset()  # speech cloning never implies singing compatibility

    def convert(self, *a, **k):  # pragma: no cover - never eligible, never called
        raise AssertionError("a speech-only engine must never be invoked for singing conversion")


@pytest.fixture(autouse=True)
def _registered_engines(monkeypatch: pytest.MonkeyPatch) -> None:
    # Imported here, not at module scope: tests/backend/conftest.py purges services.* from
    # sys.modules after every test in this tree, so a module-level reference would go stale and
    # split from the fresh module the router's own local imports re-resolve mid-test (see that
    # conftest's docstring). A local import always matches whatever generation is live right now.
    from services import tts_backend

    monkeypatch.setitem(tts_backend._REGISTRY, _FakeSingingEngine.id, _FakeSingingEngine)
    monkeypatch.setitem(tts_backend._REGISTRY, _SpeechOnlyEngine.id, _SpeechOnlyEngine)


@pytest.fixture(autouse=True)
def _no_watermark_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import watermark

    monkeypatch.setattr(watermark, "mark_synthetic", lambda waveform, rate, *, context, force=False: waveform)


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(singing_router.router)
    return TestClient(app)


@pytest.fixture()
def target_voice_profile() -> str:
    import os

    profile_id = f"test-{uuid.uuid4().hex}"
    os.makedirs(VOICES_DIR, exist_ok=True)
    filename = f"{profile_id}.wav"
    with open(f"{VOICES_DIR}/{filename}", "wb") as handle:
        handle.write(_wav_bytes(330.0, 1.0))
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO voice_profiles (id, name, ref_audio_path, created_at) VALUES (?, ?, ?, ?)",
            (profile_id, "Target Voice", filename, time.time()),
        )
        conn.commit()
    return profile_id


# ── GET /singing/engines ─────────────────────────────────────────────────


def test_list_engines_includes_the_singing_capable_engine_and_excludes_the_speech_only_one(client) -> None:
    response = client.get("/singing/engines")
    assert response.status_code == 200
    ids = {entry["id"] for entry in response.json()}
    assert _FakeSingingEngine.id in ids
    assert _SpeechOnlyEngine.id not in ids


# ── POST /singing/analyze ────────────────────────────────────────────────


def test_analyze_returns_f0_track_and_project(client) -> None:
    response = client.post(
        "/singing/analyze",
        files={"guide_vocal": ("guide.wav", _wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"]
    assert body["guide_audio_url"] == f"/singing/projects/{body['project_id']}/audio/guide"
    voiced = [f for f in body["guide_f0"] if f["voiced"]]
    assert len(voiced) > 10
    assert all(abs(f["frequency_hz"] - 220.0) < 10.0 for f in voiced)
    assert len(body["voiced_segments"]) == 1

    audio_response = client.get(body["guide_audio_url"])
    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"] == "audio/wav"


def test_analyze_rejects_a_non_wav_upload(client) -> None:
    response = client.post(
        "/singing/analyze",
        files={"guide_vocal": ("guide.txt", b"not audio", "text/plain")},
    )
    assert response.status_code == 400


def _off_event_loop(real, seen: list[bool]):
    """Wrap a service call so it records whether it ran on a thread with no running event loop."""

    def wrapper(*args, **kwargs):
        try:
            asyncio.get_running_loop()
            seen.append(False)
        except RuntimeError:
            seen.append(True)
        return real(*args, **kwargs)

    return wrapper


def test_analyze_runs_pitch_extraction_off_the_event_loop(client, monkeypatch: pytest.MonkeyPatch) -> None:
    # Review P1: a whole-song analysis on the loop thread froze every other request.
    seen: list[bool] = []
    monkeypatch.setattr(
        singing_router, "analyze_guide_vocal", _off_event_loop(singing_router.analyze_guide_vocal, seen)
    )
    response = client.post(
        "/singing/analyze",
        files={"guide_vocal": ("guide.wav", _wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 200
    assert seen == [True]


def test_preview_renders_off_the_event_loop(
    client, target_voice_profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[bool] = []
    monkeypatch.setattr(
        singing_router, "render_preview", _off_event_loop(singing_router.render_preview, seen)
    )
    response = client.post(
        "/singing/preview",
        files={"guide_vocal": ("guide.wav", _wav_bytes(), "audio/wav")},
        data={"engine_id": _FakeSingingEngine.id, "target_voice_profile_id": target_voice_profile},
    )
    assert response.status_code == 200
    assert seen == [True]


# ── POST /singing/preview ────────────────────────────────────────────────


def test_preview_renders_and_returns_both_f0_tracks_and_ab_audio(client, target_voice_profile) -> None:
    response = client.post(
        "/singing/preview",
        files={"guide_vocal": ("guide.wav", _wav_bytes(), "audio/wav")},
        data={"engine_id": _FakeSingingEngine.id, "target_voice_profile_id": target_voice_profile},
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert len(body["guide_f0"]) == len(body["output_f0"]) == len(body["cents_diff"])
    assert body["engine_id"] == _FakeSingingEngine.id
    assert body["within_tolerance"] is True
    assert body["provenance"]["target_voice"]

    guide_audio = client.get(body["guide_audio_url"])
    preview_audio = client.get(body["preview_audio_url"])
    assert guide_audio.status_code == preview_audio.status_code == 200


def test_preview_refuses_a_speech_only_engine_with_a_clear_message(client, target_voice_profile) -> None:
    response = client.post(
        "/singing/preview",
        files={"guide_vocal": ("guide.wav", _wav_bytes(), "audio/wav")},
        data={"engine_id": _SpeechOnlyEngine.id, "target_voice_profile_id": target_voice_profile},
    )
    assert response.status_code == 400
    assert "singing" in response.json()["detail"].lower()


def test_preview_refuses_an_unknown_engine(client, target_voice_profile) -> None:
    response = client.post(
        "/singing/preview",
        files={"guide_vocal": ("guide.wav", _wav_bytes(), "audio/wav")},
        data={"engine_id": "not-a-real-engine", "target_voice_profile_id": target_voice_profile},
    )
    assert response.status_code == 400


def test_preview_refuses_an_unknown_target_voice(client) -> None:
    response = client.post(
        "/singing/preview",
        files={"guide_vocal": ("guide.wav", _wav_bytes(), "audio/wav")},
        data={"engine_id": _FakeSingingEngine.id, "target_voice_profile_id": "does-not-exist"},
    )
    assert response.status_code == 404


# ── GET /singing/projects/{id}/audio/{which} ─────────────────────────────


def test_audio_endpoint_404s_for_an_unknown_project_or_kind(client) -> None:
    assert client.get("/singing/projects/not-a-real-project/audio/guide").status_code == 404
    assert client.get("/singing/projects/a:b/audio/guide").status_code == 400
    response = client.post(
        "/singing/analyze",
        files={"guide_vocal": ("guide.wav", _wav_bytes(), "audio/wav")},
    )
    project_id = response.json()["project_id"]
    assert client.get(f"/singing/projects/{project_id}/audio/preview").status_code == 404
    assert client.get(f"/singing/projects/{project_id}/audio/not-a-kind").status_code == 404
