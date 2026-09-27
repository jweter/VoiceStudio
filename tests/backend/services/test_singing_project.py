import json
from pathlib import Path

import pytest

from services.singing_project import (
    SingingProject,
    SingingSource,
    load_project,
    save_project,
    sha256_file,
)

def _file(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path

def test_source_records_content_hash(tmp_path):
    guide = _file(tmp_path, "guide.wav", b"guide-audio")
    source = SingingSource.from_file(guide, "guide_vocal")
    assert source.sha256 == sha256_file(guide)
    assert len(source.sha256) == 64

def test_conversion_requires_guide_and_target(tmp_path):
    voice = SingingSource.from_file(_file(tmp_path, "voice.wav", b"voice"), "target_voice")
    project = SingingProject(project_id="song-1", mode="conversion", sources=[voice])
    with pytest.raises(ValueError, match="guide_vocal"):
        project.validate()

def test_synthesis_requires_melody_and_target(tmp_path):
    voice = SingingSource.from_file(_file(tmp_path, "voice.wav", b"voice"), "target_voice")
    project = SingingProject(project_id="song-1", mode="synthesis", sources=[voice])
    with pytest.raises(ValueError, match="melody"):
        project.validate()

def test_source_roles_are_unique(tmp_path):
    first = SingingSource.from_file(_file(tmp_path, "a.wav", b"a"), "guide_vocal")
    second = SingingSource.from_file(_file(tmp_path, "b.wav", b"b"), "guide_vocal")
    voice = SingingSource.from_file(_file(tmp_path, "voice.wav", b"v"), "target_voice")
    with pytest.raises(ValueError, match="unique"):
        SingingProject("song-1", "conversion", [first, second, voice]).validate()

def test_project_round_trip_is_deterministic_and_keeps_hashes(tmp_path):
    guide = SingingSource.from_file(_file(tmp_path, "guide.wav", b"guide"), "guide_vocal")
    voice = SingingSource.from_file(_file(tmp_path, "voice.wav", b"voice"), "target_voice")
    project = SingingProject("song-1", "conversion", [guide, voice], analysis={"status": "pending"})
    manifest = tmp_path / "metadata" / "singing-project.json"
    save_project(project, manifest)
    first = manifest.read_bytes()
    loaded = load_project(manifest)
    save_project(loaded, manifest)
    assert manifest.read_bytes() == first
    assert loaded.to_dict() == project.to_dict()

def test_unknown_schema_version_fails_closed(tmp_path):
    manifest = tmp_path / "project.json"
    manifest.write_text(json.dumps({"schema_version": 999, "project_id": "x", "mode": "conversion"}))
    with pytest.raises(ValueError, match="schema_version"):
        load_project(manifest)
