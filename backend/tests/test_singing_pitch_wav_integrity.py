"""Truncated PCM inputs must not produce apparently valid Singing Mode F0 evidence."""

import wave

import numpy as np
import pytest

from services.singing_pitch import extract_f0_wav


def _write_pcm(path):
    sample_rate = 48000
    samples = np.arange(9600, dtype=np.float64)
    pcm = np.round(0.5 * np.sin(2 * np.pi * 220.0 * samples / sample_rate) * 32767)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.astype("<i2").tobytes())


def test_complete_pcm_wav_extracts_pitch(tmp_path):
    path = tmp_path / "complete.wav"
    _write_pcm(path)
    result = extract_f0_wav(path)
    assert result.sample_rate == 48000
    assert any(frame.voiced for frame in result.frames)


@pytest.mark.parametrize("missing_bytes", [2, 6, 18])
def test_truncated_pcm_wav_is_rejected_instead_of_analyzed(tmp_path, missing_bytes):
    path = tmp_path / "truncated.wav"
    _write_pcm(path)
    path.write_bytes(path.read_bytes()[:-missing_bytes])
    with pytest.raises(ValueError, match="truncated PCM WAV"):
        extract_f0_wav(path)
