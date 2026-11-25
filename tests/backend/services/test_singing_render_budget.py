"""Tests for backend/services/singing_render_budget.py."""
import math

import pytest

from services.singing_render_budget import full_render_seconds_remaining


@pytest.mark.parametrize(
    "guide_duration_seconds,max_seconds,expected",
    [
        (100.0, 300.0, 200.0),
        (120.0, 600.0, 480.0),
        (0.5, 1.0, 0.5),
        (1, 600, 599.0),
        (100.04, 300.0, 200.0),
        (0.1, 0.3, 0.2),
    ],
)
def test_duration_within_cap_returns_rounded_remaining_seconds(
    guide_duration_seconds, max_seconds, expected
):
    assert full_render_seconds_remaining(guide_duration_seconds, max_seconds) == expected


@pytest.mark.parametrize(
    "guide_duration_seconds,max_seconds",
    [
        (600.0, 600.0),
        (601.0, 600.0),
        (10_000, 600),
    ],
)
def test_duration_at_or_beyond_cap_returns_zero(guide_duration_seconds, max_seconds):
    assert full_render_seconds_remaining(guide_duration_seconds, max_seconds) == 0.0


@pytest.mark.parametrize(
    "guide_duration_seconds",
    [0, -1.0, math.nan, math.inf, -math.inf, None, "10", []],
)
def test_unusable_guide_duration_returns_full_cap_unchanged(guide_duration_seconds):
    assert full_render_seconds_remaining(guide_duration_seconds, 600.0) == 600.0


@pytest.mark.parametrize("max_seconds", [0, -5.0, math.nan, math.inf, -math.inf, None, "600", []])
@pytest.mark.parametrize("guide_duration_seconds", [100.0, 0, math.nan, None])
def test_unusable_cap_returns_zero_regardless_of_duration(guide_duration_seconds, max_seconds):
    assert full_render_seconds_remaining(guide_duration_seconds, max_seconds) == 0.0


def test_result_is_a_float_and_inputs_are_not_changed():
    result = full_render_seconds_remaining(100, 600)

    assert isinstance(result, float)
    assert result == 500.0
