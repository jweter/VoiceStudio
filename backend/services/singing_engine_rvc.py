"""RVC adapter behind the S4 singing-conversion contract (docs/projects/singing-engine-evaluation.md).

RVC is an *optional* engine, absent by default: nothing here imports it.  It is run as a subprocess of its own
``infer/cli.py`` (an undocumented CLI, so any argument change is a version-bump task) from a user-provided checkout:

* ``VOICESTUDIO_RVC_DIR``    -- the RVC checkout containing ``infer/cli.py`` (required; absent => not installed);
* ``VOICESTUDIO_RVC_PYTHON`` -- interpreter for that checkout's environment (default: the current interpreter).

``target_voice`` is the path of a trained per-voice RVC model (``.pth``).  The subprocess runs with Hugging Face /
Transformers offline flags and never downloads anything here.  The guide vocal's ``F0Track`` is accepted by the
contract but not injected: RVC's CLI does its own pitch extraction (evaluation condition 3).  Provenance (engine,
version, model, input and output SHA-256) is returned on ``EngineOutput.provenance``; the output hash is of the file
as the engine wrote it, before the synthetic-audio mark is applied.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from services.singing_conversion import EngineOutput, EngineOutputError, InvalidConversionRequest, SingingConversionError, wav_duration_seconds

if TYPE_CHECKING:  # pragma: no cover
    from services.singing_pitch import F0Track

DIR_ENV = "VOICESTUDIO_RVC_DIR"
PYTHON_ENV = "VOICESTUDIO_RVC_PYTHON"
CLI_RELATIVE = Path("infer") / "cli.py"
TIMEOUT_SECONDS = 1800


class OptionalSingingEngineNotInstalled(SingingConversionError):
    """The optional RVC singing engine is not installed; the default install never has it."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _detect_version(engine_dir: Path) -> str:
    """Tag/commit of the checkout (local git only); ``unknown`` when it cannot be determined -- never guessed."""
    try:
        done = subprocess.run(["git", "-C", str(engine_dir), "describe", "--tags", "--always"],
                              capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() or "unknown" if done.returncode == 0 else "unknown"


class RvcSingingEngine:
    id = "rvc"
    singing_capabilities = frozenset({"singing_conversion"})

    def __init__(self, engine_dir: str | os.PathLike | None = None, python: str | None = None,
                 version: str | None = None) -> None:
        raw = engine_dir if engine_dir is not None else os.environ.get(DIR_ENV, "")
        self.engine_dir = Path(raw) if raw else None
        self.python = python or os.environ.get(PYTHON_ENV) or sys.executable
        self._version = version

    @property
    def cli(self) -> Path | None:
        return self.engine_dir / CLI_RELATIVE if self.engine_dir else None

    @property
    def installed(self) -> bool:
        return bool(self.cli and self.cli.is_file())

    @property
    def version(self) -> str:
        if self._version is None:
            self._version = _detect_version(self.engine_dir) if self.installed else "not-installed"
        return self._version

    def convert(self, guide_vocal: Path, target_voice: str, output: Path, f0_track: "F0Track | None") -> EngineOutput:
        if not self.installed:
            raise OptionalSingingEngineNotInstalled(
                f"optional singing engine not installed: set {DIR_ENV} to an RVC checkout containing {CLI_RELATIVE}")
        model = Path(target_voice)
        if not model.is_file():
            raise InvalidConversionRequest("target_voice must be the path of an existing RVC model file")
        input_sha = _sha256(guide_vocal)
        command = [self.python, str(self.cli), "--model", str(model), "--input", str(guide_vocal), "--output", str(output)]
        env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        try:
            done = subprocess.run(command, cwd=str(self.engine_dir), env=env, capture_output=True, text=True,
                                  timeout=TIMEOUT_SECONDS, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise EngineOutputError(f"RVC could not be run: {exc}") from exc
        if done.returncode != 0:
            tail = (done.stderr or done.stdout or "").strip()[-500:]
            raise EngineOutputError(f"RVC exited with status {done.returncode}: {tail}")
        if not output.is_file():
            raise EngineOutputError("RVC exited successfully but wrote no output file")
        seconds, rate = wav_duration_seconds(output, EngineOutputError)
        return EngineOutput(rate, seconds, provenance={
            "engine": self.id, "engine_version": self.version, "model": model.name, "model_sha256": _sha256(model),
            "input_sha256": input_sha, "output_sha256": _sha256(output)})
