"""First real singing-conversion adapter: RVC behind the S4 contract (docs/projects/singing-engine-evaluation.md).

RVC is an *optional* external install, absent by default.  It is never imported: its ``infer/cli.py`` is run as a
subprocess from the directory named by ``VOICESTUDIO_RVC_DIR``.  Nothing here touches the network -- the child process
is started with Hugging Face/transformers offline switches and the adapter itself opens no sockets.  Because RVC's CLI is
not a documented contract, the argument list is pinned to ``RVC_PINNED_VERSION``; changing it is a version-bump task.

``target_voice`` is the path to a per-voice RVC ``.pth`` model.  The adapter records engine, version, model and
input/output SHA-256 hashes in the ``EngineOutput.provenance`` that ``convert_singing`` copies into its result.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from services.singing_conversion import (
    EngineOutput, EngineOutputError, InvalidConversionRequest, SingingConversionError, wav_duration_seconds,
)

RVC_ENGINE_ID = "rvc"
RVC_PINNED_VERSION = "2.3.260718"  # tag evaluated in docs/projects/singing-engine-evaluation.md
RVC_DIR_ENV = "VOICESTUDIO_RVC_DIR"
DEFAULT_TIMEOUT_SECONDS = 600.0
_OFFLINE_ENV = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1"}

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class OptionalSingingEngineNotInstalled(SingingConversionError):
    """The optional RVC install is not present; the default install is unaffected."""


class EngineInvocationError(SingingConversionError):
    """RVC ran but failed or timed out."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RvcSingingEngine:
    id = RVC_ENGINE_ID
    version = RVC_PINNED_VERSION
    singing_capabilities = frozenset({"singing_conversion", "pitch_conditioning"})

    def __init__(self, rvc_dir: str | os.PathLike | None = None, *, python: str | None = None,
                 runner: Runner | None = None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        configured = rvc_dir if rvc_dir is not None else os.environ.get(RVC_DIR_ENV, "")
        self.rvc_dir = Path(configured) if configured else None
        self.python = python or os.environ.get("VOICESTUDIO_RVC_PYTHON") or sys.executable
        self.runner = runner or subprocess.run
        self.timeout_seconds = timeout_seconds

    def _cli(self) -> Path:
        cli = self.rvc_dir / "infer" / "cli.py" if self.rvc_dir else None
        if cli is None or not cli.is_file():
            raise OptionalSingingEngineNotInstalled(
                f"optional singing engine not installed: RVC {RVC_PINNED_VERSION} was not found "
                f"(set {RVC_DIR_ENV} to an RVC checkout containing infer/cli.py)")
        return cli

    def convert(self, guide_vocal: Path, target_voice: str, output: Path, f0_track) -> EngineOutput:
        cli = self._cli()
        model = Path(target_voice)
        if not model.is_file() or model.suffix.lower() != ".pth":
            raise InvalidConversionRequest("target_voice must be the path to an existing RVC .pth model")
        input_hash, model_hash = sha256_file(guide_vocal), sha256_file(model)
        # The guide vocal's own F0 track is not passed: RVC's CLI selects its pitch method internally (pitch shift 0).
        command = [self.python, str(cli), "--model", str(model), "--input", str(guide_vocal),
                   "--output", str(output), "--pitch", "0"]
        env = {**os.environ, **_OFFLINE_ENV}
        try:
            completed = self.runner(command, cwd=str(self.rvc_dir), env=env, capture_output=True, text=True,
                                    timeout=self.timeout_seconds, check=False, shell=False)
        except subprocess.TimeoutExpired as exc:
            raise EngineInvocationError(f"RVC timed out after {self.timeout_seconds:.0f}s") from exc
        except OSError as exc:
            raise EngineInvocationError(f"RVC could not be started: {exc}") from exc
        if completed.returncode != 0:
            tail = (completed.stderr or "").strip()[-300:]
            raise EngineInvocationError(f"RVC exited with status {completed.returncode}: {tail}")
        if not output.is_file():
            raise EngineOutputError("RVC finished without writing its output file")
        seconds, rate = wav_duration_seconds(output, EngineOutputError)
        provenance = {
            "engine": self.id, "engine_version": self.version, "model": model.name, "model_sha256": model_hash,
            "input_sha256": input_hash, "output_sha256": sha256_file(output), "network_access": False,
        }
        return EngineOutput(rate, seconds, provenance)
