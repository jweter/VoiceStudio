from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "engineering" / "learning-memory.json"
SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(password|api[_-]?key|secret|token)\s*[:=]\s*[^\s]+"),
]


def load_memory() -> dict[str, Any]:
    payload = json.loads(MEMORY.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("events"), list):
        raise ValueError("learning-memory.json must be schema_version 1 with an events list")
    return payload


def _contains_secret(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True)
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def add_event(
    *,
    event_type: str,
    summary: str,
    root_cause: str,
    successful_pattern: str,
    verification: str,
    residual_risk: str,
    source_ref: str,
) -> str:
    fields = {
        "type": event_type.strip(),
        "repository": "jweter/VoiceStudio",
        "summary": summary.strip(),
        "root_cause": root_cause.strip(),
        "successful_pattern": successful_pattern.strip(),
        "verification": verification.strip(),
        "residual_risk": residual_risk.strip(),
        "source_ref": source_ref.strip(),
        "evidence_state": "VERIFIED",
    }
    if any(not value for value in fields.values()):
        raise ValueError("all verified learning fields are required")
    if _contains_secret(fields):
        raise ValueError("learning event appears to contain secret material")
    fingerprint = hashlib.sha256(
        json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    memory = load_memory()
    if any(event.get("fingerprint") == fingerprint for event in memory["events"]):
        return fingerprint
    event = {**fields, "fingerprint": fingerprint, "recorded_at": datetime.now(UTC).isoformat()}
    memory["events"].append(event)
    MEMORY.write_text(json.dumps(memory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return fingerprint


def validate() -> int:
    memory = load_memory()
    seen: set[str] = set()
    for event in memory["events"]:
        if not isinstance(event, dict):
            raise ValueError("learning event must be an object")
        if event.get("evidence_state") != "VERIFIED":
            raise ValueError("VoiceStudio persists only VERIFIED learning events")
        if not isinstance(event.get("verification"), str) or not event["verification"].strip():
            raise ValueError("verified learning event requires verification evidence")
        if _contains_secret(event):
            raise ValueError("learning event appears to contain secret material")
        fingerprint = event.get("fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise ValueError("learning event requires fingerprint")
        if fingerprint in seen:
            raise ValueError("duplicate learning fingerprint")
        seen.add(fingerprint)
    print(f"VOICESTUDIO LEARNING MEMORY: PASS ({len(memory['events'])} verified events)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    record = sub.add_parser("record")
    for name in ("type", "summary", "root-cause", "successful-pattern", "verification", "residual-risk", "source-ref"):
        record.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    if args.command == "validate":
        return validate()
    print(add_event(
        event_type=args.type,
        summary=args.summary,
        root_cause=args.root_cause,
        successful_pattern=args.successful_pattern,
        verification=args.verification,
        residual_risk=args.residual_risk,
        source_ref=args.source_ref,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
