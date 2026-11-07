"""RVC adapter tests: subprocess mocked, no engine needed; one smoke test skipped unless RVC is installed."""
from __future__ import annotations

import hashlib
import os
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from services import singing_conversion as sc
from services import singing_engine_rvc as rvc
from services.singing_project import create_singing_project


def write_wav(path: Path, seconds: float, rate: int = 8000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack("<h", 0) * round(seconds * rate))
    return path


@pytest.fixture()
def setup(tmp_path: Path):
    create_singing_project(tmp_path, "demo")
    guide = write_wav(tmp_path / "demo" / "source" / "guide.wav", 1.0)
    model = tmp_path / "voice.pth"
    model.write_bytes(b"model-bytes")
    engine_dir = tmp_path / "rvc"
    (engine_dir / "infer").mkdir(parents=True)
    (engine_dir / "infer" / "cli.py").write_text("# stub")
    req = sc.ConversionRequest(tmp_path, "demo", guide, str(model), "out.wav")
    return tmp_path, guide, model, engine_dir, req


def test_missing_engine_is_clear_error(setup, monkeypatch):
    _, _, _, _, req = setup
    monkeypatch.delenv(rvc.DIR_ENV, raising=False)
    with pytest.raises(rvc.OptionalSingingEngineNotInstalled, match="optional singing engine not installed"):
        sc.convert_singing(rvc.RvcSingingEngine(), req)


def test_default_install_has_no_engine(monkeypatch):
    monkeypatch.delenv(rvc.DIR_ENV, raising=False)
    assert not rvc.RvcSingingEngine().installed


def test_conversion_records_provenance_offline(setup, monkeypatch):
    _, guide, model, engine_dir, req = setup
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(command=command, env=kwargs["env"], cwd=kwargs["cwd"])
        write_wav(Path(command[command.index("--output") + 1]), 1.0)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(rvc.subprocess, "run", fake_run)
    result = sc.convert_singing(rvc.RvcSingingEngine(engine_dir, version="2.3.260718"), req)
    prov = result.provenance
    assert prov["engine"] == "rvc" and prov["engine_version"] == "2.3.260718" and prov["model"] == "voice.pth"
    assert prov["model_sha256"] == hashlib.sha256(b"model-bytes").hexdigest()
    assert prov["input_sha256"] == hashlib.sha256(guide.read_bytes()).hexdigest()
    assert len(prov["output_sha256"]) == 64
    assert seen["command"][-2:] == ["--index-rate", "0"]
    assert all(Path(seen["command"][i]).is_absolute() for i in (1, 3, 5, 7))
    assert seen["env"]["HF_HUB_OFFLINE"] == "1" and seen["env"]["TRANSFORMERS_OFFLINE"] == "1"
    assert result.engine_id == "rvc"


def test_nonzero_exit_and_missing_output_refused(setup, monkeypatch):
    _, _, _, engine_dir, req = setup
    engine = rvc.RvcSingingEngine(engine_dir, version="v")
    monkeypatch.setattr(rvc.subprocess, "run", lambda c, **k: subprocess.CompletedProcess(c, 1, "", "boom"))
    with pytest.raises(sc.EngineOutputError, match="status 1"):
        sc.convert_singing(engine, req)
    monkeypatch.setattr(rvc.subprocess, "run", lambda c, **k: subprocess.CompletedProcess(c, 0, "", ""))
    with pytest.raises(sc.EngineOutputError, match="no output"):
        sc.convert_singing(engine, req)


def test_missing_model_refused(setup):
    _, _, _, engine_dir, req = setup
    bad = sc.ConversionRequest(req.projects_root, "demo", req.guide_vocal, "/nonexistent.pth", "o2.wav")
    with pytest.raises(sc.InvalidConversionRequest):
        sc.convert_singing(rvc.RvcSingingEngine(engine_dir, version="v"), bad)


@pytest.mark.skipif(not (os.environ.get(rvc.DIR_ENV) and os.environ.get("VOICESTUDIO_RVC_MODEL")),
                    reason=f"optional RVC engine not installed: set {rvc.DIR_ENV} and VOICESTUDIO_RVC_MODEL to run")
def test_smoke_real_rvc(tmp_path):
    create_singing_project(tmp_path, "demo")
    guide = write_wav(tmp_path / "demo" / "source" / "guide.wav", 2.0, 16000)
    req = sc.ConversionRequest(tmp_path, "demo", guide, os.environ["VOICESTUDIO_RVC_MODEL"], "out.wav")
    result = sc.convert_singing(rvc.RvcSingingEngine(), req, allow_drift=True)
    assert result.provenance["output_sha256"]


def test_relative_paths_are_made_absolute_before_the_subprocess_changes_directory(setup, monkeypatch):
    tmp, _, _, engine_dir, req = setup
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        write_wav(Path(command[command.index("--output") + 1]), 1.0)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(rvc.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp)
    sc.convert_singing(rvc.RvcSingingEngine("rvc", version="v"), req)
    assert Path(seen["command"][1]).is_absolute() and Path(seen["command"][1]).is_file()
