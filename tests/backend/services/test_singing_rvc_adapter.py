"""RVC adapter tests: the subprocess is mocked; one smoke test is skipped unless a real RVC install is configured."""
from __future__ import annotations

import hashlib
import os
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from services import singing_conversion as sc
from services import singing_rvc_adapter as rvc
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
    root = tmp_path / "rvc"
    (root / "infer").mkdir(parents=True)
    (root / "infer" / "cli.py").write_text("# stub\n")
    return tmp_path, guide, model, root


def req(setup, **kw):
    tmp, guide, model, _ = setup
    values = dict(projects_root=tmp, project_id="demo", guide_vocal=guide, target_voice=str(model), output_name="o.wav")
    values.update(kw)
    return sc.ConversionRequest(**values)


def fake_runner(calls, returncode=0, write=True):
    def run(command, **kwargs):
        calls.append((command, kwargs))
        if write:
            write_wav(Path(command[command.index("--output") + 1]), 1.0)
        return subprocess.CompletedProcess(command, returncode, "", "boom")
    return run


def test_missing_engine_gives_clear_error(setup, monkeypatch):
    monkeypatch.delenv(rvc.RVC_DIR_ENV, raising=False)
    with pytest.raises(rvc.OptionalSingingEngineNotInstalled, match="optional singing engine not installed"):
        sc.convert_singing(rvc.RvcSingingEngine(), req(setup))
    assert not (setup[0] / "demo" / "renders" / "o.wav").exists()


def test_missing_cli_in_configured_dir(setup, tmp_path):
    with pytest.raises(rvc.OptionalSingingEngineNotInstalled):
        sc.convert_singing(rvc.RvcSingingEngine(tmp_path / "nowhere"), req(setup))


def test_conversion_records_provenance_offline(setup):
    calls: list = []
    engine = rvc.RvcSingingEngine(setup[3], runner=fake_runner(calls))
    result = sc.convert_singing(engine, req(setup))
    command, kwargs = calls[0]
    assert kwargs["shell"] is False and kwargs["env"]["HF_HUB_OFFLINE"] == "1"
    assert "--model" in command and command[-2:] == ["--pitch", "0"]
    p = result.provenance
    assert p["engine"] == "rvc" and p["engine_version"] == rvc.RVC_PINNED_VERSION and p["model"] == "voice.pth"
    assert p["model_sha256"] == hashlib.sha256(b"model-bytes").hexdigest()
    assert p["input_sha256"] == rvc.sha256_file(setup[1])
    assert p["output_sha256"] and p["network_access"] is False
    assert result.engine_id == "rvc"


def test_failures_are_reported(setup):
    engine = rvc.RvcSingingEngine(setup[3], runner=fake_runner([], returncode=2, write=False))
    with pytest.raises(rvc.EngineInvocationError, match="status 2"):
        sc.convert_singing(engine, req(setup))

    def timeout(command, **kw):
        raise subprocess.TimeoutExpired(command, 1)
    with pytest.raises(rvc.EngineInvocationError, match="timed out"):
        sc.convert_singing(rvc.RvcSingingEngine(setup[3], runner=timeout), req(setup))
    with pytest.raises(sc.EngineOutputError):
        sc.convert_singing(rvc.RvcSingingEngine(setup[3], runner=fake_runner([], write=False)), req(setup))


def test_bad_model_reference(setup):
    engine = rvc.RvcSingingEngine(setup[3], runner=fake_runner([]))
    with pytest.raises(sc.InvalidConversionRequest):
        sc.convert_singing(engine, req(setup, target_voice=str(setup[0] / "missing.pth")))


@pytest.mark.skipif(not (os.environ.get(rvc.RVC_DIR_ENV) and os.environ.get("VOICESTUDIO_RVC_TEST_MODEL")),
                    reason=f"optional singing engine not installed ({rvc.RVC_DIR_ENV} and VOICESTUDIO_RVC_TEST_MODEL unset)")
def test_real_rvc_smoke(setup):  # pragma: no cover - needs a real install
    result = sc.convert_singing(rvc.RvcSingingEngine(), req(setup, target_voice=os.environ["VOICESTUDIO_RVC_TEST_MODEL"]),
                                allow_drift=True)
    assert result.provenance["output_sha256"]
