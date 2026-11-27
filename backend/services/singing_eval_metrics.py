"""Pure metrics for the singing evaluation harness (Phase 4.7.5).

Small, deterministic building blocks for judging a rendered vocal against its target:
pitch accuracy, onset timing, vibrato, identity retention and style adherence.  Inputs are
plain lists and mappings of numbers (F0 contours in Hz, onset times in seconds), so the
metrics run anywhere and never need audio.

Every function is pure, never raises on bad input and imports only the standard library
plus the style-profile module.  Invalid input never yields a passing result: numeric
metrics return ``None`` ("not measurable"), and pass/fail checks return ``"INVALID"``.
A frame is *voiced* when its F0 is a finite number greater than zero.

* ``mean_abs_cents_error``  - mean absolute pitch error in cents over frames voiced in both contours.
* ``onset_error_ms``        - mean distance from each reference onset to its nearest rendered onset.
* ``vibrato_stats``         - vibrato rate (Hz) and depth (cents) of the longest voiced run.
* ``identity_floor_check``  - PASS/FAIL/INVALID of a speaker-similarity score against a floor.
* ``style_adherence``       - how closely measured style dimensions match a normalized profile.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from services.singing_style_profile import style_dimensions

_MIN_VIBRATO_SECONDS = 1.0
# Below this oscillation amplitude there is no audible vibrato: a pure glide or steady tone leaves
# only floating-point residue after detrending, whose sign changes must not be counted as a rate.
_MIN_VIBRATO_DEPTH_CENTS = 2.0


def _is_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def _is_voiced(value: object) -> bool:
    return _is_number(value) and value > 0  # type: ignore[operator]


def _sequence(value: object) -> Sequence[object] | None:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return None
    return value


def mean_abs_cents_error(f0_ref_hz: object, f0_est_hz: object) -> float | None:
    """Mean absolute pitch error in cents over frames voiced in BOTH contours.

    ``None`` when either input is not a sequence, the lengths differ, or no frame is voiced
    in both (an empty overlap is "not measurable", never zero error).
    """
    ref = _sequence(f0_ref_hz)
    est = _sequence(f0_est_hz)
    if ref is None or est is None or len(ref) != len(est):
        return None
    errors = [
        abs(1200.0 * math.log2(float(e) / float(r)))  # type: ignore[arg-type]
        for r, e in zip(ref, est)
        if _is_voiced(r) and _is_voiced(e)
    ]
    if not errors:
        return None
    return sum(errors) / len(errors)


def _onsets(value: object) -> list[float] | None:
    seq = _sequence(value)
    if seq is None or not seq:
        return None
    if not all(_is_number(item) and item >= 0 for item in seq):  # type: ignore[operator]
        return None
    return [float(item) for item in seq]  # type: ignore[arg-type]


def onset_error_ms(ref_onsets_s: object, est_onsets_s: object) -> float | None:
    """Mean absolute distance (milliseconds) from each reference onset to the nearest rendered one.

    ``None`` when either list is empty, not a sequence, or holds a non-finite, negative or
    non-numeric time.
    """
    ref = _onsets(ref_onsets_s)
    est = _onsets(est_onsets_s)
    if ref is None or est is None:
        return None
    total = sum(min(abs(r - e) for e in est) for r in ref)
    return 1000.0 * total / len(ref)


def _longest_voiced_run(f0: Sequence[object]) -> list[float]:
    best: list[float] = []
    current: list[float] = []
    for value in f0:
        if _is_voiced(value):
            current.append(float(value))  # type: ignore[arg-type]
            if len(current) > len(best):
                best = list(current)
        else:
            current = []
    return best


def vibrato_stats(f0_hz: object, frame_rate_hz: object) -> dict[str, float] | None:
    """Vibrato ``{"rate_hz", "depth_cents"}`` of the longest uninterrupted voiced run.

    The run's pitch contour is converted to cents and its linear trend removed, so a slow
    glide is not mistaken for vibrato.  Rate is half the number of zero crossings per second;
    depth is the amplitude of the oscillation (RMS * sqrt(2)).  When that depth is under
    2 cents there is no vibrato to time, so the rate is reported as 0.0 (numerical noise from a
    glide or a steady tone is never counted as oscillation) and the measured depth is still
    returned.  ``None`` when the frame rate is invalid, the input is not a sequence, or the run
    is shorter than one second.
    """
    seq = _sequence(f0_hz)
    if seq is None or not _is_number(frame_rate_hz) or float(frame_rate_hz) <= 0:  # type: ignore[arg-type]
        return None
    frame_rate = float(frame_rate_hz)  # type: ignore[arg-type]
    run = _longest_voiced_run(seq)
    if len(run) < frame_rate * _MIN_VIBRATO_SECONDS or len(run) < 4:
        return None
    reference = run[0]
    cents = [1200.0 * math.log2(value / reference) for value in run]
    count = len(cents)
    xs = list(range(count))
    mean_x = (count - 1) / 2.0
    mean_y = sum(cents) / count
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, cents)) / denominator
    detrended = [y - (mean_y + slope * (x - mean_x)) for x, y in zip(xs, cents)]
    crossings = sum(
        1 for a, b in zip(detrended, detrended[1:]) if (a < 0 <= b) or (a > 0 >= b)
    )
    duration_s = count / frame_rate
    rms = math.sqrt(sum(value * value for value in detrended) / count)
    depth_cents = rms * math.sqrt(2.0)
    rate_hz = (crossings / 2.0) / duration_s if depth_cents >= _MIN_VIBRATO_DEPTH_CENTS else 0.0
    return {"rate_hz": rate_hz, "depth_cents": depth_cents}


def identity_floor_check(similarity: object, floor: object) -> str:
    """``"PASS"`` if ``similarity >= floor``, ``"FAIL"`` if lower, ``"INVALID"`` for bad input.

    Both values must be finite numbers in [0, 1]; anything else (including booleans) is
    ``INVALID`` and can never pass.
    """
    for value in (similarity, floor):
        if not _is_number(value) or not 0.0 <= float(value) <= 1.0:  # type: ignore[arg-type]
            return "INVALID"
    return "PASS" if float(similarity) >= float(floor) else "FAIL"  # type: ignore[arg-type]


def style_adherence(
    measured: object, profile: object, tolerance: object = 0.2
) -> dict[str, object]:
    """Compare measured style dimensions with a normalized profile.

    Each dimension present in both ``measured`` and ``profile`` is compared on its own
    range: the absolute difference divided by (max - min) must be at most ``tolerance``.
    Dimensions that are not measured, not numeric, or not part of the style model are
    ignored.  Returns ``{"status", "per_dimension", "evaluated", "fraction"}`` where status
    is ``"OK"``, ``"NOTHING_MEASURED"`` or ``"INVALID"`` (bad ``measured``/``profile``/
    ``tolerance``), and ``fraction`` is the share of evaluated dimensions that passed
    (``None`` unless status is ``OK``).
    """
    empty: dict[str, object] = {
        "status": "INVALID",
        "per_dimension": {},
        "evaluated": 0,
        "fraction": None,
    }
    if (
        not isinstance(measured, Mapping)
        or not isinstance(profile, Mapping)
        or not _is_number(tolerance)
        or float(tolerance) < 0  # type: ignore[arg-type]
    ):
        return empty
    limit = float(tolerance)  # type: ignore[arg-type]
    results: dict[str, str] = {}
    for name, spec in style_dimensions().items():
        have = measured.get(name)
        want = profile.get(name)
        if not _is_number(have) or not _is_number(want):
            continue
        span = spec["max"] - spec["min"]
        distance = abs(float(have) - float(want)) / span  # type: ignore[arg-type]
        results[name] = "PASS" if distance <= limit else "FAIL"
    if not results:
        return {**empty, "status": "NOTHING_MEASURED"}
    passed = sum(1 for verdict in results.values() if verdict == "PASS")
    return {
        "status": "OK",
        "per_dimension": results,
        "evaluated": len(results),
        "fraction": passed / len(results),
    }
