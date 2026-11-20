"""Full-length S5 rendering uses the existing S4 contract, not preview."""
from __future__ import annotations

import wave
from pathlib import Path

import pytest

from services import singing_full_render as full_render
from services.singing_conversion import ConversionRequest, InvalidConversionRequest


def _guide(path: Path, seconds: int = 2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * (seconds * 8000))
    return path


def _request(tmp_path: Path, *, name: str = "vocal_full.wav") -> ConversionRequest:
    return ConversionRequest(
        projects_root=tmp_path,
        project_id="demo",
        guide_vocal=_guide(tmp_path / "demo" / "source" / "guide_vocal.wav"),
        target_voice="voice-a",
        output_name=name,
    )


def test_full_render_passes_the_original_whole_song_to_the_s4_contract(tmp_path, monkeypatch):
    request = _request(tmp_path)
    calls = []
    expected = object()

    def convert(engine, given):
        calls.append((engine, given))
        return expected

    monkeypatch.setattr(full_render, "convert_singing", convert)
    engine = object()
    result = full_render.render_full_singing(engine, request, max_seconds=2.0)
    assert result is expected
    assert calls == [(engine, request)]
    assert request.guide_vocal.stat().st_size == 44 + 2 * 8000 * 2


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


def test_wrong_output_name_is_refused_before_creating_any_audio(tmp_path, monkeypatch):
    request = _request(tmp_path, name="preview.wav")
    monkeypatch.setattr(full_render, "convert_singing", lambda *_: pytest.fail("conversion started"))
    with pytest.raises(InvalidConversionRequest, match="vocal_full.wav"):
        full_render.render_full_singing(object(), request, max_seconds=600.0)


def test_non_wav_guide_is_refused_before_running_engine(tmp_path, monkeypatch):
    request = _request(tmp_path)
    request.guide_vocal.write_bytes(b"not a wave file")
    monkeypatch.setattr(full_render, "convert_singing", lambda *_: pytest.fail("conversion started"))
    with pytest.raises(InvalidConversionRequest, match="not a readable WAV"):
        full_render.render_full_singing(object(), request, max_seconds=600.0)
