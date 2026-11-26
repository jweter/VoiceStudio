"""Tests for backend/services/singing_control_layer.py."""
import copy
import json
import math

import pytest

from services.singing_control_layer import control_ranges, render_controls
from services.singing_style_profile import neutral_style, normalize_style, style_dimensions

DIMENSIONS = style_dimensions()
RANGES = control_ranges()
BY_DIMENSION = {spec["dimension"]: name for name, spec in RANGES.items()}


def _profile_at(extreme, **overrides):
    """A profile with every dimension at its min or max, plus explicit overrides."""
    profile = {"mode": "sung"}
    for name, spec in DIMENSIONS.items():
        profile[name] = spec[extreme]
    profile.update(overrides)
    return profile


def test_every_style_dimension_has_exactly_one_control():
    assert set(BY_DIMENSION) == set(DIMENSIONS)
    assert len(RANGES) == len(DIMENSIONS)


def test_control_ranges_are_ordered_and_have_units():
    for name, spec in RANGES.items():
        assert spec["min"] <= spec["max"], name
        assert isinstance(spec["unit"], str) and spec["unit"]
        assert spec["dimension"] in DIMENSIONS


def test_the_neutral_profile_maps_to_documented_baseline_values():
    result = render_controls(neutral_style())
    controls = result["controls"]
    assert result["mode"] == "sung"
    assert result["unsupported_dimensions"] == []
    assert result["applied_rules"] == []
    assert controls["vibrato_rate_hz"]["value"] == pytest.approx(5.0)
    assert controls["vibrato_depth_cents"]["value"] == pytest.approx(20.0)
    assert controls["onset_offset_ms"]["value"] == pytest.approx(0.0)
    assert controls["note_gap_ms"]["value"] == pytest.approx(60.0)
    assert controls["attack_time_ms"]["value"] == pytest.approx(57.5)
    assert controls["pitch_jitter_cents"]["value"] == pytest.approx(5.0)
    assert controls["breath_mix"]["value"] == 0.0
    assert controls["register_balance"]["value"] == 0.0


def test_each_dimension_endpoint_maps_to_its_documented_end_value():
    # Move one dimension at a time from neutral so the interaction rules cannot interfere.
    for dimension, spec in DIMENSIONS.items():
        name = BY_DIMENSION[dimension]
        ends = []
        for extreme in ("min", "max"):
            profile = {"mode": "sung", dimension: spec[extreme]}
            ends.append(render_controls(profile)["controls"][name]["value"])
        bounds = RANGES[name]
        assert sorted(ends) == pytest.approx([bounds["min"], bounds["max"]]), (dimension, ends)


def test_direction_of_each_control_follows_its_documented_meaning():
    low = render_controls(_profile_at("min", mode="sung"))["controls"]
    high = render_controls(_profile_at("max", mode="sung"))["controls"]
    # More of the dimension -> larger control, except the three deliberately inverted ones.
    inverted = {"note_gap_ms", "attack_time_ms", "pitch_jitter_cents"}
    for name, spec in RANGES.items():
        # The double-track rule lowers formant shift at the top, so judge that one separately.
        if name == "max_formant_shift_semitones":
            continue
        if name in inverted:
            assert high[name]["value"] < low[name]["value"], name
        else:
            assert high[name]["value"] > low[name]["value"], name
    assert high["max_formant_shift_semitones"]["value"] == pytest.approx(2.0)  # capped at 0.5


def test_every_control_value_stays_inside_its_documented_range():
    profiles = [
        _profile_at("min"),
        _profile_at("max"),
        neutral_style(),
        {"mode": "rap", **{n: d["max"] for n, d in DIMENSIONS.items()}},
        {"mode": "spoken", **{n: d["min"] for n, d in DIMENSIONS.items()}},
        {"mode": "sung", "energy": 99, "register": -99},  # clamped by normalization
    ]
    for profile in profiles:
        for name, control in render_controls(profile)["controls"].items():
            bounds = RANGES[name]
            assert bounds["min"] - 1e-9 <= control["value"] <= bounds["max"] + 1e-9, (name, profile)


def test_rap_and_spoken_modes_hold_vibrato_and_scoop_at_zero():
    base = {"vibrato_depth": 0.9, "scoop_tendency": 0.8, "vibrato_rate": 0.7}
    for mode in ("rap", "spoken"):
        result = render_controls({"mode": mode, **base})
        assert result["controls"]["vibrato_depth_cents"]["value"] == 0.0
        assert result["controls"]["scoop_depth_cents"]["value"] == 0.0
        assert result["controls"]["vibrato_rate_hz"]["value"] > 3.0  # rate itself is untouched
        assert result["applied_rules"] == ["free_rhythm_mode_suppresses_vibrato_and_scoop"]
    for mode in ("sung", "hybrid"):
        result = render_controls({"mode": mode, **base})
        assert result["controls"]["vibrato_depth_cents"]["value"] == pytest.approx(90.0)
        assert result["applied_rules"] == []


def test_the_mode_rule_is_not_reported_when_nothing_changed():
    result = render_controls({"mode": "rap", "vibrato_depth": 0.0, "scoop_tendency": 0.0})
    assert result["applied_rules"] == []


def test_strong_double_tracking_caps_the_formant_shift():
    capped = render_controls({"double_track_tendency": 0.8, "formant_shift_allowance": 1.0})
    assert capped["controls"]["max_formant_shift_semitones"]["value"] == pytest.approx(2.0)
    assert capped["applied_rules"] == ["double_tracking_limits_formant_shift"]

    boundary = render_controls({"double_track_tendency": 0.5, "formant_shift_allowance": 1.0})
    assert boundary["controls"]["max_formant_shift_semitones"]["value"] == pytest.approx(4.0)
    assert boundary["applied_rules"] == []

    already_low = render_controls({"double_track_tendency": 0.9, "formant_shift_allowance": 0.25})
    assert already_low["controls"]["max_formant_shift_semitones"]["value"] == pytest.approx(1.0)
    assert already_low["applied_rules"] == []


def test_both_rules_report_in_a_fixed_order():
    result = render_controls(
        {
            "mode": "rap",
            "vibrato_depth": 0.5,
            "double_track_tendency": 0.9,
            "formant_shift_allowance": 1.0,
        }
    )
    assert result["applied_rules"] == [
        "free_rhythm_mode_suppresses_vibrato_and_scoop",
        "double_tracking_limits_formant_shift",
    ]


def test_an_unsupported_dimension_is_omitted_and_reported():
    supported = [d for d in DIMENSIONS if d not in ("grit", "vibrato_depth")]
    result = render_controls(neutral_style(), supported)
    assert "saturation_drive" not in result["controls"]
    assert "vibrato_depth_cents" not in result["controls"]
    assert result["unsupported_dimensions"] == ["grit", "vibrato_depth"]
    assert len(result["controls"]) == len(DIMENSIONS) - 2


def test_unknown_names_in_the_capability_list_are_ignored():
    result = render_controls(neutral_style(), list(DIMENSIONS) + ["telepathy", 7, None])
    assert result["unsupported_dimensions"] == []
    assert len(result["controls"]) == len(DIMENSIONS)


def test_capabilities_may_be_any_collection_of_names():
    for caps in (["energy"], ("energy",), {"energy"}, frozenset({"energy"}), iter(["energy"])):
        result = render_controls(neutral_style(), caps)
        assert list(result["controls"]) == ["energy"]


def test_an_empty_declaration_supports_nothing():
    result = render_controls(neutral_style(), [])
    assert result["controls"] == {}
    assert result["unsupported_dimensions"] == sorted(DIMENSIONS)


@pytest.mark.parametrize("bad", ["energy", b"energy", 5, 3.5, True, {"energy": True}, object()])
def test_an_invalid_capability_declaration_supports_nothing_never_everything(bad):
    result = render_controls(neutral_style(), bad)
    assert result["controls"] == {}
    assert result["unsupported_dimensions"] == sorted(DIMENSIONS)


def test_a_suppressed_dimension_still_reports_the_rule_even_if_unsupported():
    result = render_controls({"mode": "rap", "vibrato_depth": 0.9}, ["energy"])
    assert result["applied_rules"] == ["free_rhythm_mode_suppresses_vibrato_and_scoop"]
    assert list(result["controls"]) == ["energy"]


@pytest.mark.parametrize("bad", [None, "x", 5, [1, 2], math.nan, object()])
def test_a_malformed_profile_fails_closed_to_the_neutral_baseline(bad):
    assert render_controls(bad) == render_controls(neutral_style())


def test_out_of_range_and_non_finite_values_are_normalized_first():
    result = render_controls({"energy": 99, "grit": math.nan, "register": -50})
    assert result["controls"]["energy"]["value"] == 1.0
    assert result["controls"]["saturation_drive"]["value"] == 0.0  # neutral for nan
    assert result["controls"]["register_balance"]["value"] == -1.0


def test_the_input_profile_is_never_mutated():
    profile = {"mode": "rap", "vibrato_depth": 0.9, "double_track_tendency": 0.9}
    before = copy.deepcopy(profile)
    render_controls(profile, ["vibrato_depth"])
    assert profile == before


def test_the_result_is_json_serializable_and_deterministic():
    profile = normalize_style({"mode": "hybrid", "energy": 0.7, "scoop_tendency": 0.4})
    first = render_controls(profile)
    assert json.loads(json.dumps(first)) == first
    assert render_controls(profile) == first


def test_controls_are_listed_in_dimension_name_order():
    names = [spec["dimension"] for spec in (render_controls(neutral_style())["controls"]).values()]
    assert names == sorted(names)


def test_there_is_no_identity_in_the_output():
    result = render_controls({"mode": "sung", "speaker_id": "abc", "identity": "me", "voice": "x"})
    text = json.dumps(result).lower()
    for token in ("speaker", "identity", "voice", "abc"):
        assert token not in text


def test_a_style_strength_result_feeds_straight_into_the_layer():
    from services.singing_style_profile import apply_style_strength

    preset = normalize_style({"mode": "sung", "vibrato_depth": 1.0, "energy": 1.0})
    soft = render_controls(apply_style_strength(preset, 25))["controls"]
    strong = render_controls(apply_style_strength(preset, 100))["controls"]
    assert strong["vibrato_depth_cents"]["value"] > soft["vibrato_depth_cents"]["value"]
    assert strong["energy"]["value"] > soft["energy"]["value"]


def test_every_library_preset_maps_to_in_range_controls_for_a_full_engine():
    from services.singing_style_presets import list_presets, preset_profile

    for preset in list_presets():
        result = render_controls(preset_profile(preset["preset_id"]))
        assert result["mode"] == preset["mode"]
        assert result["unsupported_dimensions"] == []
        assert len(result["controls"]) == len(DIMENSIONS)
        for name, control in result["controls"].items():
            bounds = RANGES[name]
            assert bounds["min"] - 1e-9 <= control["value"] <= bounds["max"] + 1e-9, (
                preset["preset_id"],
                name,
            )


def test_rap_and_spoken_presets_get_no_vibrato_or_scoop_from_the_layer():
    from services.singing_style_presets import list_presets, preset_profile

    for preset in list_presets():
        if preset["mode"] not in ("rap", "spoken"):
            continue
        controls = render_controls(preset_profile(preset["preset_id"]))["controls"]
        assert controls["vibrato_depth_cents"]["value"] == 0.0
        assert controls["scoop_depth_cents"]["value"] == 0.0
