"""Persistent, engine-neutral data model for Singing Mode projects."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

SingingMode = Literal["conversion", "synthesis"]
SCHEMA_VERSION = 1

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

@dataclass(frozen=True)
class SingingSource:
    path: str
    sha256: str
    role: Literal["guide_vocal", "target_voice", "melody", "lyrics"]

    @classmethod
    def from_file(cls, path: Path, role: str) -> "SingingSource":
        if not path.is_file():
            raise ValueError(f"{role} must be an existing file")
        return cls(path=str(path), sha256=sha256_file(path), role=role)  # type: ignore[arg-type]

@dataclass
class SingingProject:
    project_id: str
    mode: SingingMode
    sources: list[SingingSource]
    schema_version: int = SCHEMA_VERSION
    analysis: dict[str, Any] = field(default_factory=dict)
    renders: list[dict[str, Any]] = field(default_factory=list)

    def validate(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id must not be empty")
        roles = [source.role for source in self.sources]
        required = {"target_voice"}
        required.add("guide_vocal" if self.mode == "conversion" else "melody")
        missing = required.difference(roles)
        if missing:
            raise ValueError(f"missing required singing sources: {sorted(missing)}")
        if len(roles) != len(set(roles)):
            raise ValueError("singing source roles must be unique")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SingingProject":
        if value.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported singing project schema_version")
        project = cls(
            project_id=value["project_id"],
            mode=value["mode"],
            sources=[SingingSource(**source) for source in value.get("sources", [])],
            schema_version=value["schema_version"],
            analysis=dict(value.get("analysis", {})),
            renders=list(value.get("renders", [])),
        )
        project.validate()
        return project

def save_project(project: SingingProject, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(project.to_dict(), indent=2, sort_keys=True) + "
"
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(path)

def load_project(path: Path) -> SingingProject:
    return SingingProject.from_dict(json.loads(path.read_text(encoding="utf-8")))
