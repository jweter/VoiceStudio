"""Singing Mode S3 golden fixtures: known melodies generated in code, scored with the roadmap's metrics.

The fixtures are synthesized (deterministic, no recorded material, so nothing to license). They prove the analysis
contract -- cents error, voiced/unvoiced agreement, octave-error rate, segment onsets, serialization -- not that a
real voice will sound right; real-vocal checks remain a Product Reality step.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from services.singing_pitch import (
    F0Evaluation,
    F0Track,
    ReferenceNote,
    cents,
    evaluate_f0,
    extract_f0,
    voiced_segments,
)

SAMPLE_RATE = 16000
ANALYSIS = {"hop_samples": 160, "frame_samples": 1024, "min_hz": 80.0, "max_hz": 800.0, "voicing_threshold": 0.5}
FRAME_SECONDS = ANALYSIS["frame_samples"] / SAMPLE_RATE  # a window starts at its frame time, so onsets read early by <= this


def voice(frequency: float, seconds: float) -> np.ndarray:
    """A vowel-like tone: strong second and third harmonics make octave errors a real risk for the extractor."""
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    return sum(weight * np.sin(2 * np.pi * frequency * k * t) for k, weight in ((1, 0.5), (2, 0.3), (3, 0.2)))


def melody(notes: list[tuple[float | None, float]]) -> tuple[np.ndarray, list[ReferenceNote]]:
    audio, reference, cursor = [], [], 0.0
    for frequency, seconds in notes:
        audio.append(voice(frequency, seconds) if frequency else np.zeros(int(SAMPLE_RATE * seconds)))
        reference.append(ReferenceNote(cursor, cursor + seconds, frequency))
        cursor += seconds
    return np.concatenate(audio), reference


THREE_NOTES = [(261.63, 0.4), (None, 0.1), (329.63, 0.4), (None, 0.1), (392.0, 0.4)]  # C4 rest E4 rest G4


def test_a_known_three_note_melody_is_tracked_within_a_few_cents_with_no_octave_errors() -> None:
    audio, reference = melody(THREE_NOTES)
    result = evaluate_f0(extract_f0(audio, SAMPLE_RATE, **ANALYSIS), reference, edge_guard_seconds=0.05)

    assert isinstance(result, F0Evaluation) and result.frames_evaluated > 80
    assert result.voiced_agreement == 1.0
    assert result.median_abs_cents is not None and result.median_abs_cents <= 15.0
    assert result.p95_abs_cents is not None and result.p95_abs_cents <= 35.0
    assert result.octave_error_rate == 0.0


def test_note_onsets_and_durations_match_the_fixture_within_one_analysis_window() -> None:
    audio, reference = melody(THREE_NOTES)
    found = voiced_segments(extract_f0(audio, SAMPLE_RATE, **ANALYSIS), min_frames=3)
    expected = [(note.start_seconds, note.end_seconds) for note in reference if note.frequency_hz]

    assert len(found) == len(expected) == 3
    for (start, end), (want_start, want_end) in zip(found, expected, strict=True):
        assert -FRAME_SECONDS - 0.01 <= start - want_start <= 0.01  # reads early, never late
        assert abs(end - want_end) <= FRAME_SECONDS + 0.01
    assert abs((found[-1][1] - found[0][0]) - (expected[-1][1] - expected[0][0])) <= FRAME_SECONDS + 0.02  # no duration drift


def test_noise_and_silence_are_unvoiced() -> None:
    noise = np.random.default_rng(0).standard_normal(SAMPLE_RATE) * 0.3
    for audio in (noise, np.zeros(SAMPLE_RATE)):
        track = extract_f0(audio, SAMPLE_RATE, **ANALYSIS)
        result = evaluate_f0(track, [ReferenceNote(0.0, 1.0, None)])
        assert result.voiced_agreement >= 0.95 and result.median_abs_cents is None and result.octave_error_rate is None
        assert voiced_segments(track, min_frames=3) == ()


def test_an_octave_slip_is_counted_as_an_octave_error_and_a_small_detune_is_not() -> None:
    reference = [ReferenceNote(0.0, 0.05, 220.0)]
    from services.singing_pitch import F0Frame

    def track(frequency: float) -> F0Track:
        return F0Track(SAMPLE_RATE, 160, tuple(F0Frame(i * 0.01, frequency, True, 0.9) for i in range(5)))

    assert evaluate_f0(track(440.0), reference).octave_error_rate == 1.0
    assert evaluate_f0(track(110.0), reference).octave_error_rate == 1.0
    detuned = evaluate_f0(track(220.0 * 2 ** (30 / 1200)), reference)
    assert detuned.octave_error_rate == 0.0 and detuned.median_abs_cents == pytest.approx(30.0)


def test_the_measurement_is_deterministic_and_the_track_survives_serialization() -> None:
    audio, reference = melody(THREE_NOTES)
    first = extract_f0(audio, SAMPLE_RATE, **ANALYSIS)
    second = extract_f0(audio.copy(), SAMPLE_RATE, **ANALYSIS)
    assert first.to_json() == second.to_json()
    assert F0Track.from_dict(first.to_dict()) == first
    assert evaluate_f0(F0Track.from_dict(first.to_dict()), reference, edge_guard_seconds=0.05) == \
        evaluate_f0(first, reference, edge_guard_seconds=0.05)


def test_cents_is_signed_and_rejects_bad_frequencies() -> None:
    assert cents(440.0, 440.0) == 0.0
    assert cents(880.0, 440.0) == pytest.approx(1200.0)
    assert cents(220.0, 440.0) == pytest.approx(-1200.0)
    for bad in (0.0, -1.0, math.nan, math.inf):
        with pytest.raises(ValueError):
            cents(bad, 440.0)
        with pytest.raises(ValueError):
            cents(440.0, bad)


def test_invalid_reference_and_arguments_fail_loudly_not_silently() -> None:
    audio, reference = melody(THREE_NOTES)
    track = extract_f0(audio, SAMPLE_RATE, **ANALYSIS)
    for start, end, hz in ((0.5, 0.5, 220.0), (-1.0, 1.0, 220.0), (0.0, math.inf, 220.0), (0.0, 1.0, -5.0), (0.0, 1.0, 0.0)):
        with pytest.raises(ValueError):
            ReferenceNote(start, end, hz)
    with pytest.raises(ValueError, match="no frames"):
        evaluate_f0(track, [ReferenceNote(50.0, 51.0, 220.0)])
    with pytest.raises(ValueError, match="edge_guard"):
        evaluate_f0(track, reference, edge_guard_seconds=-0.1)
    with pytest.raises(ValueError, match="min_frames"):
        voiced_segments(track, min_frames=0)
    assert voiced_segments(F0Track(SAMPLE_RATE, 160, ())) == ()
