"""Seconds left in the full (unbounded) singing render duration cap.

Companion to services/singing_render_limits.py (accept/refuse) and
services/singing_render_progress.py (percentage used): this reports how many
seconds of the server-owned cap a guide vocal leaves unused, for any UI or API
surface that wants to show the remaining budget.
"""

from __future__ import annotations

import math


def full_render_seconds_remaining(guide_duration_seconds: object, max_seconds: object) -> float:
    """Return the seconds left in the full-render cap after the guide vocal.

    A non-positive, NaN or infinite cap leaves nothing to spend, so ``0.0`` is
    returned. A non-positive, NaN or infinite guide duration is not a usable
    measurement, so none of the cap is treated as consumed and ``max_seconds``
    is returned unchanged. A guide vocal at or beyond the cap leaves ``0.0``.
    Otherwise the difference is rounded to one decimal place. This function is
    total and never raises, even for non-numeric input.
    """
    if not _is_positive_finite(max_seconds):
        return 0.0

    if not _is_positive_finite(guide_duration_seconds):
        return max_seconds  # type: ignore[return-value]

    if guide_duration_seconds >= max_seconds:  # type: ignore[operator]
        return 0.0

    return round(float(max_seconds) - float(guide_duration_seconds), 1)  # type: ignore[arg-type]


def _is_positive_finite(value: object) -> bool:
    try:
        return value > 0 and math.isfinite(value)  # type: ignore[operator, arg-type]
    except TypeError:
        return False
