#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "engineering" / "control-plane.json"
EVIDENCE = ROOT / "preflight-evidence.json"


def load_control() -> dict:
    payload = json.loads(CONTROL.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "repository",
        "authoritative_documents",
        "preflight",
    }
    if payload.get("schema_version") != 4 or not required <= payload.keys():
        raise ValueError("invalid control-plane contract")
    if payload.get("repository") != "jweter/VoiceStudio":
        raise ValueError("unexpected repository identity")
    docs = payload.get("authoritative_documents")
    if not isinstance(docs, list) or not docs:
        raise ValueError("authoritative_documents must be a non-empty list")
    missing = [item for item in docs if not (ROOT / item).exists()]
    if missing:
        raise ValueError(f"missing authoritative documents: {missing}")
    checks = payload.get("preflight", {}).get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("preflight checks must be declared")
    return payload


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def run_check(check: dict) -> dict:
    argv = check.get("argv")
    if not isinstance(argv, list) or not argv or any(
        not isinstance(part, str) or not part for part in argv
    ):
        raise ValueError(f"invalid argv for {check.get('id')}")
    executable = argv[0]
    if shutil.which(executable) is None:
        return {
            "id": check.get("id"),
            "argv": argv,
            "returncode": 127,
            "duration_seconds": 0.0,
            "stdout": "",
            "stderr": f"required executable not found: {executable}",
        }
    env = os.environ.copy()
    env.setdefault("HF_HUB_OFFLINE", "1")
    started = time.monotonic()
    result = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return {
        "id": check.get("id"),
        "argv": argv,
        "returncode": result.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout": result.stdout[-12000:],
        "stderr": result.stderr[-12000:],
    }


def write_evidence(status: str, head: str, results: list[dict]) -> None:
    EVIDENCE.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repository": "jweter/VoiceStudio",
                "head_sha": head,
                "status": status,
                "recorded_at_utc": datetime.now(UTC).isoformat(),
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()

    try:
        control = load_control()
    except Exception as exc:
        print(f"CONTROL PLANE: FAIL: {exc}", file=sys.stderr)
        return 1

    if args.self_check:
        print("CONTROL PLANE: PASS")
        return 0

    expected_head = git_head()
    if expected_head == "UNKNOWN":
        print("PREFLIGHT: FAIL: git head unavailable", file=sys.stderr)
        return 1

    results: list[dict] = []
    for check in control["preflight"]["checks"]:
        if check.get("id") == "control_plane":
            result = {
                "id": "control_plane",
                "argv": check["argv"],
                "returncode": 0,
                "duration_seconds": 0.0,
                "stdout": "CONTROL PLANE: PASS\n",
                "stderr": "",
            }
        else:
            result = run_check(check)
        results.append(result)

        observed_head = git_head()
        if observed_head != expected_head:
            results.append(
                {
                    "id": "exact_head_fence",
                    "argv": [],
                    "returncode": 125,
                    "duration_seconds": 0.0,
                    "stdout": "",
                    "stderr": (
                        f"HEAD_MOVED expected={expected_head} observed={observed_head}"
                    ),
                }
            )
            write_evidence("FAILED", expected_head, results)
            print("PREFLIGHT: FAIL: exact-head fence", file=sys.stderr)
            return 1

        if result["returncode"] != 0:
            write_evidence("FAILED", expected_head, results)
            print(f"PREFLIGHT: FAIL: {result['id']}", file=sys.stderr)
            if result["stdout"]:
                print(result["stdout"])
            if result["stderr"]:
                print(result["stderr"], file=sys.stderr)
            return 1

    write_evidence("GREEN", expected_head, results)
    print(f"PREFLIGHT: GREEN {expected_head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
