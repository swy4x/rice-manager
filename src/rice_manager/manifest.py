"""Load and validate portable rice profile manifests (read-only)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


class ManifestError(ValueError):
    """Raised when a rice profile manifest is invalid."""


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    kind: str
    source: str
    scope: str
    required: bool = False
    read_only: bool = False
    payload: str | None = None


@dataclass(frozen=True)
class Manifest:
    id: str
    name: str
    version: str
    description: str
    components: tuple[Component, ...]
    dependencies: tuple[str, ...] = ()


_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
_PACKAGE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9@._+-]*$")
_ALLOWED_VARS = {"HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"}


def _absolute_env(name: str, fallback: Path) -> Path:
    value = os.environ.get(name)
    candidate = Path(value).expanduser() if value else fallback
    return candidate if candidate.is_absolute() else fallback


def resolve_source(source: str) -> Path:
    """Expand only documented variables; never evaluate shell syntax."""
    home = Path.home()
    config_home = _absolute_env("XDG_CONFIG_HOME", home / ".config")
    data_home = _absolute_env("XDG_DATA_HOME", home / ".local" / "share")
    values = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(config_home),
        "XDG_DATA_HOME": str(data_home),
    }
    resolved = source
    for name, value in values.items():
        resolved = resolved.replace("${" + name + "}", value)
    if "${" in resolved or not Path(resolved).is_absolute():
        raise ManifestError(f"Unsupported variable or non-absolute source: {source}")
    return Path(resolved)


def load_manifest(path: str | Path) -> Manifest:
    """Read and strictly validate a JSON manifest without touching its sources."""
    manifest_path = Path(path).expanduser()
    try:
        raw: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"Cannot read manifest: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Invalid JSON at line {exc.lineno}: {exc.msg}") from exc

    if not isinstance(raw, dict):
        raise ManifestError("Manifest root must be a JSON object.")

    required_keys = {"schema_version", "id", "name", "version", "description", "components"}
    missing = required_keys - raw.keys()
    if missing:
        raise ManifestError(f"Missing manifest fields: {', '.join(sorted(missing))}")
    if raw["schema_version"] != 1:
        raise ManifestError("Unsupported schema_version; expected 1.")
    for key in ("id", "name", "version", "description"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ManifestError(f"'{key}' must be a non-empty string.")
    if not _ID.fullmatch(raw["id"]):
        raise ManifestError("'id' must be lowercase letters, numbers, and hyphens.")

    raw_dependencies = raw.get("dependencies", [])
    if not isinstance(raw_dependencies, list):
        raise ManifestError("'dependencies' must be an array of Arch package names.")
    dependencies: list[str] = []
    seen_dependencies: set[str] = set()
    for index, package in enumerate(raw_dependencies):
        if not isinstance(package, str) or not _PACKAGE_NAME.fullmatch(package):
            raise ManifestError(
                f"dependencies[{index}] must be a valid Arch package name."
            )
        if package in seen_dependencies:
            raise ManifestError(f"Duplicate package dependency: {package}")
        seen_dependencies.add(package)
        dependencies.append(package)

    entries = raw["components"]
    if not isinstance(entries, list) or not entries:
        raise ManifestError("'components' must be a non-empty array.")

    components: list[Component] = []
    seen: set[str] = set()
    allowed = {"id", "name", "kind", "source", "scope", "required", "read_only", "payload"}
    for index, item in enumerate(entries):
        prefix = f"components[{index}]"
        if not isinstance(item, dict):
            raise ManifestError(f"{prefix} must be an object.")
        unknown = item.keys() - allowed
        if unknown:
            raise ManifestError(f"{prefix} has unknown fields: {', '.join(sorted(unknown))}")
        for key in ("id", "name", "kind", "source", "scope"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ManifestError(f"{prefix}.{key} must be a non-empty string.")
        if not _ID.fullmatch(item["id"]) or item["id"] in seen:
            raise ManifestError(f"{prefix}.id is invalid or duplicated: {item['id']}")
        seen.add(item["id"])
        if item["kind"] not in {"config-directory", "config-file"}:
            raise ManifestError(f"{prefix}.kind must be config-directory or config-file.")
        if item["scope"] not in {"user", "system"}:
            raise ManifestError(f"{prefix}.scope must be user or system.")
        for flag in ("required", "read_only"):
            if flag in item and not isinstance(item[flag], bool):
                raise ManifestError(f"{prefix}.{flag} must be boolean.")
        resolve_source(item["source"])
        payload = item.get("payload")
        if payload is not None:
            if not isinstance(payload, str) or not payload.strip():
                raise ManifestError(f"{prefix}.payload must be a non-empty relative path.")
            payload_path = PurePosixPath(payload)
            raw_parts = payload.split("/")
            if (payload_path.is_absolute() or "\\" in payload or "\x00" in payload
                    or any(part in {"", ".", ".."} for part in raw_parts)):
                raise ManifestError(f"{prefix}.payload must be a safe relative POSIX path.")
        components.append(Component(
            id=item["id"],
            name=item["name"],
            kind=item["kind"],
            source=item["source"],
            scope=item["scope"],
            required=item.get("required", False),
            read_only=item.get("read_only", False),
            payload=payload,
        ))

    return Manifest(
        id=raw["id"],
        name=raw["name"],
        version=raw["version"],
        description=raw["description"],
        components=tuple(components),
        dependencies=tuple(dependencies),
    )
