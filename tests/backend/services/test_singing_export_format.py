"""Tests for backend/services/singing_export_format.py."""
import pytest

from services.singing_export_format import singing_export_codec_args

WAV = ["-c:a", "pcm_s16le"]
M4A = ["-c:a", "aac", "-b:a", "192k"]
MP3 = ["-c:a", "libmp3lame", "-q:a", "2"]
FLAC = ["-c:a", "flac"]


@pytest.mark.parametrize(
    "container_format,expected",
    [
        ("wav", WAV),
        ("m4a", M4A),
        ("mp3", MP3),
        ("flac", FLAC),
    ],
)
def test_documented_formats(container_format, expected):
    assert singing_export_codec_args(container_format) == expected


@pytest.mark.parametrize(
    "container_format,expected",
    [
        ("WAV", WAV),
        ("Mp3", MP3),
        ("FLAC", FLAC),
        ("  wav  ", WAV),
        ("\tmp3\n", MP3),
        (" M4A ", M4A),
    ],
)
def test_matching_ignores_case_and_surrounding_whitespace(container_format, expected):
    assert singing_export_codec_args(container_format) == expected


@pytest.mark.parametrize(
    "container_format",
    [
        "ogg",
        "unknown",
        "",
        "   ",
        None,
        123,
        3.14,
        [],
        {},
        object(),
    ],
)
def test_unrecognized_or_non_string_input_falls_back_to_m4a(container_format):
    assert singing_export_codec_args(container_format) == M4A


def test_fallback_and_result_are_independent_copies():
    """Mutating a returned list must not affect the next call's result."""
    first = singing_export_codec_args("wav")
    first.append("mutated")
    second = singing_export_codec_args("wav")
    assert second == WAV
