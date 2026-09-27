from pathlib import Path

import pytest
import torch

from services.singing_backend import (
    DeterministicSingingBackend,
    SingingBackend,
    SingingCapabilities,
    SingingConversionRequest,
    SingingSynthesisRequest,
)

class SpeechOnlySingingBackend(SingingBackend):
    @classmethod
    def is_available(cls):
        return True, "test"

def _file(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(b"fixture")
    return path

def test_capabilities_fail_closed():
    caps = SingingCapabilities()
    assert caps.conversion is False
    assert caps.synthesis is False
    assert caps.pitch_conditioning is False
    assert caps.midi_input is False
    assert caps.musicxml_input is False

def test_unsupported_operations_never_fall_back_to_tts(tmp_path):
    backend = SpeechOnlySingingBackend()
    request = SingingConversionRequest(_file(tmp_path, "guide.wav"), _file(tmp_path, "voice.wav"))
    with pytest.raises(NotImplementedError, match="does not support singing conversion"):
        backend.convert(request)

def test_conversion_validates_inputs_before_engine_execution(tmp_path):
    backend = DeterministicSingingBackend(torch.zeros(1, 240))
    request = SingingConversionRequest(tmp_path / "missing.wav", _file(tmp_path, "voice.wav"))
    with pytest.raises(ValueError, match="guide_vocal"):
        backend.convert(request)

def test_deterministic_conversion_preserves_shape_timing_and_metadata(tmp_path):
    guide = torch.linspace(-0.5, 0.5, 480).unsqueeze(0)
    backend = DeterministicSingingBackend(guide, sample_rate=24000)
    request = SingingConversionRequest(_file(tmp_path, "guide.wav"), _file(tmp_path, "voice.wav"))
    render = backend.convert(request)
    assert render.operation == "conversion"
    assert render.engine_id == "deterministic-singing-test"
    assert render.sample_rate == 24000
    assert render.audio.shape == guide.shape
    assert torch.equal(render.audio, guide)
    assert render.audio.data_ptr() != guide.data_ptr()

def test_conversion_harness_cannot_claim_synthesis(tmp_path):
    backend = DeterministicSingingBackend(torch.zeros(1, 10))
    request = SingingSynthesisRequest(
        lyrics="la",
        melody=_file(tmp_path, "melody.mid"),
        melody_format="midi",
        target_voice=_file(tmp_path, "voice.wav"),
    )
    with pytest.raises(NotImplementedError, match="does not support singing synthesis"):
        backend.synthesize(request)
