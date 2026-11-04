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


def _is_valid_project_id(project_id: object) -> bool:
    """A project id is one plain path segment: no separators, no dot segments, no blanks."""
    if not isinstance(project_id, str):
        return False
    if not project_id or project_id != project_id.strip():
        return False
    if "/" in project_id or "\\" in project_id or "\x00" in project_id:
        return False
    return project_id not in {".", ".."}


def singing_project_paths(project_id: str) -> dict[str, str]:
    """Return the singing project layout as paths relative to the projects root.

    Every path starts with ``project_id`` and uses ``/`` separators on every
    platform.  An invalid ``project_id`` (empty, blank, padded with whitespace,
    ``.``/``..``, containing a path separator or NUL, or not a string) yields an
    empty dict, so a caller can never build a path that escapes the project.
    """
    if not _is_valid_project_id(project_id):
        return {}
    return {name: f"{project_id}/{relative}" for name, relative in _LAYOUT.items()}
