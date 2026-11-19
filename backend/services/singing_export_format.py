"""ffmpeg audio codec args for singing-export container formats.

Mirrors the dub-export codec table (``backend/api/routers/dub_export.py``'s
``_AUDIO_FORMAT_CODECS``) so the two export paths agree on container -> codec
mapping, without either importing the other.
"""

from __future__ import annotations

#: Singing-export container format -> ffmpeg audio codec args. Any format
#: not listed here (including non-string or malformed input) falls back to
#: the "m4a" entry so a bad export request can never build a broken ffmpeg
#: command.
SINGING_EXPORT_CODEC_ARGS: dict[str, list[str]] = {
    "wav": ["-c:a", "pcm_s16le"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "flac": ["-c:a", "flac"],
}

_FALLBACK_FORMAT = "m4a"


def singing_export_codec_args(container_format: object) -> list[str]:
    """Return the ffmpeg ``-c:a ...`` args for a singing-export container format.

    Matching is case-insensitive and ignores surrounding whitespace. Any
    value that isn't one of the documented formats once normalized -
    including an empty string, a value of the wrong type, or anything else
    unrecognized - falls back to the "m4a" args. This function never raises.
    """
    normalized = container_format.strip().lower() if isinstance(container_format, str) else None

    codec_args = SINGING_EXPORT_CODEC_ARGS.get(
        normalized, SINGING_EXPORT_CODEC_ARGS[_FALLBACK_FORMAT]
    )
    return list(codec_args)
