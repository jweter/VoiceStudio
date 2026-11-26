"""Tests for backend/services/singing_style_presets.py."""
import json

import pytest

from services.singing_style_presets import (
    get_preset,
    list_presets,
    preset_profile,
    public_listing,
)
from services.singing_style_profile import (
    apply_style_strength,
    neutral_style,
    normalize_style,
    style_dimensions,
)

DIMENSIONS = style_dimensions()
EXPECTED_LABELS = {
    "Haunted Doom Croon",
    "Percussive Thrash Bark",
    "Controlled Alt-Metal Intensity",
    "Elastic Funk-Metal Character",
    "Operatic Metal Screamer",
    "Galloping Arena Tenor",
    "Deep Gothic Baritone",
    "Nu-Metal Whisper-to-Break",
    "Precision Rapid-Fire Rap",
    "Laid-Back West-Coast Flow",
    "Industrial Command Baritone",
    "Staccato Dramatic Spoken",
    "Theatrical Operatic Rock",
    "Blues-Rock Wail",
}
# Every artist or band the R&D references name, whole and in part.
ARTIST_TOKENS = (
    "Ozzy", "Osbourne", "Black Sabbath", "Sabbath", "Metallica", "Tool", "Primus",
    "Judas Priest", "Iron Maiden", "Maiden", "Type O", "Korn", "Eminem", "Snoop",
    "Rammstein", "Walken", "Mercury", "Freddie", "Led Zeppelin", "Zeppelin",
)


def test_there_are_exactly_fourteen_presets_with_unique_ids_and_labels():
    presets = list_presets()
    assert len(presets) == 14
    assert len({p["preset_id"] for p in presets}) == 14
    assert {p["public_label"] for p in presets} == EXPECTED_LABELS
    assert len({p["rd_reference"] for p in presets}) == 14


def test_ids_are_snake_case_identifiers():
    for preset in list_presets():
        pid = preset["preset_id"]
        assert pid == pid.lower() and pid.replace("_", "").isalnum()


def test_every_mode_is_one_of_the_documented_modes():
    modes = {p["mode"] for p in list_presets()}
    assert modes <= {"sung", "rap", "spoken", "hybrid"}
    assert {"sung", "rap", "spoken", "hybrid"} <= modes  # the library exercises all four


def test_every_dimension_is_a_known_name_inside_its_range():
    for preset in list_presets():
        assert preset["dimensions"], preset["preset_id"]
        for name, value in preset["dimensions"].items():
            assert name in DIMENSIONS, (preset["preset_id"], name)
            assert not isinstance(value, bool)
            assert DIMENSIONS[name]["min"] <= value <= DIMENSIONS[name]["max"], (
                preset["preset_id"],
                name,
                value,
            )


def test_normalizing_a_preset_never_changes_its_authored_values():
    for preset in list_presets():
        raw = {"mode": preset["mode"], **preset["dimensions"]}
        normalized = normalize_style(raw)
        assert normalized["mode"] == preset["mode"]
        for name, value in preset["dimensions"].items():
            assert normalized[name] == pytest.approx(value, abs=1e-4)


def test_preset_profile_is_a_complete_normalized_profile():
    for preset in list_presets():
        profile = preset_profile(preset["preset_id"])
        assert profile is not None
        assert set(profile) == {"mode", *DIMENSIONS}
        assert profile == normalize_style(profile)
        assert profile["mode"] == preset["mode"]


def test_a_preset_at_strength_zero_is_neutral_and_at_100_differs():
    for preset in list_presets():
        profile = preset_profile(preset["preset_id"])
        assert apply_style_strength(profile, 0) == neutral_style()
        assert apply_style_strength(profile, 100) != neutral_style()


def test_no_two_presets_have_the_same_dimensions_or_profile():
    seen = set()
    for preset in list_presets():
        key = json.dumps(preset["dimensions"], sort_keys=True)
        assert key not in seen
        seen.add(key)
    profiles = {json.dumps(preset_profile(p["preset_id"]), sort_keys=True) for p in list_presets()}
    assert len(profiles) == 14


def test_public_listing_has_only_id_label_and_mode():
    listing = public_listing()
    assert len(listing) == 14
    for item in listing:
        assert set(item) == {"preset_id", "public_label", "mode"}


def test_public_listing_never_names_an_artist_or_band():
    blob = json.dumps(public_listing())
    for token in ARTIST_TOKENS:
        assert token.lower() not in blob.lower(), token
    for preset in list_presets():
        # The internal reference is real and distinct from anything public.
        assert preset["rd_reference"].lower() not in blob.lower()


def test_in_product_labels_and_ids_contain_no_artist_names():
    for preset in list_presets():
        text = f"{preset['preset_id']} {preset['public_label']}".lower()
        for token in ARTIST_TOKENS:
            assert token.lower() not in text, (preset["preset_id"], token)


def test_get_preset_returns_the_matching_preset_or_none():
    preset = get_preset("haunted_doom_croon")
    assert preset is not None
    assert preset["public_label"] == "Haunted Doom Croon"
    assert preset["rd_reference"] == "Ozzy Osbourne / Black Sabbath"
    for bad in ("nope", "", " haunted_doom_croon", "HAUNTED_DOOM_CROON", None, 5, ["x"], b"x"):
        assert get_preset(bad) is None
        assert preset_profile(bad) is None


def test_returned_objects_are_copies_so_the_library_cannot_be_mutated():
    first = get_preset("blues_rock_wail")
    first["dimensions"]["energy"] = 0.0
    first["public_label"] = "changed"
    again = get_preset("blues_rock_wail")
    assert again["dimensions"]["energy"] == 0.85
    assert again["public_label"] == "Blues-Rock Wail"

    list_presets()[0]["dimensions"].clear()
    assert list_presets()[0]["dimensions"]

    profile = preset_profile("blues_rock_wail")
    profile["energy"] = 0.0
    assert preset_profile("blues_rock_wail")["energy"] == 0.85


def test_presets_carry_no_identity_fields():
    for preset in list_presets():
        assert set(preset) == {"preset_id", "public_label", "mode", "rd_reference", "dimensions"}
        profile = preset_profile(preset["preset_id"])
        assert not any("speaker" in key or "identity" in key or "voice" in key for key in profile)


def test_distinct_character_where_it_matters():
    # Spot checks that the authored values express the documented character.
    thrash = preset_profile("percussive_thrash_bark")
    croon = preset_profile("haunted_doom_croon")
    assert thrash["onset_hardness"] > croon["onset_hardness"]
    assert thrash["legato_clipped"] < 0 < croon["legato_clipped"]

    baritone = preset_profile("deep_gothic_baritone")
    screamer = preset_profile("operatic_metal_screamer")
    assert baritone["register"] < 0 < screamer["register"]

    laid_back = preset_profile("laid_back_west_coast_flow")
    rapid = preset_profile("precision_rapid_fire_rap")
    assert laid_back["rhythmic_placement"] > rapid["rhythmic_placement"]
    assert laid_back["energy"] < rapid["energy"]
    assert laid_back["mode"] == rapid["mode"] == "rap"

    assert preset_profile("staccato_dramatic_spoken")["mode"] == "spoken"
