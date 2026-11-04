"""Layout of a singing project, as relative POSIX paths.

A singing project is a directory named by its project id.  ``singing_project_paths``
only *describes* where things live and never touches the filesystem;
``create_singing_project`` makes the project's directories (and nothing else).
The module imports only the standard library.

The layout is the one documented for Singing Mode: ``source`` holds the guide
vocal, ``voice`` the target voice reference, ``analysis`` the derived pitch /
segment / lyric data, ``metadata`` the generation record, ``renders`` the audio
outputs and ``logs`` the run logs.
"""

from __future__ import annotations

from pathlib import Path

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


# The directory entries of the layout, parents before children, in creation order.
_DIRECTORY_ENTRIES = ("source_dir", "analysis_dir", "voice_dir", "renders_dir", "metadata_dir", "logs_dir")


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
    # Control characters are refused everywhere: Windows rejects them in names, Linux would accept them.
    if any(char in _FORBIDDEN_CHARS or ord(char) < 32 or ord(char) == 127 for char in project_id):
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


def create_singing_project(root: Path | str, project_id: str) -> dict[str, str]:
    """Create the directories of a singing project below ``root`` and return its layout.

    Returns ``singing_project_paths(project_id)`` once ``source/``, ``analysis/``, ``voice/``,
    ``renders/``, ``metadata/`` and ``logs/`` exist under ``root / project_id``.  It is idempotent and
    additive: it never writes a file, never deletes or replaces anything, and leaves existing content
    alone.  It returns ``{}`` and creates nothing when

    * ``project_id`` is invalid (see ``singing_project_paths``);
    * ``root`` is not an existing directory (the projects root is never created here);
    * the project directory, or any of its directories, already exists as something other than a real
      directory (a file or a symlink), so a link can never redirect the project outside ``root``;
    * the filesystem refuses (``OSError``).

    All the checks above run before the first directory is created, so a refusal by them leaves nothing
    behind.  (An ``OSError`` while creating can still leave the directories made before it; they are
    plain empty directories and a retry completes them.)  A symlinked ``root`` is accepted: it is the
    caller's chosen location, and only links *inside* the project are refused.
    """
    layout = singing_project_paths(project_id)
    if not layout:
        return {}
    try:
        base = Path(root)
        if not base.is_dir():
            return {}
        project = base / project_id
        directories = [project, *(base / layout[name] for name in _DIRECTORY_ENTRIES)]
        for directory in directories:
            if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
                return {}
        for directory in directories:
            directory.mkdir(exist_ok=True)
    except OSError:
        return {}
    return layout
