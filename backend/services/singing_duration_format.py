"""Duration display formatting for guide and full-render vocals.

Shared by any UI surface in the Singing workspace that needs to show a
vocal's length, so the M:SS / H:MM:SS switch-over and padding rules are
defined in exactly one place.
"""

from __future__ import annotations

import math


def format_singing_duration(seconds: object) -> str:
    """Format a duration in seconds as ``M:SS``, or ``H:MM:SS`` once it reaches one hour.

    The input is rounded to the nearest whole second before formatting. The
    leading unit (minutes, or hours once shown) is never zero-padded; every
    unit after it is zero-padded to two digits. A negative, NaN, infinite or
    otherwise non-numeric value returns ``"0:00"``. This function is total
    and never raises.
    """
    try:
        value = float(seconds)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "0:00"

    if not math.isfinite(value) or value < 0:
        return "0:00"

    total_seconds = int(round(value))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
