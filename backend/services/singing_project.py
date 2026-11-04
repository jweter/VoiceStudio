"""Layout of a singing project, as relative POSIX paths.

A singing project is a directory named by its project id.  This module only
*describes* where things live; it never touches the filesystem and imports only
the standard library, so the layout can be tested and reused anywhere.

The layout is the one documented for Singing Mode: ``source`` holds the guide
vocal, ``voice`` the target voice reference, ``analysis`` the derived pitch /
segment / lyric data, ``metadata`` the generation record, ``renders`` the audio
outputs and ``logs`` the run logs.
"""

from __future__ import annotations

# Entry name -> path below the project directory.  Sorted by name on purpose:
# the returned mapping has a stable, reviewable order.
_LAYOUT: dict[str, str] = {
    "analysis_dir": "analysis",
    "f0": "analysis/f0.json",
    "generation": "metadata/generation.json",
    "logs_dir": "logs",
    "lyric_alignment": "analysis/lyric_alignment.json",
    "metadata_dir": "metadata",
    "preview": "renders/preview.wav",
    "renders_dir": "renders",
    "segments": "analysis/segments.json",
    "source_dir": "source",
    "target_voice": "voice/target_voice.json",
    "vocal_full": "renders/vocal_full.wav",
    "voice_dir": "voice",
}


# Separators of either kind, NUL, and the characters Windows forbids in a name.  ":" matters most: it
# makes drive-qualified ids ("C:", "C:..") that discard the projects directory when joined, and
# NTFS alternate-stream names ("demo:stream").
_FORBIDDEN_CHARS = frozenset('/\\\x00:*?"<>|')


def _is_valid_project_id(project_id: object) -> bool:
    """A project id is one plain path segment on every platform: no separators, drive or stream marks, dot segments or blanks."""
    if not isinstance(project_id, str):
        return False
    if not project_id or project_id != project_id.strip():
        return False
    if any(char in project_id for char in _FORBIDDEN_CHARS):
        return False
    # Windows strips trailing dots, so "demo." would alias "demo" and "..." could mean "..".
    return not project_id.endswith(".")


def singing_project_paths(project_id: str) -> dict[str, str]:
    """Return the singing project layout as paths relative to the projects root.

    Every path starts with ``project_id`` and uses ``/`` separators on every
    platform.  An invalid ``project_id`` (empty, blank, padded with whitespace,
    ending in ``.`` -- which covers ``.`` and ``..`` -- containing a path
    separator, ``:`` or another character Windows forbids in names, or not a
    string) yields an empty dict, so a caller can never build a path that
    escapes the projects root.
    """
    if not _is_valid_project_id(project_id):
        return {}
    return {name: f"{project_id}/{relative}" for name, relative in _LAYOUT.items()}
