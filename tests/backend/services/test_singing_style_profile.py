"""Tests for backend/services/singing_style_profile.py."""
import math

import pytest

from services.singing_style_profile import (
    apply_style_overrides,
    apply_style_strength,
    blend_styles,
    neutral_style,
    normalize_style,
    style_dimensions,
)

DIMENSIONS = style_dimensions()
NAMES = sorted(DIMENSIONS)

# A deliberately extreme preset: every dimension pushed as far as its range allows, in the
# direction away from neutral.
EXTREME = {"mode": "rap"}
for _name, _d in DIMENSIONS.items():
    EXTREME[_name] = _d["max"] if _d["max"] - _d["neutral"] >= _d["neutral"] - _d["min"] else _d["min"]


def _distance(profile, name):
    return abs(profile[name] - DIMENSIONS[name]["neutral"])


def test_neutral_style_has_every_dimension_at_its_neutral_value_and_sung_mode():
    profile = neutral_style()
    assert profile["mode"] == "sung"
    assert {k: v for k, v in profile.items() if k != "mode"} == {
        name: DIMENSIONS[name]["neutral"] for name in NAMES
    }


def test_neutral_style_returns_a_fresh_dict_each_call():
    first = neutral_style()
    first["energy"] = 1.0
    assert neutral_style()["energy"] == DIMENSIONS["energy"]["neutral"]


def test_dimension_table_is_consistent():
    assert NAMES == list(DIMENSIONS)  # stable, sorted order
    for name, d in DIMENSIONS.items():
        assert d["min"] <= d["neutral"] <= d["max"], name
        assert d["cap"] > 0, name
    # No dimension may describe a speaker; identity is not part of a style.
    assert not [n for n in NAMES if "speaker" in n or "identity" in n or "timbre" in n]


def test_normalize_fills_missing_dimensions_with_neutral():
    assert normalize_style({}) == neutral_style()
    assert normalize_style({"energy": 0.9})["energy"] == 0.9
    assert normalize_style({"energy": 0.9})["grit"] == DIMENSIONS["grit"]["neutral"]


def test_normalize_clamps_to_each_dimensions_range():
    profile = normalize_style({"energy": 5, "register": -9, "grit": -1})
    assert profile["energy"] == 1.0
    assert profile["register"] == -1.0
    assert profile["grit"] == 0.0


def test_normalize_drops_unknown_keys_including_identity_attempts():
    profile = normalize_style({"speaker_embedding": [1, 2], "identity": "x", "voice": "y", "energy": 0.7})
    assert set(profile) == set(neutral_style())
    assert profile["energy"] == 0.7


@pytest.mark.parametrize("bad", [None, "0.5", [0.5], True, False, math.nan, math.inf, -math.inf, {}])
def test_normalize_treats_non_finite_or_non_numeric_values_as_neutral(bad):
    assert normalize_style({"grit": bad})["grit"] == DIMENSIONS["grit"]["neutral"]


@pytest.mark.parametrize("raw", [None, 5, "rap", [1, 2], (), set()])
def test_normalize_of_a_non_mapping_is_neutral(raw):
    assert normalize_style(raw) == neutral_style()


@pytest.mark.parametrize("mode", ["sung", "rap", "spoken", "hybrid"])
def test_normalize_keeps_known_modes(mode):
    assert normalize_style({"mode": mode})["mode"] == mode


@pytest.mark.parametrize("mode", ["scream", "", None, 3, ["rap"], "RAP"])
def test_normalize_replaces_unknown_modes_with_sung(mode):
    assert normalize_style({"mode": mode})["mode"] == "sung"


def test_normalize_is_idempotent():
    once = normalize_style({"energy": 0.123456789, "register": 2})
    assert normalize_style(once) == once


def test_strength_zero_is_exactly_neutral():
    assert apply_style_strength(EXTREME, 0) == neutral_style()


def test_strength_100_reaches_the_cap_but_never_beyond():
    profile = apply_style_strength(EXTREME, 100)
    for name in NAMES:
        full = _distance(normalize_style(EXTREME), name)
        assert _distance(profile, name) == pytest.approx(min(full, DIMENSIONS[name]["cap"]), abs=1e-4)
        assert _distance(profile, name) <= DIMENSIONS[name]["cap"] + 1e-4


def test_strength_increases_every_dimension_monotonically():
    previous = {name: 0.0 for name in NAMES}
    for strength in range(0, 101, 5):
        profile = apply_style_strength(EXTREME, strength)
        for name in NAMES:
            now = _distance(profile, name)
            assert now >= previous[name] - 1e-9, (name, strength)
            previous[name] = now


def test_strength_scales_linearly_below_the_cap():
    preset = {"breathiness": 0.4}
    assert apply_style_strength(preset, 50)["breathiness"] == 0.2
    assert apply_style_strength(preset, 25)["breathiness"] == 0.1
    assert apply_style_strength(preset, 100)["breathiness"] == 0.4


def test_strength_moves_toward_a_preset_value_below_neutral():
    # vibrato_depth neutral is 0.2; a preset of 0.0 moves it down, never below the range.
    assert apply_style_strength({"vibrato_depth": 0.0}, 100)["vibrato_depth"] == 0.0
    assert apply_style_strength({"vibrato_depth": 0.0}, 50)["vibrato_depth"] == 0.1


def test_strength_above_100_is_treated_as_100_and_below_0_as_0():
    assert apply_style_strength(EXTREME, 250) == apply_style_strength(EXTREME, 100)
    assert apply_style_strength(EXTREME, -40) == neutral_style()


@pytest.mark.parametrize("bad", [None, "50", True, math.nan, math.inf, -math.inf, [50], {}])
def test_unusable_strength_fails_closed_to_neutral(bad):
    assert apply_style_strength(EXTREME, bad) == neutral_style()


def test_mode_stays_neutral_below_half_strength_and_follows_the_preset_from_half():
    assert apply_style_strength({"mode": "rap"}, 49.9)["mode"] == "sung"
    assert apply_style_strength({"mode": "rap"}, 50)["mode"] == "rap"
    assert apply_style_strength({"mode": "rap"}, 100)["mode"] == "rap"


def test_strength_accepts_int_and_float_equivalently():
    assert apply_style_strength(EXTREME, 40) == apply_style_strength(EXTREME, 40.0)


def test_strength_does_not_mutate_its_inputs():
    preset = dict(EXTREME)
    apply_style_strength(preset, 60)
    assert preset == EXTREME


def test_strength_of_a_malformed_preset_is_neutral():
    assert apply_style_strength("not a preset", 100) == neutral_style()
    assert apply_style_strength(None, 100) == neutral_style()


def test_overrides_replace_only_the_named_dimensions():
    base = normalize_style({"energy": 0.6, "grit": 0.3})
    result = apply_style_overrides(base, {"grit": 0.9})
    assert result["grit"] == 0.9
    assert result["energy"] == 0.6


def test_overrides_are_clamped_to_range():
    result = apply_style_overrides({}, {"register": 7, "energy": -3})
    assert result["register"] == 1.0
    assert result["energy"] == 0.0


def test_overrides_can_set_a_known_mode_only():
    assert apply_style_overrides({}, {"mode": "spoken"})["mode"] == "spoken"
    assert apply_style_overrides({"mode": "rap"}, {"mode": "scream"})["mode"] == "rap"


def test_overrides_ignore_unknown_keys_and_unusable_values():
    base = normalize_style({"energy": 0.6})
    result = apply_style_overrides(
        base, {"speaker": "x", "energy": math.nan, "grit": "high", "breathiness": True}
    )
    assert result == base


@pytest.mark.parametrize("overrides", [None, 3, "grit", [("grit", 1)]])
def test_non_mapping_overrides_leave_the_profile_normalized_but_unchanged(overrides):
    base = normalize_style({"energy": 0.6})
    assert apply_style_overrides(base, overrides) == base


def test_overrides_normalize_a_malformed_profile():
    assert apply_style_overrides("junk", {"grit": 0.5})["grit"] == 0.5


def test_blend_endpoints_return_each_normalized_profile():
    a = normalize_style({"energy": 0.9, "mode": "rap"})
    b = normalize_style({"energy": 0.1, "register": -0.8, "mode": "spoken"})
    assert blend_styles(a, b, 0) == a
    assert blend_styles(a, b, 1) == b


def test_blend_midpoint_is_the_dimension_average():
    a = {"energy": 0.2, "register": -1.0}
    b = {"energy": 0.8, "register": 1.0}
    mid = blend_styles(a, b, 0.5)
    assert mid["energy"] == 0.5
    assert mid["register"] == 0.0


def test_blend_is_symmetric_when_the_mix_is_mirrored():
    a = normalize_style({"energy": 0.9, "grit": 0.1})
    b = normalize_style({"energy": 0.3, "grit": 0.7})
    forward = blend_styles(a, b, 0.25)
    backward = blend_styles(b, a, 0.75)
    for name in NAMES:
        assert forward[name] == pytest.approx(backward[name], abs=1e-4)


def test_blend_mode_follows_the_larger_share_with_ties_going_to_the_first():
    a = {"mode": "rap"}
    b = {"mode": "spoken"}
    assert blend_styles(a, b, 0.4)["mode"] == "rap"
    assert blend_styles(a, b, 0.5)["mode"] == "rap"
    assert blend_styles(a, b, 0.6)["mode"] == "spoken"


def test_blend_clamps_the_mix_to_zero_through_one():
    a = normalize_style({"energy": 0.2})
    b = normalize_style({"energy": 0.8})
    assert blend_styles(a, b, -5) == a
    assert blend_styles(a, b, 5) == b


@pytest.mark.parametrize("bad", [None, "0.5", True, math.nan, math.inf, [0.5]])
def test_unusable_mix_fails_closed_to_the_first_profile(bad):
    a = normalize_style({"energy": 0.2, "mode": "rap"})
    b = normalize_style({"energy": 0.8})
    assert blend_styles(a, b, bad) == a


def test_blend_never_leaves_a_dimension_range_and_carries_no_identity():
    a = normalize_style(EXTREME)
    b = normalize_style({name: DIMENSIONS[name]["min"] for name in NAMES})
    for mix in (0, 0.1, 0.33, 0.5, 0.9, 1):
        blended = blend_styles(a, b, mix)
        assert set(blended) == set(neutral_style())
        for name in NAMES:
            assert DIMENSIONS[name]["min"] <= blended[name] <= DIMENSIONS[name]["max"]


HUGE = 10**400


def test_normalize_clamps_integers_too_large_for_a_float():
    profile = normalize_style({"energy": HUGE, "register": -HUGE, "grit": -HUGE})
    assert profile["energy"] == 1.0
    assert profile["register"] == -1.0
    assert profile["grit"] == 0.0


def test_strength_treats_integers_too_large_for_a_float_as_the_range_ends():
    preset = {"breathiness": 0.4}
    assert apply_style_strength(preset, HUGE) == apply_style_strength(preset, 100)
    assert apply_style_strength(preset, -HUGE) == neutral_style()


def test_oversized_integers_inside_a_preset_do_not_raise_through_strength():
    # The preset clamps to 1.0; neutral 0.4 plus the 0.6 cap lands exactly on the range end.
    assert apply_style_strength({"energy": HUGE}, 100)["energy"] == 1.0
    assert apply_style_strength({"energy": -HUGE}, 100)["energy"] == 0.0


def test_overrides_clamp_integers_too_large_for_a_float():
    result = apply_style_overrides({}, {"register": HUGE, "energy": -HUGE})
    assert result["register"] == 1.0
    assert result["energy"] == 0.0


def test_blend_clamps_a_mix_that_is_an_integer_too_large_for_a_float():
    a = normalize_style({"energy": 0.2})
    b = normalize_style({"energy": 0.8})
    assert blend_styles(a, b, HUGE) == b
    assert blend_styles(a, b, -HUGE) == a


def test_integers_arriving_through_json_are_handled():
    import json

    raw = json.loads('{"energy": 1' + "0" * 400 + ', "register": -1' + "0" * 400 + "}")
    assert isinstance(raw["energy"], int)
    profile = normalize_style(raw)
    assert profile["energy"] == 1.0
    assert profile["register"] == -1.0


def test_style_dimensions_returns_a_copy():
    dims = style_dimensions()
    dims["energy"]["cap"] = 99
    assert style_dimensions()["energy"]["cap"] != 99
