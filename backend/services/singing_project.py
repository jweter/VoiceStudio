from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import PurePosixPath

SINGING_PROJECT_SCHEMA_VERSION = 1
_ALLOWED_SOURCE_KINDS = {"guide_vocal", "original_mix"}
_WINDOWS_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{prefix}{digit}" for prefix in ("COM", "LPT") for digit in "123456789¹²³"}
)
_WINDOWS_FORBIDDEN_CHARS = frozenset('\\:<>"|?*')


def _safe_relative_path(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    # Persist only canonical POSIX-relative paths safe on Windows as well.
    # PurePosixPath alone accepts drive-relative paths, NTFS streams and devices.
    parts = value.split("/")
    if (
        PurePosixPath(value).is_absolute()
        or any(ord(char) < 32 or char in _WINDOWS_FORBIDDEN_CHARS for char in value)
        or any(
            not part
            or part in {".", ".."}
            or part.endswith((" ", "."))
            or part.split(".", 1)[0].upper() in _WINDOWS_DEVICE_NAMES
            for part in parts
        )
    ):
        raise ValueError(f"{name} must be a safe project-relative POSIX path")
    return value


@dataclass(frozen=True)
class SingingSource:
    kind: str
    path: str
    sha256: str
    sample_rate: int
    channels: int
    duration_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or self.kind not in _ALLOWED_SOURCE_KINDS:
            raise ValueError("unsupported singing source kind")
        _safe_relative_path("path", self.path)
        if (
            not isinstance(self.sha256, str)
            or len(self.sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.sha256)
        ):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        if type(self.sample_rate) is not int or self.sample_rate <= 0:
            raise ValueError("sample_rate must be a positive integer")
        if type(self.channels) is not int or self.channels <= 0:
            raise ValueError("channels must be a positive integer")
        if isinstance(self.duration_seconds, bool) or not isinstance(
            self.duration_seconds, (int, float)
        ):
            raise ValueError("duration_seconds must be positive and finite")
        try:
            finite = math.isfinite(float(self.duration_seconds))
        except OverflowError:
            finite = False
        if not finite or self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive and finite")


@dataclass(frozen=True)
class SingingProject:
    project_id: str
    source: SingingSource
    target_voice_id: str
    lyrics: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.project_id, str) or not self.project_id.strip():
            raise ValueError("project_id must be a non-empty string")
        if (
            not isinstance(self.target_voice_id, str)
            or not self.target_voice_id.strip()
        ):
            raise ValueError("target_voice_id must be a non-empty string")
        if self.lyrics is not None and not isinstance(self.lyrics, str):
            raise ValueError("lyrics must be a string or null")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SINGING_PROJECT_SCHEMA_VERSION,
            "project_id": self.project_id,
            "source": asdict(self.source),
            "target_voice_id": self.target_voice_id,
            "lyrics": self.lyrics,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"

    @classmethod
    def from_json(cls, raw: str) -> "SingingProject":
        """Parse persisted project metadata without silent provenance overrides."""
        if not isinstance(raw, str):
            raise ValueError("singing project JSON must be a string")

        def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate singing project JSON key")
                result[key] = value
            return result

        def reject_constant(value: str) -> None:
            raise ValueError("nonstandard singing project JSON number")

        try:
            payload = json.loads(
                raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant
            )
        except json.JSONDecodeError as exc:
            raise ValueError("invalid singing project JSON") from exc
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: object) -> "SingingProject":
        if not isinstance(payload, dict):
            raise ValueError("singing project must be a JSON object")
        expected = {
            "schema_version",
            "project_id",
            "source",
            "target_voice_id",
            "lyrics",
        }
        if set(payload) != expected:
            raise ValueError("singing project contains missing or unsupported fields")
        if (
            type(payload["schema_version"]) is not int
            or payload["schema_version"] != SINGING_PROJECT_SCHEMA_VERSION
        ):
            raise ValueError("unsupported singing project schema version")
        raw_source = payload["source"]
        if not isinstance(raw_source, dict) or set(raw_source) != {
            "kind",
            "path",
            "sha256",
            "sample_rate",
            "channels",
            "duration_seconds",
        }:
            raise ValueError("invalid singing source")
        source = SingingSource(**raw_source)
        project_id = payload["project_id"]
        target_voice_id = payload["target_voice_id"]
        lyrics = payload["lyrics"]
        if not isinstance(project_id, str) or not isinstance(target_voice_id, str):
            raise ValueError("project_id and target_voice_id must be strings")
        if lyrics is not None and not isinstance(lyrics, str):
            raise ValueError("lyrics must be a string or null")
        return cls(project_id, source, target_voice_id, lyrics)
