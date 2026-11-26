"""Performance-style profiles and the Style Strength mixer for Singing Mode.

A style profile is a plain ``dict`` mapping each documented style dimension to a
number on that dimension's own normalized range (see ``docs/singing-style-presets.md``,
"Control model").  It describes *how* a voice delivers a line and never *who* is
delivering it: there is no speaker or identity dimension, and unknown keys are
dropped, so a profile can be blended or serialized without touching a voice
identity.

Every function is pure, returns new dicts, never raises on bad input and imports
only the standard library.  A malformed profile or strength fails closed to the
neutral baseline (the unstyled, cloned-voice delivery), never to a stronger style.

* ``normalize_style``       - validate and clamp a raw mapping into a full profile.
* ``apply_style_strength``  - scale a preset from neutral (0) to its full per-dimension
  capped effect (100).
* ``apply_style_overrides`` - replace chosen dimensions with explicit values.
* ``blend_styles``          - mix two performance profiles dimension by dimension.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

# Dimension -> (minimum, neutral, maximum, cap).  ``neutral`` is the baseline cloned-voice
# delivery.  ``cap`` is the largest distance from neutral a style may reach at strength 100,
# which keeps an extreme preset from producing an implausible or unstable result.  Sorted by
# name on purpose: every returned profile has a stable, reviewable key order.
_DIMENSIONS: dict[str, tuple[float, float, float, float]] = {
    "ad_lib_probability": (0.0, 0.0, 1.0, 0.6),
    "breathiness": (0.0, 0.0, 1.0, 0.8),
    "consonant_attack": (0.0, 0.3, 1.0, 0.7),
    "double_track_tendency": (0.0, 0.0, 1.0, 0.6),
    "dynamic_range": (0.0, 0.3, 1.0, 0.7),
    "energy": (0.0, 0.4, 1.0, 0.6),
    "formant_shift_allowance": (0.0, 0.0, 1.0, 0.5),
    "grit": (0.0, 0.0, 1.0, 0.8),
    "intimacy_projection": (-1.0, 0.0, 1.0, 0.9),
    "legato_clipped": (-1.0, 0.0, 1.0, 0.9),
    "melisma_tendency": (0.0, 0.0, 1.0, 0.7),
    "non_lexical_tendency": (0.0, 0.0, 1.0, 0.6),
    "onset_hardness": (0.0, 0.3, 1.0, 0.7),
    "pause_frequency": (0.0, 0.3, 1.0, 0.6),
    "phrase_length": (0.0, 0.5, 1.0, 0.5),
    "pitch_stability": (0.0, 0.8, 1.0, 0.7),
    "register": (-1.0, 0.0, 1.0, 0.8),
    "rhythmic_placement": (-1.0, 0.0, 1.0, 0.6),
    "scoop_tendency": (0.0, 0.0, 1.0, 0.7),
    "vibrato_depth": (0.0, 0.2, 1.0, 0.8),
    "vibrato_rate": (0.0, 0.4, 1.0, 0.6),
    "vowel_openness": (0.0, 0.5, 1.0, 0.5),
}

# The performance modes a profile may name.  ``sung`` is the neutral default.
_MODES = ("sung", "rap", "spoken", "hybrid")
_NEUTRAL_MODE = "sung"

_DECIMALS = 4


def _number(value: object) -> float | None:
    """Return ``value`` as a finite float, or ``None`` for bools, non-numbers, NaN and infinity."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _fraction(value: object) -> float | None:
    """A finite number clamped to 0..1, or ``None`` when ``value`` is not a finite number."""
    number = _number(value)
    return None if number is None else _clamp(number, 0.0, 1.0)


def _neutral_values() -> dict[str, float]:
    return {name: neutral for name, (_low, neutral, _high, _cap) in _DIMENSIONS.items()}


def neutral_style() -> dict[str, object]:
    """Return the neutral profile: the baseline cloned voice with unstyled delivery."""
    profile: dict[str, object] = {"mode": _NEUTRAL_MODE}
    profile.update(_neutral_values())
    return profile


def style_dimensions() -> dict[str, dict[str, float]]:
    """Describe every style dimension as ``{"min", "neutral", "max", "cap"}`` for UI and docs."""
    return {
        name: {"min": low, "neutral": neutral, "max": high, "cap": cap}
        for name, (low, neutral, high, cap) in _DIMENSIONS.items()
    }


def normalize_style(raw: object) -> dict[str, object]:
    """Turn ``raw`` into a complete, in-range profile.

    A dimension that is missing or not a finite number takes its neutral value; a number
    outside the dimension's range is clamped to it.  Unknown keys (including any attempt to
    carry a speaker identity) are dropped.  An unknown or non-string ``mode`` becomes
    ``sung``.  A ``raw`` that is not a mapping yields the neutral profile.
    """
    profile = neutral_style()
    if not isinstance(raw, Mapping):
        return profile
    mode = raw.get("mode")
    if isinstance(mode, str) and mode in _MODES:
        profile["mode"] = mode
    for name, (low, neutral, high, _cap) in _DIMENSIONS.items():
        number = _number(raw.get(name))
        value = neutral if number is None else _clamp(number, low, high)
        profile[name] = round(value, _DECIMALS)
    return profile


def apply_style_strength(preset: object, strength: object) -> dict[str, object]:
    """Scale ``preset`` by a Style Strength of 0-100 and return the resulting profile.

    Each dimension moves linearly from neutral toward the preset's value, so the style
    increases monotonically with strength: 0 is exactly neutral, 100 is the full preset.
    The distance from neutral never exceeds the dimension's cap, which holds even at 100.
    ``mode`` stays neutral until strength reaches 50, then follows the preset, so a weakly
    styled render does not switch performance mode.  A strength above 100 is treated as 100
    and below 0 as 0; one that is not a finite number is treated as 0 (neutral).
    """
    target = normalize_style(preset)
    number = _number(strength)
    weight = 0.0 if number is None else _clamp(number, 0.0, 100.0) / 100.0
    profile = neutral_style()
    if weight >= 0.5:
        profile["mode"] = target["mode"]
    for name, (low, neutral, high, cap) in _DIMENSIONS.items():
        goal = target[name]
        assert isinstance(goal, float)
        shift = _clamp((goal - neutral) * weight, -cap, cap)
        profile[name] = round(_clamp(neutral + shift, low, high), _DECIMALS)
    return profile


def apply_style_overrides(profile: object, overrides: object) -> dict[str, object]:
    """Return ``profile`` with the dimensions named in ``overrides`` replaced by explicit values.

    An override is clamped to its dimension's range.  An override whose key is unknown or whose
    value is not a finite number is ignored, as is a non-mapping ``overrides``; ``mode`` may be
    overridden with one of the known modes.  The result is always a full normalized profile.
    """
    result = normalize_style(profile)
    if not isinstance(overrides, Mapping):
        return result
    mode = overrides.get("mode")
    if isinstance(mode, str) and mode in _MODES:
        result["mode"] = mode
    for name, (low, _neutral, high, _cap) in _DIMENSIONS.items():
        number = _number(overrides.get(name))
        if number is not None:
            result[name] = round(_clamp(number, low, high), _DECIMALS)
    return result


def blend_styles(first: object, second: object, mix: object) -> dict[str, object]:
    """Blend two performance profiles; ``mix`` is the 0-1 share of ``second``.

    Only the normalized style dimensions are interpolated, never an identity.  A ``mix`` of 0
    gives ``first`` and 1 gives ``second`` (each normalized); a ``mix`` outside 0-1 is clamped.
    A ``mix`` that is not a finite number fails closed to ``first`` unchanged.  ``mode`` comes
    from the profile with the larger share, ``first`` on a tie.
    """
    one = normalize_style(first)
    two = normalize_style(second)
    share = _fraction(mix)
    if share is None:
        return one
    blended = neutral_style()
    blended["mode"] = two["mode"] if share > 0.5 else one["mode"]
    for name, (low, _neutral, high, _cap) in _DIMENSIONS.items():
        a = one[name]
        b = two[name]
        assert isinstance(a, float) and isinstance(b, float)
        blended[name] = round(_clamp(a + (b - a) * share, low, high), _DECIMALS)
    return blended
