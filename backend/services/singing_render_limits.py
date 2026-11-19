"""Duration cap for the full (unbounded) singing render.

Shared by the full-render service and its API route so both agree on
whether a guide vocal is short enough to render in full, without either
needing to duplicate the validation order or the error wording.
"""

from __future__ import annotations

import math


def full_render_duration_error(guide_duration_seconds: object, max_seconds: object) -> str | None:
    """Return a reason the full render must be refused, or ``None`` if it's allowed.

    The guide vocal's duration is checked first: it must be a positive,
    finite number, or the duration itself is rejected regardless of the
    configured cap. The cap (``max_seconds``) is then checked the same way,
    since a non-positive or non-finite cap can never be satisfied. Only once
    both are valid is the duration compared against the cap. This function
    is total and never raises, even for non-numeric input.
    """
    if not _is_positive_finite(guide_duration_seconds):
        return "Guide vocal duration must be positive."

    if not _is_positive_finite(max_seconds):
        return "Full-render duration limit is not configured."

    if guide_duration_seconds > max_seconds:
        return (
            f"Guide vocal is {guide_duration_seconds}s, longer than the "
            f"{max_seconds}s full-render limit."
        )

    return None


def _is_positive_finite(value: object) -> bool:
    try:
        return value > 0 and math.isfinite(value)
    except TypeError:
        return False
