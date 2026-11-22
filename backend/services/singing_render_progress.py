"""Full-render duration cap usage, as a percentage, for the Singing workspace.

Shared by any UI or API surface that wants to show how much of the
server-owned full-render duration cap (services/singing_render_limits.py)
a guide vocal would consume, without duplicating the validity rules for
the duration or the cap.
"""

from __future__ import annotations

import math


def full_render_cap_usage_percent(guide_duration_seconds: object, max_seconds: object) -> float:
    """Return the percentage of the full-render duration cap a guide vocal uses.

    Both inputs are validated the same way: a non-positive, NaN or infinite
    value makes the percentage unmeasurable, so ``0.0`` is returned. Once both
    are valid, a guide vocal at or under the cap reports its exact share of
    it, rounded to one decimal place; a guide vocal over the cap reports
    ``100.0`` rather than a value past it. This function is total and never
    raises, even for non-numeric input.
    """
    if not _is_positive_finite(guide_duration_seconds):
        return 0.0

    if not _is_positive_finite(max_seconds):
        return 0.0

    if guide_duration_seconds > max_seconds:
        return 100.0

    percent = round((guide_duration_seconds / max_seconds) * 100, 1)
    return min(100.0, max(0.0, percent))


def _is_positive_finite(value: object) -> bool:
    try:
        return value > 0 and math.isfinite(value)
    except TypeError:
        return False
