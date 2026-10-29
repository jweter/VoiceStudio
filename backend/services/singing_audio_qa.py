"""Local WAV-to-WAV pitch fidelity measurement for Singing Mode S3."""

from __future__ import annotations

from pathlib import Path

from services.singing_pitch import extract_f0_wav
from services.singing_pitch_metrics import F0Comparison, compare_f0_tracks


def compare_f0_wavs(
    reference_path: str | Path,
    observed_path: str | Path,
    *,
    hop_samples: int = 480,
    frame_samples: int = 2048,
    min_hz: float = 70.0,
    max_hz: float = 1000.0,
    voicing_threshold: float = 0.30,
) -> F0Comparison:
    """Compare actual PCM guide/output WAV pitch without implicit resampling.

    Both files use identical analysis parameters. Existing WAV ingestion rejects
    unsupported channel/sample formats; the track comparator rejects differing
    sample rates, frame counts, or frame timing. These metrics are diagnostic
    evidence, not a singing-conversion quality or Product Reality verdict.
    """
    options = {
        "hop_samples": hop_samples,
        "frame_samples": frame_samples,
        "min_hz": min_hz,
        "max_hz": max_hz,
        "voicing_threshold": voicing_threshold,
    }
    reference = extract_f0_wav(reference_path, **options)
    observed = extract_f0_wav(observed_path, **options)
    return compare_f0_tracks(reference, observed)
