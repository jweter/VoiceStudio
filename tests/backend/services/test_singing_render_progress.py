"""Tests for backend/services/singing_render_progress.py."""
import math

import pytest

from services.singing_render_progress import full_render_cap_usage_percent


@pytest.mark.parametrize(
    "guide_duration_seconds,max_seconds,expected",
    [
        (100.0, 300.0, 33.3),
        (120.0, 600.0, 20.0),
        (0.5, 1.0, 50.0),
        (1, 600, 0.2),
        (600.0, 600.0, 100.0),
    ],
)
def test_duration_within_cap_returns_rounded_percentage(guide_duration_seconds, max_seconds, expected):
    assert full_render_cap_usage_percent(guide_duration_seconds, max_seconds) == expected


@pytest.mark.parametrize(
    "guide_duration_seconds,max_seconds",
    [
        (700.0, 600.0),
        (601.0, 600.0),
        (600.0001, 600.0),
    ],
)
def test_duration_over_cap_returns_exactly_100(guide_duration_seconds, max_seconds):
    assert full_render_cap_usage_percent(guide_duration_seconds, max_seconds) == 100.0


@pytest.mark.parametrize(
    "guide_duration_seconds",
    [0.0, -1.0, -0.0001, math.nan, math.inf, -math.inf],
)
def test_invalid_duration_returns_zero_regardless_of_cap(guide_duration_seconds):
    assert full_render_cap_usage_percent(guide_duration_seconds, 600.0) == 0.0


@pytest.mark.parametrize(
    "max_seconds",
    [0.0, -1.0, -0.0001, math.nan, math.inf, -math.inf],
)
def test_invalid_cap_returns_zero_regardless_of_duration(max_seconds):
    assert full_render_cap_usage_percent(120.0, max_seconds) == 0.0


def test_invalid_duration_wins_over_invalid_cap():
    assert full_render_cap_usage_percent(0.0, 0.0) == 0.0
    assert full_render_cap_usage_percent(math.nan, math.nan) == 0.0


def test_never_raises_on_non_numeric_input():
    assert full_render_cap_usage_percent(None, 600.0) == 0.0
    assert full_render_cap_usage_percent("120", 600.0) == 0.0
    assert full_render_cap_usage_percent(120.0, None) == 0.0
    assert full_render_cap_usage_percent(120.0, "600") == 0.0
    assert full_render_cap_usage_percent(None, None) == 0.0
