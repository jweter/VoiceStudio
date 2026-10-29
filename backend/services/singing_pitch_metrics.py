"""Deterministic F0 comparison metrics for Singing Mode golden fixtures."""

from __future__ import annotations

from dataclasses import dataclass
import math

from services.singing_pitch import F0Track


@dataclass(frozen=True)
class F0Comparison:
    """Metrics for sample-aligned reference and measured pitch tracks.

    An absent mean error or octave rate means there were no paired voiced frames.
    Octave error includes deviations of at least 1150 cents (an octave within
    50 cents, or a larger pitch displacement).
    """

    frame_count: int
    paired_voiced_count: int
    voiced_agreement_rate: float
    mean_absolute_cents: float | None
    octave_error_rate: float | None


def compare_f0_tracks(reference: F0Track, observed: F0Track) -> F0Comparison:
    """Compare aligned tracks without hiding unvoiced or missing frames."""
    if (
        reference.sample_rate != observed.sample_rate
        or reference.hop_samples != observed.hop_samples
        or len(reference.frames) != len(observed.frames)
    ):
        raise ValueError("F0 tracks must have matching sampling and frame counts")

    errors: list[float] = []
    agreements = 0
    for expected, actual in zip(reference.frames, observed.frames):
        if not math.isclose(
            expected.time_seconds,
            actual.time_seconds,
            rel_tol=0.0,
            abs_tol=0.5 / reference.sample_rate,
        ):
            raise ValueError("F0 tracks must have sample-aligned timestamps")
        agreements += expected.voiced == actual.voiced
        if expected.voiced and actual.voiced:
            assert expected.frequency_hz is not None
            assert actual.frequency_hz is not None
            errors.append(
                abs(
                    1200.0
                    * (
                        math.log2(actual.frequency_hz)
                        - math.log2(expected.frequency_hz)
                    )
                )
            )

    count = len(reference.frames)
    return F0Comparison(
        frame_count=count,
        paired_voiced_count=len(errors),
        voiced_agreement_rate=agreements / count if count else 1.0,
        mean_absolute_cents=sum(errors) / len(errors) if errors else None,
        octave_error_rate=(
            sum(error >= 1150.0 for error in errors) / len(errors) if errors else None
        ),
    )
