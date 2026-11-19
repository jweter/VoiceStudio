"""Tests for backend/services/singing_render_limits.py."""
import math

import pytest

from services.singing_render_limits import full_render_duration_error


@pytest.mark.parametrize(
    "guide_duration_seconds,max_seconds",
    [
        (120.0, 600.0),
        (600.0, 600.0),
        (0.5, 1.0),
        (1, 600),
    ],
)
def test_duration_within_cap_returns_none(guide_duration_seconds, max_seconds):
    assert full_render_duration_error(guide_duration_seconds, max_seconds) is None


@pytest.mark.parametrize(
    "guide_duration_seconds",
    [0.0, -1.0, -0.0001, math.nan, math.inf, -math.inf],
)
def test_invalid_duration_is_rejected_before_cap_is_checked(guide_duration_seconds):
    assert (
        full_render_duration_error(guide_duration_seconds, 0.0)
        == "Guide vocal duration must be positive."
    )


@pytest.mark.parametrize(
    "max_seconds",
    [0.0, -1.0, math.nan, math.inf, -math.inf],
)
def test_invalid_cap_is_rejected_once_duration_is_valid(max_seconds):
    assert (
        full_render_duration_error(120.0, max_seconds)
        == "Full-render duration limit is not configured."
    )


@pytest.mark.parametrize(
    "guide_duration_seconds,max_seconds,expected",
    [
        (700.0, 600.0, "Guide vocal is 700.0s, longer than the 600.0s full-render limit."),
        (601.0, 600.0, "Guide vocal is 601.0s, longer than the 600.0s full-render limit."),
    ],
)
def test_duration_over_a_valid_cap_names_both_values(guide_duration_seconds, max_seconds, expected):
    assert full_render_duration_error(guide_duration_seconds, max_seconds) == expected


def test_never_raises_on_non_numeric_input():
    assert full_render_duration_error(None, 600.0) == "Guide vocal duration must be positive."
    assert full_render_duration_error("120", 600.0) == "Guide vocal duration must be positive."
    assert full_render_duration_error(120.0, None) == "Full-render duration limit is not configured."
    assert full_render_duration_error(120.0, "600") == "Full-render duration limit is not configured."
