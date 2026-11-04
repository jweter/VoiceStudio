"""Singing project layout (roadmap slice s2-singing-project-layout)."""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

from services.singing_project import create_singing_project, singing_project_paths

DEMO = {
    "analysis_dir": "demo/analysis",
    "f0": "demo/analysis/f0.json",
    "generation": "demo/metadata/generation.json",
    "logs_dir": "demo/logs",
    "lyric_alignment": "demo/analysis/lyric_alignment.json",
    "metadata_dir": "demo/metadata",
    "preview": "demo/renders/preview.wav",
    "renders_dir": "demo/renders",
    "segments": "demo/analysis/segments.json",
    "source_dir": "demo/source",
    "target_voice": "demo/voice/target_voice.json",
    "vocal_full": "demo/renders/vocal_full.wav",
    "voice_dir": "demo/voice",
}


def test_layout_for_a_valid_project_id() -> None:
    assert singing_project_paths("demo") == DEMO


def test_every_path_is_relative_posix_below_the_project_id() -> None:
    paths = singing_project_paths("my-song_01")
    assert len(paths) == 13
    for value in paths.values():
        assert value.startswith("my-song_01/")
        assert "\\" not in value and not value.startswith("/") and ".." not in value.split("/")


def test_entries_are_sorted_by_name() -> None:
    assert list(singing_project_paths("demo")) == sorted(DEMO)


@pytest.mark.parametrize(
    "bad",
    ["", " ", "   ", " demo", "demo ", "\tdemo", ".", "..", "../escape", "a/b", "/abs", "absolute/path",
     "a\\b", "..\\escape", "C:\\x", "de\x00mo",
     # Windows: drive-qualified / drive-relative ids escape the projects root when joined; "demo." aliases "demo".
     "C:", "C:..", "c:demo", "demo:stream", "...", "demo.", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b"],
)
def test_invalid_project_ids_give_an_empty_layout(bad: str) -> None:
    assert singing_project_paths(bad) == {}


@pytest.mark.parametrize("bad", [None, 1, b"demo", ["demo"]])
def test_non_string_project_ids_give_an_empty_layout(bad: object) -> None:
    assert singing_project_paths(bad) == {}  # type: ignore[arg-type]


def test_a_dotted_name_is_still_one_plain_segment() -> None:
    assert singing_project_paths("v1.2")["f0"] == "v1.2/analysis/f0.json"
    assert singing_project_paths(".hidden")["f0"] == ".hidden/analysis/f0.json"


def test_result_is_a_fresh_dict_each_call() -> None:
    first = singing_project_paths("demo")
    first["f0"] = "changed"
    assert singing_project_paths("demo") == DEMO


def test_module_imports_only_the_standard_library() -> None:
    import services.singing_project as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    roots = {
        (alias.name if isinstance(node, ast.Import) else node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [None])
    }
    assert roots <= set(sys.stdlib_module_names)


DIRS = ["analysis", "logs", "metadata", "renders", "source", "voice"]


def _tree(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


def test_create_makes_exactly_the_six_directories_and_no_files(tmp_path: Path) -> None:
    assert create_singing_project(tmp_path, "demo") == DEMO
    assert _tree(tmp_path) == ["demo", *(f"demo/{d}" for d in DIRS)]
    assert all(p.is_dir() for p in tmp_path.rglob("*"))


def test_create_accepts_a_str_root_and_returns_the_same_layout(tmp_path: Path) -> None:
    assert create_singing_project(str(tmp_path), "demo") == singing_project_paths("demo")


def test_create_is_idempotent_and_leaves_existing_content_alone(tmp_path: Path) -> None:
    create_singing_project(tmp_path, "demo")
    keep = tmp_path / "demo" / "source" / "guide_vocal.wav"
    keep.write_bytes(b"audio")
    assert create_singing_project(tmp_path, "demo") == DEMO
    assert keep.read_bytes() == b"audio"
    assert len(_tree(tmp_path)) == 7 + 1


def test_create_completes_a_partial_project(tmp_path: Path) -> None:
    (tmp_path / "demo" / "analysis").mkdir(parents=True)
    assert create_singing_project(tmp_path, "demo") == DEMO
    assert _tree(tmp_path) == ["demo", *(f"demo/{d}" for d in DIRS)]


@pytest.mark.parametrize("bad", ["", " ", "..", "../escape", "a/b", "C:", "a\b"])
def test_create_refuses_invalid_ids_and_creates_nothing(tmp_path: Path, bad: str) -> None:
    assert create_singing_project(tmp_path, bad) == {}
    assert _tree(tmp_path) == []


def test_create_never_creates_the_projects_root(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-root"
    assert create_singing_project(missing, "demo") == {}
    assert not missing.exists()


def test_create_refuses_a_root_that_is_a_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.write_text("x", encoding="utf-8")
    assert create_singing_project(root, "demo") == {}


def test_create_refuses_when_the_project_path_is_a_file(tmp_path: Path) -> None:
    (tmp_path / "demo").write_text("x", encoding="utf-8")
    assert create_singing_project(tmp_path, "demo") == {}
    assert (tmp_path / "demo").read_text(encoding="utf-8") == "x"


def test_a_blocked_subdirectory_leaves_nothing_new_behind(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "voice").write_text("x", encoding="utf-8")
    assert create_singing_project(tmp_path, "demo") == {}
    assert _tree(tmp_path) == ["demo", "demo/voice"]


def test_create_refuses_a_symlinked_project_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    try:
        os.symlink(outside, root / "demo", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available here")
    assert create_singing_project(root, "demo") == {}
    assert list(outside.iterdir()) == []


def test_create_refuses_a_symlinked_subdirectory(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    (root / "demo").mkdir(parents=True)
    try:
        os.symlink(outside, root / "demo" / "renders", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available here")
    assert create_singing_project(root, "demo") == {}
    assert list(outside.iterdir()) == []
    assert sorted(p.name for p in (root / "demo").iterdir()) == ["renders"]
