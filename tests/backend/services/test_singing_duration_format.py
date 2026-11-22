"""Tests for backend/services/singing_duration_format.py."""
import math

import pytest

from services.singing_duration_format import format_singing_duration


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "0:00"),
        (5, "0:05"),
        (5.4, "0:05"),
        (59, "0:59"),
        (59.6, "1:00"),
    ],
)
def test_under_one_minute_returns_0_ss(seconds, expected):
    assert format_singing_duration(seconds) == expected


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (60, "1:00"),
        (65, "1:05"),
        (125, "2:05"),
        (125.4, "2:05"),
        (599, "9:59"),
        (3599, "59:59"),
        (3599.6, "1:00:00"),
    ],
)
def test_one_minute_to_under_one_hour_returns_m_ss(seconds, expected):
    assert format_singing_duration(seconds) == expected


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (3600, "1:00:00"),
        (3661, "1:01:01"),
        (7325, "2:02:05"),
        (36000, "10:00:00"),
    ],
)
def test_one_hour_or_more_returns_h_mm_ss(seconds, expected):
    assert format_singing_duration(seconds) == expected


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (1.5, "0:02"),
        (1.4, "0:01"),
        (2.5, "0:02"),
        (3661.5, "1:01:02"),
    ],
)
def test_fractional_seconds_round_to_nearest_whole_second(seconds, expected):
    assert format_singing_duration(seconds) == expected


@pytest.mark.parametrize(
    "value",
    [
        -1,
        -0.5,
        math.nan,
        math.inf,
        -math.inf,
        "not-a-number",
        None,
        [],
        {},
        object(),
    ],
)
def test_invalid_input_returns_zero_without_raising(value):
    assert format_singing_duration(value) == "0:00"
