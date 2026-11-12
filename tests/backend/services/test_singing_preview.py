"""Tests for the S5 headless workspace service: analyze_guide_vocal + render_preview.

Reuses the fake engine from the S4 contract tests (tests/backend/services/test_singing_conversion.py) so
nothing here requires RVC, or any other real engine, to be installed.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from services import singing_conversion as sc
from services import singing_preview as sp
from services.singing_project import create_singing_project

RATE = 8000


@pytest.fixture(autouse=True)
def _no_watermark_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep convert_singing's provenance chokepoint a deterministic no-op (same pattern the S4 contract tests use)
    so this slice's own tests never depend on AudioSeal weights being cached and never touch the network."""
    from services import watermark

    monkeypatch.setattr(watermark, "mark_synthetic", lambda waveform, rate, *, context, force=False: waveform)


class FakeEngine:
    """Same shape as the S4 contract tests' fake engine (tests/backend/services/test_singing_conversion.py)."""

    id = "fake-svc"
    version = "0.0-test"
    singing_capabilities = frozenset({"singing_conversion", "pitch_conditioning"})

    def __init__(self, stretch: float = 0.0, rate: int = RATE) -> None:
        self.calls: list[tuple] = []
        self.stretch, self.rate = stretch, rate

    def convert(self, guide_vocal, target_voice, output, f0_track):
        guide_seconds, _ = sc.wav_duration_seconds(guide_vocal)
        seconds = guide_seconds + self.stretch
        sp._write_mono_pcm16(output, np.zeros(round(seconds * self.rate)), self.rate)
        self.calls.append((guide_vocal, target_voice, output, f0_track))
        return sc.EngineOutput(self.rate, seconds)


class SpeechOnlyEngine(FakeEngine):
    id = "speech-clone"
    singing_capabilities = frozenset({"speaker_clone", "speaker_embedding"})  # clones voices, cannot sing


def tone_wav(path: Path, frequency: float, seconds: float, rate: int = RATE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(rate * seconds)) / rate
    samples = 0.5 * np.sin(2 * np.pi * frequency * t)
    sp._write_mono_pcm16(path, samples, rate)
    return path


@pytest.fixture()
def project(tmp_path: Path):
    layout = create_singing_project(tmp_path, "demo")
    assert layout
    guide = tone_wav(tmp_path / "demo" / "source" / "guide.wav", 220.0, 2.0)
    return tmp_path, guide


def request(project, **overrides) -> sc.ConversionRequest:
    root, guide = project
    values = dict(projects_root=root, project_id="demo", guide_vocal=guide, target_voice="voice-a", output_name="preview.wav")
    values.update(overrides)
    return sc.ConversionRequest(**values)


# ── analyze_guide_vocal ──────────────────────────────────────────────────


def test_analyze_returns_f0_track_and_voiced_segments_for_a_deterministic_fixture(project) -> None:
    _, guide = project

    result = sp.analyze_guide_vocal(guide)

    assert isinstance(result, sp.AnalysisResult)
    assert result.f0_track.sample_rate == RATE
    voiced = [f for f in result.f0_track.frames if f.voiced]
    assert len(voiced) > 10
    assert all(abs(f.frequency_hz - 220.0) < 10.0 for f in voiced)
    assert len(result.voiced_segments) == 1
    start, end = result.voiced_segments[0]
    assert start == pytest.approx(0.0, abs=0.02) and end == pytest.approx(2.0, abs=0.1)


def test_analyze_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(sc.InvalidConversionRequest):
        sp.analyze_guide_vocal(tmp_path / "nope.wav")


def test_analyze_rejects_non_wav_input(tmp_path: Path) -> None:
    junk = tmp_path / "not_audio.wav"
    junk.write_bytes(b"this is not a wav file at all")

    with pytest.raises(sc.InvalidConversionRequest):
        sp.analyze_guide_vocal(junk)


def test_analyze_rejects_a_truncated_wav(project) -> None:
    _, guide = project
    truncated = guide.with_name("cut.wav")
    truncated.write_bytes(guide.read_bytes()[:44])

    with pytest.raises(sc.InvalidConversionRequest, match="truncated"):
        sp.analyze_guide_vocal(truncated)


# ── render_preview ───────────────────────────────────────────────────────


def test_render_preview_converts_and_returns_f0_tracks_and_cents_diff(project) -> None:
    engine = FakeEngine(rate=RATE)

    result = sp.render_preview(engine, request(project))

    assert isinstance(result, sp.PreviewResult)
    assert result.conversion.output_path.is_file()
    assert result.conversion.within_tolerance is True
    assert result.guide_f0.frames and result.output_f0.frames
    assert len(result.cents_diff) == min(len(result.guide_f0.frames), len(result.output_f0.frames))
    # FakeEngine writes silence, so the "output" is unvoiced everywhere -- no frame pairs both voiced.
    assert all(frame.cents is None for frame in result.cents_diff)


def test_render_preview_cents_diff_is_near_zero_when_the_engine_preserves_pitch(project) -> None:
    class PitchPreservingEngine(FakeEngine):
        def convert(self, guide_vocal, target_voice, output, f0_track):
            samples, rate = sp._load_mono_pcm16(guide_vocal)
            sp._write_mono_pcm16(output, samples, rate)
            self.calls.append((guide_vocal, target_voice, output, f0_track))
            return sc.EngineOutput(rate, samples.size / rate)

    result = sp.render_preview(PitchPreservingEngine(rate=RATE), request(project))

    voiced_diffs = [frame.cents for frame in result.cents_diff if frame.cents is not None]
    assert voiced_diffs
    assert all(math.isfinite(c) and abs(c) < 5.0 for c in voiced_diffs)


def test_render_preview_bounds_the_excerpt_to_the_documented_maximum(project) -> None:
    root, _ = project
    long_guide = tone_wav(root / "demo" / "source" / "long.wav", 220.0, sp.MAX_PREVIEW_SECONDS + 5.0)
    engine = FakeEngine(rate=RATE)

    result = sp.render_preview(engine, request(project, guide_vocal=long_guide, output_name="bounded.wav"))

    assert result.conversion.guide_duration_seconds == pytest.approx(sp.MAX_PREVIEW_SECONDS)
    assert result.conversion.duration_seconds <= sp.MAX_PREVIEW_SECONDS + 1e-6


def test_render_preview_refuses_an_engine_without_singing_conversion(project) -> None:
    engine = SpeechOnlyEngine()

    with pytest.raises(sc.EngineNotEligible, match="singing_conversion"):
        sp.render_preview(engine, request(project))

    assert engine.calls == []


def test_render_preview_rejects_a_non_positive_bound(project) -> None:
    engine = FakeEngine(rate=RATE)

    with pytest.raises(sc.InvalidConversionRequest):
        sp.render_preview(engine, request(project), max_preview_seconds=0)


def test_render_preview_returns_the_s4_provenance(project) -> None:
    class ProvenanceEngine(FakeEngine):
        def convert(self, guide_vocal, target_voice, output, f0_track):
            out = super().convert(guide_vocal, target_voice, output, f0_track)
            return sc.EngineOutput(out.sample_rate, out.duration_seconds, provenance={"engine": "fake-svc", "input_sha256": "abc"})

    result = sp.render_preview(ProvenanceEngine(rate=RATE), request(project))

    assert result.provenance == {"engine": "fake-svc", "input_sha256": "abc"}
    assert result.provenance == result.conversion.provenance


# ── compatible_singing_engines ───────────────────────────────────────────


def test_compatible_singing_engines_reuses_s1_catalogue_filtering(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_list_backends(*, singing_capability=None):
        captured["singing_capability"] = singing_capability
        return [{"id": "fake-svc", "singing_capabilities": ["singing_conversion"]}]

    from services import tts_backend

    monkeypatch.setattr(tts_backend, "list_backends", fake_list_backends)

    rows = sp.compatible_singing_engines()

    assert captured["singing_capability"] == sc.CONVERSION_CAPABILITY
    assert rows == [{"id": "fake-svc", "singing_capabilities": ["singing_conversion"]}]
