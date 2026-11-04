"""Singing project layout (roadmap slice s2-singing-project-layout)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from services.singing_project import singing_project_paths

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
     "a\\b", "..\\escape", "C:\\x", "de\x00mo"],
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
