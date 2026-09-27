from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def _preflight_module():
    path = ROOT / "engineering" / "preflight.py"
    spec = importlib.util.spec_from_file_location("voice_preflight", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_control_plane_separates_canonical_and_development_repository():
    payload = json.loads(
        (ROOT / "engineering" / "control-plane.json").read_text(encoding="utf-8")
    )
    assert payload["repository"] == "debpalash/VoiceStudio"
    assert payload["development_repository"] == "jweter/VoiceStudio"
    assert payload["work_ownership"]["canonical_repository"] == "debpalash/VoiceStudio"
    assert payload["work_ownership"]["development_repository"] == "jweter/VoiceStudio"


def test_required_preflight_includes_renderer_workflow_smokes():
    payload = json.loads(
        (ROOT / "engineering" / "control-plane.json").read_text(encoding="utf-8")
    )
    by_id = {item["id"]: item for item in payload["preflight"]["checks"]}
    assert by_id["renderer_workflow_smokes"]["argv"] == [
        "python",
        "engineering/renderer_smoke.py",
    ]
    assert by_id["playwright_chromium_environment"]["argv"] == [
        "bunx",
        "playwright",
        "install",
        "chromium",
    ]


def test_run_check_forces_offline_empty_huggingface_cache(monkeypatch):
    preflight = _preflight_module()
    captured = {}

    def fake_run(argv, **kwargs):
        captured["env"] = kwargs["env"]
        cache = Path(captured["env"]["HF_HUB_CACHE"])
        home = Path(captured["env"]["HF_HOME"])
        assert cache.parent.exists()
        assert not cache.exists()
        assert not home.exists()
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(preflight.shutil, "which", lambda _name: "python")
    monkeypatch.setattr(preflight.subprocess, "run", fake_run)

    result = preflight.run_check({"id": "test", "argv": ["python", "-V"]})

    assert result["returncode"] == 0
    assert captured["env"]["HF_HUB_OFFLINE"] == "1"


def test_preflight_evidence_is_gitignored():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/preflight-evidence.json" in ignore
