"""Singing/rap performance control layer (Phase 4.7.2).

Turns a normalized performance-style profile (``singing_style_profile``) into concrete,
engine-independent render controls in real units - vibrato rate in Hz and depth in cents,
attack time and onset offset in milliseconds, breath and saturation amounts, pause rate and
so on - so any renderer can consume one documented vocabulary.  It describes *how* a line is
delivered and never *who* delivers it: there is no identity input or output.

Each style dimension maps linearly onto one control between two documented end values
(``control_ranges`` publishes them for UI and docs).  Two interaction rules adjust the
profile first:

* ``free_rhythm_mode_suppresses_vibrato_and_scoop`` - in ``rap`` and ``spoken`` modes there
  are no sustained melodic notes, so vibrato depth and pitch scoop are held at zero.
* ``double_tracking_limits_formant_shift`` - when double-tracking is strong (> 0.5) the
  formant-shift allowance is capped at 0.5 (2 semitones) so doubled takes do not turn phasey.

An engine adapter declares which *style dimensions* it supports; an unsupported dimension
degrades gracefully: its control is omitted and the dimension is reported in
``unsupported_dimensions``.  Omitting ``capabilities`` means every dimension is supported;
an invalid declaration (not a collection of names) supports nothing, never everything.

Every function is pure, never raises on bad input and imports only the standard library plus
the profile module.  A malformed profile fails closed to the neutral baseline.

* ``control_ranges``    - the documented control vocabulary: unit, min, max, source dimension.
* ``render_controls``   - map a profile to concrete controls for an engine's capabilities.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from services.singing_style_profile import normalize_style, style_dimensions

_DECIMALS = 4

# dimension -> (control name, unit, control value at the dimension's minimum, at its maximum).
# Sorted by dimension name on purpose: stable, reviewable output order.
_CONTROLS: dict[str, tuple[str, str, float, float]] = {
    "ad_lib_probability": ("ad_lib_probability", "probability", 0.0, 1.0),
    "breathiness": ("breath_mix", "ratio", 0.0, 0.5),
    "consonant_attack": ("consonant_gain_db", "dB", -3.0, 6.0),
    "double_track_tendency": ("double_track_mix", "ratio", 0.0, 1.0),
    "dynamic_range": ("dynamic_range_db", "dB", 3.0, 24.0),
    "energy": ("energy", "ratio", 0.0, 1.0),
    "formant_shift_allowance": ("max_formant_shift_semitones", "semitones", 0.0, 4.0),
    "grit": ("saturation_drive", "ratio", 0.0, 1.0),
    "intimacy_projection": ("projection", "ratio", -1.0, 1.0),
    # Clipped (-1) leaves a long gap between notes; legato (+1) leaves none.
    "legato_clipped": ("note_gap_ms", "ms", 120.0, 0.0),
    "melisma_tendency": ("melisma_probability", "probability", 0.0, 1.0),
    "non_lexical_tendency": ("non_lexical_probability", "probability", 0.0, 1.0),
    # Harder onsets attack faster.
    "onset_hardness": ("attack_time_ms", "ms", 80.0, 5.0),
    "pause_frequency": ("pauses_per_minute", "per_minute", 0.0, 30.0),
    "phrase_length": ("phrase_length_s", "s", 1.0, 8.0),
    # More stable pitch means less jitter.
    "pitch_stability": ("pitch_jitter_cents", "cents", 25.0, 0.0),
    "register": ("register_balance", "ratio", -1.0, 1.0),
    # Positive is behind the beat, negative ahead of it.
    "rhythmic_placement": ("onset_offset_ms", "ms", -60.0, 60.0),
    "scoop_tendency": ("scoop_depth_cents", "cents", 0.0, 150.0),
    "vibrato_depth": ("vibrato_depth_cents", "cents", 0.0, 100.0),
    "vibrato_rate": ("vibrato_rate_hz", "Hz", 3.0, 8.0),
    "vowel_openness": ("vowel_openness", "ratio", 0.0, 1.0),
}

_FREE_RHYTHM_MODES = ("rap", "spoken")
_DOUBLE_TRACK_THRESHOLD = 0.5
_FORMANT_CAP_WHEN_DOUBLED = 0.5


def control_ranges() -> dict[str, dict[str, object]]:
    """Describe every control as ``{"dimension", "unit", "min", "max"}`` (min <= max)."""
    ranges: dict[str, dict[str, object]] = {}
    for dimension, (name, unit, at_min, at_max) in _CONTROLS.items():
        ranges[name] = {
            "dimension": dimension,
            "unit": unit,
            "min": min(at_min, at_max),
            "max": max(at_min, at_max),
        }
    return ranges


def _supported_dimensions(capabilities: object) -> set[str]:
    """Resolve an engine's declared dimensions; invalid declarations support nothing."""
    known = set(_CONTROLS)
    if capabilities is None:
        return known
    if isinstance(capabilities, (str, bytes, Mapping)) or not isinstance(capabilities, Iterable):
        return set()
    names = {item for item in capabilities if isinstance(item, str)}
    return names & known


def render_controls(profile: object, capabilities: object = None) -> dict[str, object]:
    """Map ``profile`` to concrete render controls for an engine supporting ``capabilities``.

    Returns ``{"mode", "controls", "unsupported_dimensions", "applied_rules"}`` where
    ``controls`` maps each control name to ``{"value", "unit", "dimension"}`` for every
    *supported* dimension.  ``unsupported_dimensions`` is sorted; ``applied_rules`` lists
    interaction rules that actually changed the profile, in a fixed order.
    """
    normalized = normalize_style(profile)
    working: dict[str, object] = dict(normalized)
    applied: list[str] = []

    mode = normalized["mode"]
    if mode in _FREE_RHYTHM_MODES and (
        working["vibrato_depth"] != 0.0 or working["scoop_tendency"] != 0.0
    ):
        working["vibrato_depth"] = 0.0
        working["scoop_tendency"] = 0.0
        applied.append("free_rhythm_mode_suppresses_vibrato_and_scoop")

    if (
        float(working["double_track_tendency"]) > _DOUBLE_TRACK_THRESHOLD  # type: ignore[arg-type]
        and float(working["formant_shift_allowance"]) > _FORMANT_CAP_WHEN_DOUBLED  # type: ignore[arg-type]
    ):
        working["formant_shift_allowance"] = _FORMANT_CAP_WHEN_DOUBLED
        applied.append("double_tracking_limits_formant_shift")

    supported = _supported_dimensions(capabilities)
    dimensions = style_dimensions()
    controls: dict[str, dict[str, object]] = {}
    for dimension, (name, unit, at_min, at_max) in _CONTROLS.items():
        if dimension not in supported:
            continue
        low = dimensions[dimension]["min"]
        high = dimensions[dimension]["max"]
        fraction = (float(working[dimension]) - low) / (high - low)  # type: ignore[arg-type]
        controls[name] = {
            "value": round(at_min + fraction * (at_max - at_min), _DECIMALS),
            "unit": unit,
            "dimension": dimension,
        }

    return {
        "mode": mode,
        "controls": controls,
        "unsupported_dimensions": sorted(set(_CONTROLS) - supported),
        "applied_rules": applied,
    }
