"""End-to-end pitch fidelity QA from real, locally generated PCM WAV inputs."""

import wave

import numpy as np
import pytest

from services.singing_audio_qa import compare_f0_wavs


def _write_tone(path, *, hz=220.0, sample_rate=48000, seconds=0.20, channels=1):
    times = np.arange(int(sample_rate * seconds)) / sample_rate
    mono = np.round(0.6 * np.sin(2 * np.pi * hz * times) * 32767).astype("<i2")
    pcm = np.repeat(mono[:, None], channels, axis=1).reshape(-1).tobytes()
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(pcm)


def _compare(reference, observed):
    return compare_f0_wavs(
        reference,
        observed,
        hop_samples=960,
        frame_samples=4096,
        min_hz=150.0,
        max_hz=500.0,
        voicing_threshold=0.4,
    )


def test_identical_guide_and_output_wavs_have_near_zero_pitch_error(tmp_path):
    reference = tmp_path / "guide.wav"
    output = tmp_path / "converted.wav"
    _write_tone(reference)
    _write_tone(output)
    result = _compare(reference, output)
    assert result.frame_count > 0
    assert result.paired_voiced_count > 0
    assert result.voiced_agreement_rate == 1.0
    assert result.mean_absolute_cents == pytest.approx(0.0)
    assert result.octave_error_rate == 0.0


def test_detuned_output_is_not_misreported_as_pitch_preserving(tmp_path):
    reference = tmp_path / "guide.wav"
    output = tmp_path / "detuned.wav"
    _write_tone(reference, hz=220.0)
    _write_tone(output, hz=330.0)
    result = _compare(reference, output)
    assert result.paired_voiced_count > 0
    assert result.mean_absolute_cents is not None
    assert result.mean_absolute_cents > 300.0


def test_mismatched_sample_rates_fail_instead_of_implicit_resampling(tmp_path):
    reference = tmp_path / "guide.wav"
    output = tmp_path / "other-rate.wav"
    _write_tone(reference, sample_rate=48000)
    _write_tone(output, sample_rate=44100)
    with pytest.raises(ValueError, match="matching sampling"):
        _compare(reference, output)


def test_stereo_input_fails_explicitly(tmp_path):
    reference = tmp_path / "guide.wav"
    output = tmp_path / "stereo.wav"
    _write_tone(reference)
    _write_tone(output, channels=2)
    with pytest.raises(ValueError, match="mono 16-bit PCM"):
        _compare(reference, output)
