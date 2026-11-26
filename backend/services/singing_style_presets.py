"""The initial performance-style preset library (Phase 4.7.4).

Fourteen hand-authored, inspectable style presets built on ``singing_style_profile``.  A
preset is a *performance vocabulary* (how a line is delivered), never a voice: it carries
no speaker or identity data, and the user's cloned voice stays the identity anchor.

Each preset has a descriptive, in-product ``public_label`` and an internal ``rd_reference``
naming the artist whose measurable performance traits inspired it.  The reference is kept
only for research and evaluation; ``public_listing`` never exposes it, so user-facing
names stay descriptive unless branded naming is licensed
(``docs/singing-style-presets.md``, "Initial reference map").

Every function is pure, returns new objects (callers cannot mutate the library), never
raises on bad input and imports only the standard library plus the profile module.  An
unknown or non-string ``preset_id`` yields ``None`` and never a default style.

* ``list_presets``    - every preset, including its internal ``rd_reference``.
* ``get_preset``      - one preset by id.
* ``preset_profile``  - a preset as a complete normalized profile (feeds the Style Strength mixer).
* ``public_listing``  - ``{preset_id, public_label, mode}`` only, safe to show in the UI.
"""

from __future__ import annotations

import copy

from services.singing_style_profile import normalize_style

# (preset_id, public_label, mode, rd_reference, dimensions).  Dimensions not listed stay at
# their neutral value.  ``rhythmic_placement`` > 0 is behind the beat, < 0 ahead of it.
_PRESETS: tuple[tuple[str, str, str, str, dict[str, float]], ...] = (
    (
        "haunted_doom_croon",
        "Haunted Doom Croon",
        "sung",
        "Ozzy Osbourne / Black Sabbath",
        {
            "energy": 0.5, "register": 0.1, "breathiness": 0.35, "grit": 0.3,
            "vibrato_rate": 0.35, "vibrato_depth": 0.3, "pitch_stability": 0.6,
            "legato_clipped": 0.5, "scoop_tendency": 0.4, "intimacy_projection": 0.4,
            "phrase_length": 0.6,
        },
    ),
    (
        "percussive_thrash_bark",
        "Percussive Thrash Bark",
        "sung",
        "Metallica",
        {
            "energy": 0.9, "onset_hardness": 0.9, "consonant_attack": 0.9, "grit": 0.6,
            "legato_clipped": -0.7, "rhythmic_placement": 0.1, "pause_frequency": 0.4,
            "vibrato_depth": 0.1, "pitch_stability": 0.85, "dynamic_range": 0.6,
            "intimacy_projection": 0.7,
        },
    ),
    (
        "controlled_alt_metal_intensity",
        "Controlled Alt-Metal Intensity",
        "sung",
        "Tool",
        {
            "energy": 0.7, "dynamic_range": 0.85, "pitch_stability": 0.9,
            "vibrato_depth": 0.25, "onset_hardness": 0.45, "grit": 0.25,
            "phrase_length": 0.75, "pause_frequency": 0.45, "intimacy_projection": 0.5,
            "legato_clipped": 0.3,
        },
    ),
    (
        "elastic_funk_metal_character",
        "Elastic Funk-Metal Character",
        "hybrid",
        "Primus",
        {
            "energy": 0.75, "rhythmic_placement": 0.3, "scoop_tendency": 0.7,
            "formant_shift_allowance": 0.4, "vowel_openness": 0.7, "legato_clipped": -0.3,
            "non_lexical_tendency": 0.4, "melisma_tendency": 0.3, "consonant_attack": 0.65,
            "pitch_stability": 0.5,
        },
    ),
    (
        "operatic_metal_screamer",
        "Operatic Metal Screamer",
        "sung",
        "Judas Priest",
        {
            "energy": 0.95, "register": 0.9, "vibrato_rate": 0.6, "vibrato_depth": 0.7,
            "grit": 0.55, "vowel_openness": 0.9, "dynamic_range": 0.9,
            "intimacy_projection": 0.9, "legato_clipped": 0.6, "melisma_tendency": 0.4,
            "pitch_stability": 0.8,
        },
    ),
    (
        "galloping_arena_tenor",
        "Galloping Arena Tenor",
        "sung",
        "Iron Maiden",
        {
            "energy": 0.85, "register": 0.75, "vibrato_rate": 0.55, "vibrato_depth": 0.5,
            "rhythmic_placement": -0.1, "phrase_length": 0.7, "legato_clipped": 0.4,
            "vowel_openness": 0.8, "intimacy_projection": 0.85, "dynamic_range": 0.75,
            "pitch_stability": 0.85,
        },
    ),
    (
        "deep_gothic_baritone",
        "Deep Gothic Baritone",
        "sung",
        "Type O Negative",
        {
            "register": -0.8, "breathiness": 0.3, "vibrato_rate": 0.25, "vibrato_depth": 0.35,
            "energy": 0.3, "legato_clipped": 0.7, "pause_frequency": 0.5,
            "intimacy_projection": 0.3, "grit": 0.15, "phrase_length": 0.8,
            "formant_shift_allowance": 0.2,
        },
    ),
    (
        "nu_metal_whisper_to_break",
        "Nu-Metal Whisper-to-Break",
        "hybrid",
        "Korn",
        {
            "breathiness": 0.7, "grit": 0.65, "dynamic_range": 0.95, "energy": 0.6,
            "register": 0.2, "melisma_tendency": 0.2, "non_lexical_tendency": 0.5,
            "onset_hardness": 0.55, "pause_frequency": 0.6, "pitch_stability": 0.45,
            "rhythmic_placement": 0.2,
        },
    ),
    (
        "precision_rapid_fire_rap",
        "Precision Rapid-Fire Rap",
        "rap",
        "Eminem",
        {
            "energy": 0.8, "consonant_attack": 0.9, "onset_hardness": 0.7,
            "legato_clipped": -0.8, "pause_frequency": 0.15, "phrase_length": 0.85,
            "pitch_stability": 0.3, "dynamic_range": 0.5, "ad_lib_probability": 0.2,
            "intimacy_projection": 0.6, "vowel_openness": 0.55,
        },
    ),
    (
        "laid_back_west_coast_flow",
        "Laid-Back West-Coast Flow",
        "rap",
        "Snoop Dogg",
        {
            "energy": 0.3, "rhythmic_placement": 0.6, "legato_clipped": 0.5,
            "consonant_attack": 0.35, "onset_hardness": 0.2, "breathiness": 0.25,
            "phrase_length": 0.6, "pause_frequency": 0.5, "ad_lib_probability": 0.4,
            "intimacy_projection": 0.2, "pitch_stability": 0.25,
        },
    ),
    (
        "industrial_command_baritone",
        "Industrial Command Baritone",
        "sung",
        "Rammstein",
        {
            "register": -0.7, "energy": 0.8, "onset_hardness": 0.85, "consonant_attack": 0.85,
            "legato_clipped": -0.5, "grit": 0.5, "vibrato_depth": 0.05, "pitch_stability": 0.9,
            "intimacy_projection": 0.85, "rhythmic_placement": 0.05, "dynamic_range": 0.6,
        },
    ),
    (
        "staccato_dramatic_spoken",
        "Staccato Dramatic Spoken",
        "spoken",
        "Christopher Walken",
        {
            "legato_clipped": -0.9, "pause_frequency": 0.85, "rhythmic_placement": 0.5,
            "energy": 0.45, "intimacy_projection": 0.5, "consonant_attack": 0.6,
            "phrase_length": 0.2, "pitch_stability": 0.4, "dynamic_range": 0.7,
            "vowel_openness": 0.4,
        },
    ),
    (
        "theatrical_operatic_rock",
        "Theatrical Operatic Rock",
        "sung",
        "Freddie Mercury",
        {
            "register": 0.6, "vibrato_rate": 0.5, "vibrato_depth": 0.6, "melisma_tendency": 0.55,
            "dynamic_range": 0.95, "energy": 0.8, "vowel_openness": 0.85,
            "double_track_tendency": 0.7, "intimacy_projection": 0.8, "scoop_tendency": 0.5,
            "pitch_stability": 0.85, "formant_shift_allowance": 0.2,
        },
    ),
    (
        "blues_rock_wail",
        "Blues-Rock Wail",
        "sung",
        "Led Zeppelin",
        {
            "register": 0.7, "grit": 0.6, "vibrato_rate": 0.6, "vibrato_depth": 0.6,
            "scoop_tendency": 0.7, "melisma_tendency": 0.6, "energy": 0.85, "breathiness": 0.2,
            "rhythmic_placement": 0.4, "pitch_stability": 0.55, "dynamic_range": 0.8,
            "intimacy_projection": 0.8, "non_lexical_tendency": 0.4,
        },
    ),
)


def _record(entry: tuple[str, str, str, str, dict[str, float]]) -> dict[str, object]:
    preset_id, public_label, mode, rd_reference, dimensions = entry
    return {
        "preset_id": preset_id,
        "public_label": public_label,
        "mode": mode,
        "rd_reference": rd_reference,
        "dimensions": copy.deepcopy(dimensions),
    }


def list_presets() -> tuple[dict[str, object], ...]:
    """Return every preset (fresh copies), including the internal ``rd_reference``."""
    return tuple(_record(entry) for entry in _PRESETS)


def get_preset(preset_id: object) -> dict[str, object] | None:
    """Return one preset by id, or ``None`` for an unknown or non-string id."""
    if not isinstance(preset_id, str):
        return None
    for entry in _PRESETS:
        if entry[0] == preset_id:
            return _record(entry)
    return None


def preset_profile(preset_id: object) -> dict[str, object] | None:
    """Return the preset as a complete normalized profile, or ``None`` if unknown."""
    preset = get_preset(preset_id)
    if preset is None:
        return None
    raw: dict[str, object] = {"mode": preset["mode"]}
    raw.update(preset["dimensions"])  # type: ignore[arg-type]
    return normalize_style(raw)


def public_listing() -> tuple[dict[str, str], ...]:
    """Return ``{preset_id, public_label, mode}`` for each preset, never the R&D reference."""
    return tuple(
        {"preset_id": entry[0], "public_label": entry[1], "mode": entry[2]}
        for entry in _PRESETS
    )
