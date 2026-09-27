#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_URL = "http://localhost:3912"
SMOKES = (
    "electron/tests/playback-smoke.mjs",
    "electron/tests/dub-smoke.mjs",
    "electron/tests/longform-layout-smoke.mjs",
)


def _stop_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def _wait_ready(log_path: Path) -> None:
    deadline = time.monotonic() + 20.0
    last_error = "not started"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(UI_URL, timeout=1.0) as response:
                if 200 <= response.status < 500:
                    return
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(0.25)
    tail = ""
    if log_path.exists():
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-5000:]
    raise RuntimeError(f"renderer smoke server did not become ready ({last_error})\n{tail}")


def main() -> int:
    env = os.environ.copy()
    env["OMNIVOICE_PORT"] = "3999"
    env["VOICESTUDIO_UI_URL"] = UI_URL
    env["PLAYWRIGHT_CHANNEL"] = "chromium"
    env["HF_HUB_OFFLINE"] = "1"
    with tempfile.TemporaryDirectory(prefix="voicestudio-renderer-smoke-") as temp:
        log_path = Path(temp) / "server.log"
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        with log_path.open("wb") as log:
            server = subprocess.Popen(
                ["bun", "run", "--cwd", "electron", "smoke:server"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                **kwargs,
            )
        try:
            _wait_ready(log_path)
            for script in SMOKES:
                result = subprocess.run(
                    ["node", script],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if result.returncode:
                    sys.stderr.write(result.stdout[-5000:])
                    sys.stderr.write(result.stderr[-5000:])
                    return result.returncode
        finally:
            _stop_tree(server)
    print("RENDERER SMOKES: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
