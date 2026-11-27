"""Tests for backend/services/singing_eval_metrics.py."""
import math

import pytest

from services.singing_eval_metrics import (
    identity_floor_check,
    mean_abs_cents_error,
    onset_error_ms,
    style_adherence,
    vibrato_stats,
)
from services.singing_style_profile import neutral_style


def _vibrato_contour(rate_hz, depth_cents, *, seconds=2.0, fps=100.0, base_hz=220.0, drift_cents=0.0):
    frames = int(seconds * fps)
    contour = []
    for i in range(frames):
        t = i / fps
        cents = depth_cents * math.sin(2 * math.pi * rate_hz * t) + drift_cents * t
        contour.append(base_hz * 2 ** (cents / 1200.0))
    return contour


# ---------------------------------------------------------------- mean_abs_cents_error


def test_identical_contours_have_zero_cents_error():
    f0 = [220.0, 233.08, 246.94, 261.63]
    assert mean_abs_cents_error(f0, f0) == pytest.approx(0.0, abs=1e-9)


def test_a_hundred_cent_offset_measures_one_hundred():
    ref = [220.0, 330.0, 440.0]
    est = [f * 2 ** (100 / 1200) for f in ref]
    assert mean_abs_cents_error(ref, est) == pytest.approx(100.0, abs=1e-6)


def test_the_error_is_absolute_so_sharp_and_flat_do_not_cancel():
    ref = [220.0, 220.0]
    est = [220.0 * 2 ** (50 / 1200), 220.0 * 2 ** (-50 / 1200)]
    assert mean_abs_cents_error(ref, est) == pytest.approx(50.0, abs=1e-6)


def test_only_frames_voiced_in_both_contours_count():
    ref = [220.0, 0.0, 220.0, 220.0]
    est = [220.0 * 2 ** (100 / 1200), 440.0, 0.0, 220.0]
    # frames 0 and 3 are voiced in both: errors 100 and 0.
    assert mean_abs_cents_error(ref, est) == pytest.approx(50.0, abs=1e-6)


@pytest.mark.parametrize(
    "ref, est",
    [
        ([0.0, 0.0], [220.0, 220.0]),
        ([], []),
        ([220.0], [220.0, 220.0]),
        ("abc", [220.0]),
        (None, [220.0]),
        ([220.0], 5),
        ([math.nan], [220.0]),
        ([220.0], [math.inf]),
        ([True], [220.0]),
        ([-220.0], [220.0]),
    ],
)
def test_unmeasurable_pitch_input_returns_none(ref, est):
    assert mean_abs_cents_error(ref, est) is None


# --------------------------------------------------------------------- onset_error_ms


def test_identical_onsets_have_zero_error():
    assert onset_error_ms([0.5, 1.0, 1.5], [0.5, 1.0, 1.5]) == pytest.approx(0.0)


def test_each_reference_onset_uses_its_nearest_rendered_onset():
    # nearest distances: 0.01, 0.02 -> mean 0.015 s = 15 ms
    assert onset_error_ms([1.0, 2.0], [1.01, 1.98, 5.0]) == pytest.approx(15.0, abs=1e-6)


def test_a_constant_delay_is_reported_in_milliseconds():
    ref = [0.5, 1.5, 2.5]
    assert onset_error_ms(ref, [t + 0.04 for t in ref]) == pytest.approx(40.0, abs=1e-6)


@pytest.mark.parametrize(
    "ref, est",
    [
        ([], [1.0]),
        ([1.0], []),
        (None, [1.0]),
        ([1.0], "x"),
        ([math.nan], [1.0]),
        ([1.0], [math.inf]),
        ([-0.1], [1.0]),
        ([True], [1.0]),
        (["1.0"], [1.0]),
    ],
)
def test_unmeasurable_onset_input_returns_none(ref, est):
    assert onset_error_ms(ref, est) is None


# ----------------------------------------------------------------------- vibrato_stats


def test_a_five_hertz_vibrato_measures_about_five_hertz():
    stats = vibrato_stats(_vibrato_contour(5.0, 50.0), 100.0)
    assert stats is not None
    assert stats["rate_hz"] == pytest.approx(5.0, abs=0.5)
    assert stats["depth_cents"] == pytest.approx(50.0, abs=5.0)


def test_rate_and_depth_follow_the_input():
    slow = vibrato_stats(_vibrato_contour(4.0, 30.0), 100.0)
    fast = vibrato_stats(_vibrato_contour(7.0, 80.0), 100.0)
    assert fast["rate_hz"] > slow["rate_hz"]
    assert fast["depth_cents"] > slow["depth_cents"]


def test_a_steady_tone_has_no_vibrato_depth():
    stats = vibrato_stats([220.0] * 200, 100.0)
    assert stats is not None
    assert stats["depth_cents"] == pytest.approx(0.0, abs=1e-6)
    assert stats["rate_hz"] == pytest.approx(0.0, abs=1e-9)


def test_a_slow_glide_is_not_mistaken_for_vibrato():
    stats = vibrato_stats(_vibrato_contour(5.0, 20.0, drift_cents=300.0), 100.0)
    assert stats["depth_cents"] == pytest.approx(20.0, abs=5.0)  # the glide is detrended away


def test_only_the_longest_voiced_run_is_measured():
    steady = [220.0] * 120
    vib = _vibrato_contour(5.0, 50.0, seconds=2.0)
    stats = vibrato_stats(steady + [0.0] * 5 + vib, 100.0)
    assert stats["rate_hz"] == pytest.approx(5.0, abs=0.5)


@pytest.mark.parametrize(
    "f0, fps",
    [
        ([220.0] * 50, 100.0),  # shorter than one second
        (_vibrato_contour(5.0, 50.0), 0.0),
        (_vibrato_contour(5.0, 50.0), -10.0),
        (_vibrato_contour(5.0, 50.0), math.nan),
        (_vibrato_contour(5.0, 50.0), True),
        (_vibrato_contour(5.0, 50.0), "100"),
        ([0.0] * 300, 100.0),
        ("abc", 100.0),
        (None, 100.0),
        ([], 100.0),
    ],
)
def test_unmeasurable_vibrato_input_returns_none(f0, fps):
    assert vibrato_stats(f0, fps) is None


# ------------------------------------------------------------------ identity_floor_check


@pytest.mark.parametrize(
    "similarity, floor, expected",
    [
        (0.9, 0.8, "PASS"),
        (0.8, 0.8, "PASS"),
        (0.79, 0.8, "FAIL"),
        (1.0, 1.0, "PASS"),
        (0.0, 0.0, "PASS"),
        (0.0, 0.1, "FAIL"),
    ],
)
def test_identity_floor_pass_and_fail(similarity, floor, expected):
    assert identity_floor_check(similarity, floor) == expected


@pytest.mark.parametrize(
    "similarity, floor",
    [
        (math.nan, 0.8),
        (0.9, math.nan),
        (math.inf, 0.8),
        (1.5, 0.8),
        (-0.1, 0.8),
        (0.9, 1.5),
        (True, 0.8),
        (0.9, False),
        ("0.9", 0.8),
        (None, 0.8),
        (0.9, None),
    ],
)
def test_invalid_identity_input_is_invalid_and_never_passes(similarity, floor):
    assert identity_floor_check(similarity, floor) == "INVALID"


# ------------------------------------------------------------------------ style_adherence


def test_a_perfect_match_passes_every_measured_dimension():
    profile = neutral_style()
    measured = {"energy": profile["energy"], "grit": profile["grit"]}
    result = style_adherence(measured, profile)
    assert result["status"] == "OK"
    assert result["per_dimension"] == {"energy": "PASS", "grit": "PASS"}
    assert result["evaluated"] == 2
    assert result["fraction"] == 1.0


def test_distance_is_judged_on_each_dimensions_own_range():
    profile = {"energy": 0.5, "register": 0.0}
    # energy spans 0..1 (diff 0.3 -> 0.3 > 0.2 FAIL); register spans -1..1 (diff 0.3 -> 0.15 PASS)
    result = style_adherence({"energy": 0.8, "register": 0.3}, profile)
    assert result["per_dimension"] == {"energy": "FAIL", "register": "PASS"}
    assert result["fraction"] == 0.5


def test_tolerance_changes_the_verdict():
    profile = {"energy": 0.5}
    measured = {"energy": 0.8}
    assert style_adherence(measured, profile, tolerance=0.2)["per_dimension"] == {"energy": "FAIL"}
    assert style_adherence(measured, profile, tolerance=0.31)["per_dimension"] == {"energy": "PASS"}
    assert style_adherence(measured, profile, tolerance=0)["per_dimension"] == {"energy": "FAIL"}


def test_unmeasured_non_numeric_and_unknown_dimensions_are_ignored():
    profile = {"energy": 0.5, "grit": 0.2, "made_up": 1.0}
    measured = {"energy": 0.5, "grit": "high", "made_up": 1.0, "breathiness": 0.3}
    result = style_adherence(measured, profile)
    assert result["per_dimension"] == {"energy": "PASS"}
    assert result["evaluated"] == 1


def test_nothing_measured_is_reported_not_passed():
    result = style_adherence({"energy": 0.5}, {"grit": 0.2})
    assert result["status"] == "NOTHING_MEASURED"
    assert result["fraction"] is None
    assert result["evaluated"] == 0


@pytest.mark.parametrize(
    "measured, profile, tolerance",
    [
        (None, {"energy": 0.5}, 0.2),
        ({"energy": 0.5}, None, 0.2),
        ("x", {"energy": 0.5}, 0.2),
        ({"energy": 0.5}, [1], 0.2),
        ({"energy": 0.5}, {"energy": 0.5}, -0.1),
        ({"energy": 0.5}, {"energy": 0.5}, math.nan),
        ({"energy": 0.5}, {"energy": 0.5}, True),
        ({"energy": 0.5}, {"energy": 0.5}, "0.2"),
    ],
)
def test_invalid_style_input_is_invalid(measured, profile, tolerance):
    result = style_adherence(measured, profile, tolerance)
    assert result["status"] == "INVALID"
    assert result["fraction"] is None
    assert result["per_dimension"] == {}


def test_bool_and_non_finite_measurements_never_count_as_a_match():
    profile = {"energy": 1.0, "grit": 0.0}
    result = style_adherence({"energy": True, "grit": math.nan}, profile)
    assert result["status"] == "NOTHING_MEASURED"
