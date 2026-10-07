import pytest

from services.singing_project import SingingProject, SingingSource


def _source(**overrides):
    values = {
        "kind": "guide_vocal",
        "path": "source/guide_vocal.wav",
        "sha256": "a" * 64,
        "sample_rate": 48000,
        "channels": 1,
        "duration_seconds": 2.5,
    }
    values.update(overrides)
    return SingingSource(**values)


def test_singing_project_round_trip_is_deterministic() -> None:
    project = SingingProject("song-001", _source(), "voice-123", "hello")
    assert SingingProject.from_dict(project.to_dict()) == project
    assert SingingProject.from_dict(project.to_dict()).to_json() == project.to_json()


@pytest.mark.parametrize("path", ["/tmp/guide.wav", "../guide.wav", "source\\guide.wav"])
def test_source_path_must_stay_inside_project(path: str) -> None:
    with pytest.raises(ValueError, match="project-relative"):
        _source(path=path)


def test_source_hash_is_strict_sha256() -> None:
    with pytest.raises(ValueError, match="sha256"):
        _source(sha256="ABC")


def test_project_rejects_unknown_fields() -> None:
    payload = SingingProject("song-001", _source(), "voice-123").to_dict()
    payload["engine_private_state"] = {}
    with pytest.raises(ValueError, match="unsupported fields"):
        SingingProject.from_dict(payload)


def test_source_rejects_coercible_numeric_types() -> None:
    with pytest.raises(ValueError, match="sample_rate"):
        _source(sample_rate=True)
    with pytest.raises(ValueError, match="channels"):
        _source(channels=1.5)


def test_project_requires_explicit_target_voice() -> None:
    with pytest.raises(ValueError, match="target_voice_id"):
        SingingProject("song-001", _source(), "")
