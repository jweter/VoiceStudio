"""Golden-fixture checks for the deterministic Singing Mode F0 comparator."""

import numpy as np
import pytest

from services.singing_pitch import F0Frame, F0Track, extract_f0
from services.singing_pitch_metrics import compare_f0_tracks


def test_golden_two_note_audio_with_silence() -> None:
    rate = 48000
    hop = 2400

    def tone(hz: float, seconds: float) -> np.ndarray:
        times = np.arange(int(rate * seconds), dtype=np.float64) / rate
        return 0.5 * np.sin(2 * np.pi * hz * times)

    audio = np.concatenate(
        (tone(220.0, 0.30), tone(440.0, 0.30), np.zeros(int(rate * 0.20)))
    )
    measured = extract_f0(
        audio,
        rate,
        hop_samples=hop,
        frame_samples=4096,
        min_hz=100.0,
        max_hz=600.0,
        voicing_threshold=0.5,
    )
    indices = (1, 2, 3, 7, 8, 9, 15)
    expected_hz = (220.0, 220.0, 220.0, 440.0, 440.0, 440.0, None)
    reference = F0Track(
        rate,
        hop,
        tuple(
            F0Frame(measured.frames[i].time_seconds, hz, hz is not None, 1.0)
            for i, hz in zip(indices, expected_hz)
        ),
    )
    candidate = F0Track(rate, hop, tuple(measured.frames[i] for i in indices))
    metrics = compare_f0_tracks(reference, candidate)

    assert metrics.frame_count == 7
    assert metrics.paired_voiced_count == 6
    assert metrics.voiced_agreement_rate == 1.0
    assert metrics.mean_absolute_cents is not None
    assert metrics.mean_absolute_cents < 50.0
    assert metrics.octave_error_rate == 0.0


def test_octave_displacement_and_voicing_disagreement_are_visible() -> None:
    reference = F0Track(
        48000,
        480,
        (
            F0Frame(0.0, 220.0, True, 1.0),
            F0Frame(0.01, 440.0, True, 1.0),
            F0Frame(0.02, None, False, 0.0),
        ),
    )
    candidate = F0Track(
        48000,
        480,
        (
            F0Frame(0.0, 440.0, True, 1.0),
            F0Frame(0.01, 440.0, True, 1.0),
            F0Frame(0.02, 220.0, True, 1.0),
        ),
    )
    result = compare_f0_tracks(reference, candidate)
    assert result.paired_voiced_count == 2
    assert result.voiced_agreement_rate == pytest.approx(2 / 3)
    assert result.mean_absolute_cents == pytest.approx(600.0)
    assert result.octave_error_rate == pytest.approx(0.5)


def test_unvoiced_only_and_empty_tracks_are_defined() -> None:
    empty = F0Track(48000, 480, ())
    assert compare_f0_tracks(empty, empty).voiced_agreement_rate == 1.0
    assert compare_f0_tracks(empty, empty).mean_absolute_cents is None
    silence = F0Track(48000, 480, (F0Frame(0.0, None, False, 0.0),))
    assert compare_f0_tracks(silence, silence).octave_error_rate is None


def test_misaligned_or_mismatched_tracks_are_rejected() -> None:
    reference = F0Track(48000, 480, (F0Frame(0.0, 220.0, True, 1.0),))
    misaligned = F0Track(48000, 480, (F0Frame(0.01, 220.0, True, 1.0),))
    with pytest.raises(ValueError, match="sample-aligned"):
        compare_f0_tracks(reference, misaligned)
    with pytest.raises(ValueError, match="sampling"):
        compare_f0_tracks(reference, F0Track(44100, 480, reference.frames))
    with pytest.raises(ValueError, match="frame counts"):
        compare_f0_tracks(reference, F0Track(48000, 480, ()))
