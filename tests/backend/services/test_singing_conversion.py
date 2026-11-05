"""Contract tests for singing voice conversion (S4): a fake engine proves the contract, nothing real is run."""
from __future__ import annotations

import ast
import struct
import wave
from pathlib import Path

import pytest

from services import singing_conversion as sc
from services.singing_project import create_singing_project, singing_project_paths

RATE = 8000


def write_wav(path: Path, seconds: float, rate: int = RATE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack("<h", 0) * round(seconds * rate))
    return path


class FakeEngine:
    id = "fake-svc"
    version = "0.0-test"
    singing_capabilities = frozenset({"singing_conversion", "pitch_conditioning"})

    def __init__(self, stretch: float = 0.0, rate: int = RATE) -> None:
        self.calls: list[tuple] = []
        self.stretch, self.rate = stretch, rate

    def convert(self, guide_vocal, target_voice, output, f0_track):
        guide_seconds, _ = sc.wav_duration_seconds(guide_vocal)
        seconds = guide_seconds + self.stretch
        write_wav(output, seconds, self.rate)
        self.calls.append((guide_vocal, target_voice, output, f0_track))
        return sc.EngineOutput(self.rate, seconds)


class SpeechOnlyEngine(FakeEngine):
    id = "speech-clone"
    singing_capabilities = frozenset({"speaker_clone", "speaker_embedding"})  # clones voices, cannot sing


@pytest.fixture()
def project(tmp_path: Path):
    layout = create_singing_project(tmp_path, "demo")
    assert layout
    guide = write_wav(tmp_path / "demo" / "source" / "guide.wav", 2.0)
    return tmp_path, guide


def request(project, **overrides) -> sc.ConversionRequest:
    root, guide = project
    values = dict(projects_root=root, project_id="demo", guide_vocal=guide, target_voice="voice-a", output_name="out.wav")
    values.update(overrides)
    return sc.ConversionRequest(**values)


def test_a_fake_engine_passes_the_contract_and_the_result_is_verified_evidence(project) -> None:
    engine = FakeEngine()

    result = sc.convert_singing(engine, request(project))

    root, _ = project
    assert result.output_path == root / singing_project_paths("demo")["renders_dir"] / "out.wav"
    assert result.output_path.is_file() and result.sample_rate == RATE
    assert result.duration_seconds == pytest.approx(2.0) and result.guide_duration_seconds == pytest.approx(2.0)
    assert result.drift_seconds == pytest.approx(0.0) and result.within_tolerance is True
    assert (result.engine_id, result.engine_version) == ("fake-svc", "0.0-test")
    assert len(engine.calls) == 1 and engine.calls[0][1] == "voice-a"


def test_the_s3_pitch_track_reaches_the_engine_unchanged(project) -> None:
    sentinel = object()
    engine = FakeEngine()

    sc.convert_singing(engine, request(project, f0_track=sentinel))

    assert engine.calls[0][3] is sentinel


def test_an_engine_without_singing_conversion_is_refused_before_it_is_called(project) -> None:
    engine = SpeechOnlyEngine()

    with pytest.raises(sc.EngineNotEligible, match="singing_conversion"):
        sc.convert_singing(engine, request(project))

    assert engine.calls == []  # never called, and no output was produced by anything else
    root, _ = project
    assert list((root / "demo" / "renders").iterdir()) == []


def test_invalid_capability_metadata_fails_closed(project) -> None:
    class Typo(FakeEngine):
        singing_capabilities = frozenset({"singing_conversion", "made_up_capability"})  # S1 ignores all of it

    class AsString(FakeEngine):
        singing_capabilities = "singing_conversion"  # a bare string is not a capability set

    for engine_class in (Typo, AsString):
        with pytest.raises(sc.EngineNotEligible):
            sc.convert_singing(engine_class(), request(project))


def test_a_drifting_result_is_reported_and_refused_unless_explicitly_allowed(project) -> None:
    with pytest.raises(sc.DurationDriftError) as caught:
        sc.convert_singing(FakeEngine(stretch=0.5), request(project, output_name="drift1.wav"))

    evidence = caught.value.result
    assert evidence.drift_seconds == pytest.approx(0.5) and evidence.within_tolerance is False
    assert evidence.tolerance_seconds == sc.DEFAULT_DURATION_TOLERANCE_SECONDS

    allowed = sc.convert_singing(FakeEngine(stretch=0.5), request(project, output_name="drift2.wav"), allow_drift=True)
    assert allowed.within_tolerance is False and allowed.drift_seconds == pytest.approx(0.5)

    inside = sc.convert_singing(FakeEngine(stretch=0.03), request(project, output_name="drift3.wav"), tolerance_seconds=0.05)
    assert inside.within_tolerance is True
    short = sc.convert_singing(FakeEngine(stretch=-0.04), request(project, output_name="drift4.wav"))
    assert short.drift_seconds == pytest.approx(-0.04) and short.within_tolerance is True  # shorter counts too


def test_the_engines_own_report_is_checked_against_the_file(project) -> None:
    class Liar(FakeEngine):
        def convert(self, guide_vocal, target_voice, output, f0_track):
            write_wav(output, 2.0)
            return sc.EngineOutput(RATE, 5.0)  # claims 5 s, wrote 2 s

    class WrongRate(FakeEngine):
        def convert(self, guide_vocal, target_voice, output, f0_track):
            write_wav(output, 2.0)
            return sc.EngineOutput(44100, 2.0)

    class WritesNothing(FakeEngine):
        def convert(self, guide_vocal, target_voice, output, f0_track):
            return sc.EngineOutput(RATE, 2.0)

    for number, engine in enumerate((Liar(), WrongRate(), WritesNothing())):
        with pytest.raises(sc.EngineOutputError):
            sc.convert_singing(engine, request(project, output_name=f"case{number}.wav"))


def test_an_existing_output_is_never_overwritten_or_mistaken_for_the_engines_work(project) -> None:
    first = FakeEngine()
    sc.convert_singing(first, request(project))
    second = FakeEngine()

    with pytest.raises(sc.InvalidConversionRequest, match="already exists"):
        sc.convert_singing(second, request(project))

    assert second.calls == []  # the earlier file is untouched and the engine is not asked to replace it


def test_the_output_must_stay_inside_the_project_renders_directory(project) -> None:
    for name in ("../escape.wav", "sub/out.wav", "..\\escape.wav", "C:out.wav", "out.mp3", ".wav", "", "a\x00b.wav"):
        with pytest.raises(sc.InvalidConversionRequest):
            sc.convert_singing(FakeEngine(), request(project, output_name=name))
    with pytest.raises(sc.InvalidConversionRequest):
        sc.convert_singing(FakeEngine(), request(project, project_id="../other"))
    with pytest.raises(sc.InvalidConversionRequest, match="renders"):
        sc.convert_singing(FakeEngine(), request(project, project_id="missing"))


def test_missing_or_unusable_inputs_are_refused_without_calling_the_engine(project, tmp_path: Path) -> None:
    engine = FakeEngine()
    root, guide = project
    junk = root / "demo" / "source" / "not_audio.wav"
    junk.write_bytes(b"not a wav")
    bad = [request(project, guide_vocal=root / "nope.wav"), request(project, guide_vocal=junk),
           request(project, target_voice="   "), request(project, target_voice=None)]
    for case in bad:
        with pytest.raises(sc.InvalidConversionRequest):
            sc.convert_singing(engine, case)
    with pytest.raises(sc.InvalidConversionRequest):
        sc.convert_singing(engine, request(project), tolerance_seconds=-1)
    assert engine.calls == []


def test_an_existing_output_is_not_a_symlink_escape(project, tmp_path: Path) -> None:
    root, _ = project
    outside = root / "outside.wav"
    write_wav(outside, 1.0)
    link = root / "demo" / "renders" / "linked.wav"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available here")
    with pytest.raises(sc.InvalidConversionRequest):
        sc.convert_singing(FakeEngine(), request(project, output_name="linked.wav"))


def test_no_code_path_in_the_contract_reaches_speech_synthesis() -> None:
    source = Path(sc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    # the only backend import is the S1 capability validator, imported lazily; no generate/synthesis API is used
    assert imported <= {"__future__", "wave", "dataclasses", "pathlib", "typing", "services.singing_project",
                        "services.singing_pitch", "services.tts_backend"}
    for forbidden in ("get_active_tts_backend", "get_backend_class", ".generate(", "synthesize", "list_backends"):
        assert forbidden not in source
