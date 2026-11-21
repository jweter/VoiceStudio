"""The S5 full render only publishes an S4-verified whole-song result."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
import wave

import pytest

from services import singing_full_render as full_render
from services.singing_conversion import (
    ConversionRequest,
    ConversionResult,
    EngineOutputError,
    InvalidConversionRequest,
)


def _guide(path: Path, seconds: int = 2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * (seconds * 8000))
    return path


def _request(tmp_path: Path, *, name: str = "vocal_full.wav") -> ConversionRequest:
    (tmp_path / "demo" / "renders").mkdir(parents=True, exist_ok=True)
    return ConversionRequest(
        projects_root=tmp_path,
        project_id="demo",
        guide_vocal=_guide(tmp_path / "demo" / "source" / "guide_vocal.wav"),
        target_voice="voice-a",
        output_name=name,
    )


def _result(stage: Path) -> ConversionResult:
    return ConversionResult(
        output_path=stage,
        sample_rate=8000,
        duration_seconds=2.0,
        guide_duration_seconds=2.0,
        drift_seconds=0.0,
        tolerance_seconds=0.05,
        within_tolerance=True,
        engine_id="offline-fake",
        engine_version="1",
        provenance={"engine": "offline-fake"},
    )


def _artifacts(tmp_path: Path) -> list[str]:
    return sorted(p.name for p in (tmp_path / "demo" / "renders").iterdir())


def test_full_render_publishes_only_the_verified_whole_song(tmp_path, monkeypatch):
    request = _request(tmp_path)
    calls = []

    def convert(engine, given):
        calls.append((engine, given))
        stage = tmp_path / "demo" / "renders" / given.output_name
        assert given.guide_vocal == request.guide_vocal
        assert given.output_name.startswith(".vocal_full.")
        assert given.output_name.endswith(".wav")
        stage.write_bytes(b"verified offline WAV fixture")
        assert not (stage.parent / "vocal_full.wav").exists()
        return _result(stage)

    monkeypatch.setattr(full_render, "convert_singing", convert)
    engine = object()
    result = full_render.render_full_singing(engine, request, max_seconds=2.0)
    assert result.output_path == tmp_path / "demo" / "renders" / "vocal_full.wav"
    assert result.output_path.read_bytes() == b"verified offline WAV fixture"
    assert result.provenance == {"engine": "offline-fake"}
    assert calls[0][0] is engine
    assert _artifacts(tmp_path) == ["vocal_full.wav"]
    assert request.guide_vocal.stat().st_size == 44 + 2 * 8000 * 2

    with pytest.raises(InvalidConversionRequest, match="already exists"):
        full_render.render_full_singing(engine, request, max_seconds=2.0)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "cap, expected",
    [
        (1.0, "longer than the 1.0s full-render limit"),
        (0, "Full-render duration limit is not configured"),
        (None, "Full-render duration limit is not configured"),
    ],
)
def test_over_cap_or_unconfigured_limit_prevents_all_conversion(tmp_path, monkeypatch, cap, expected):
    request = _request(tmp_path)
    calls = []
    monkeypatch.setattr(full_render, "convert_singing", lambda *_: calls.append("called"))
    with pytest.raises(InvalidConversionRequest, match=expected):
        full_render.render_full_singing(object(), request, max_seconds=cap)
    assert calls == []
    assert _artifacts(tmp_path) == []


def test_wrong_output_name_is_refused_before_creating_any_audio(tmp_path, monkeypatch):
    request = _request(tmp_path, name="preview.wav")
    monkeypatch.setattr(full_render, "convert_singing", lambda *_: pytest.fail("conversion started"))
    with pytest.raises(InvalidConversionRequest, match="vocal_full.wav"):
        full_render.render_full_singing(object(), request, max_seconds=600.0)
    assert _artifacts(tmp_path) == []


def test_non_wav_guide_is_refused_before_running_engine(tmp_path, monkeypatch):
    request = _request(tmp_path)
    request.guide_vocal.write_bytes(b"not a wave file")
    monkeypatch.setattr(full_render, "convert_singing", lambda *_: pytest.fail("conversion started"))
    with pytest.raises(InvalidConversionRequest, match="not a readable WAV"):
        full_render.render_full_singing(object(), request, max_seconds=600.0)
    assert _artifacts(tmp_path) == []


def test_invalid_s4_output_is_not_published_or_left_as_a_retry_blocker(tmp_path, monkeypatch):
    request = _request(tmp_path)

    def rejected(_engine, staged):
        stage = tmp_path / "demo" / "renders" / staged.output_name
        stage.write_bytes(b"partial and unverified audio")
        raise EngineOutputError("duration report inconsistent")

    monkeypatch.setattr(full_render, "convert_singing", rejected)
    with pytest.raises(EngineOutputError, match="inconsistent"):
        full_render.render_full_singing(object(), request, max_seconds=600)
    assert _artifacts(tmp_path) == []  # neither public WAV, private stage nor lock remains


def test_overlapping_requests_never_write_or_serve_the_same_final_file(tmp_path, monkeypatch):
    request = _request(tmp_path)
    started, finish = Event(), Event()
    calls = []

    def convert(_engine, staged):
        stage = tmp_path / "demo" / "renders" / staged.output_name
        stage.write_bytes(b"partial unvalidated audio")
        calls.append(stage.name)
        started.set()
        assert finish.wait(5), "test did not release the first render"
        stage.write_bytes(b"validated result")
        return _result(stage)

    monkeypatch.setattr(full_render, "convert_singing", convert)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(full_render.render_full_singing, object(), request, max_seconds=600)
        assert started.wait(5), "first conversion never started"
        assert not (tmp_path / "demo" / "renders" / "vocal_full.wav").exists()
        try:
            with pytest.raises(InvalidConversionRequest, match="already in progress"):
                full_render.render_full_singing(object(), request, max_seconds=600)
        finally:
            finish.set()
        assert first.result(timeout=5).output_path.read_bytes() == b"validated result"
    assert len(calls) == 1
    assert _artifacts(tmp_path) == ["vocal_full.wav"]


def test_failed_publication_does_not_leave_any_public_or_private_artifact(tmp_path, monkeypatch):
    request = _request(tmp_path)

    def convert(_engine, staged):
        stage = tmp_path / "demo" / "renders" / staged.output_name
        stage.write_bytes(b"validated result")
        return _result(stage)

    monkeypatch.setattr(full_render, "convert_singing", convert)

    def deny_link(_src, _dst):
        raise OSError("hardlink unsupported")

    monkeypatch.setattr(full_render.os, "link", deny_link)
    with pytest.raises(EngineOutputError, match="atomically publish"):
        full_render.render_full_singing(object(), request, max_seconds=600)
    assert _artifacts(tmp_path) == []
