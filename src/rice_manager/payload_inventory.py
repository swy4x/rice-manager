"""Read-only file-level comparison of profile payloads and destinations."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from .manifest import Manifest, ManifestError, resolve_source


class PayloadInventoryError(ValueError):
    """Raised when a profile payload cannot be inspected safely."""


def _safe_payload_path(profile_root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    candidate = profile_root
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise PayloadInventoryError(f"Payload path contains a symlink: {candidate}")
    try:
        candidate.resolve(strict=True).relative_to(profile_root)
    except (OSError, ValueError) as exc:
        raise PayloadInventoryError(f"Payload path is missing or escapes the profile: {relative}") from exc
    return candidate


def _payload_files(path: Path, kind: str) -> list[tuple[str, bytes]]:
    if kind == "config-file":
        if not path.is_file():
            raise PayloadInventoryError("File component payload must be a regular file.")
        return [(path.name, path.read_bytes())]
    if not path.is_dir():
        raise PayloadInventoryError("Directory component payload must be a directory.")

    files: list[tuple[str, bytes]] = []
    for current, dirs, names in os.walk(path, followlinks=False):
        current_path = Path(current)
        for name in list(dirs):
            child = current_path / name
            if child.is_symlink() or not child.is_dir():
                raise PayloadInventoryError(f"Payload contains an unsafe directory entry: {child}")
        for name in names:
            child = current_path / name
            if child.is_symlink() or not child.is_file():
                raise PayloadInventoryError(f"Payload contains an unsafe file entry: {child}")
            files.append((child.relative_to(path).as_posix(), child.read_bytes()))
    return sorted(files)


def _contains_symlink(path: Path, stop: Path) -> bool:
    try:
        relative = path.relative_to(stop)
    except ValueError:
        return True
    current = stop
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _destination_action(target: Path, payload: bytes, destination_root: Path) -> tuple[str, str]:
    if _contains_symlink(target.parent, destination_root):
        return "CONFLICT", "A destination parent is a symlink; it will not be followed."
    if target.is_symlink():
        return "CONFLICT", "Destination entry is a symlink; it will not be followed."
    if not target.exists():
        return "ADD", "File does not exist at the destination."
    if not target.is_file():
        return "CONFLICT", "Destination entry exists but is not a regular file."
    if target.read_bytes() == payload:
        return "UNCHANGED", "Destination file already matches the payload."
    return "REPLACE", "Destination file differs from the payload; replacement would be required."


def build_payload_inventory(manifest: Manifest, profile_directory: str | Path) -> dict:
    """Compare declared payload files with destinations; never write or delete files."""
    root_input = Path(profile_directory).expanduser()
    if root_input.is_symlink() or not root_input.is_dir():
        raise PayloadInventoryError("Profile directory must be a real directory.")
    root = root_input.resolve(strict=True)
    home = Path.home().resolve()
    components: list[dict] = []

    for component in manifest.components:
        base = {
            "component_id": component.id,
            "name": component.name,
            "destination": str(resolve_source(component.source)),
            "files": [],
        }
        if component.scope == "system" or component.read_only:
            components.append({**base, "status": "SKIPPED_PROTECTED",
                               "detail": "System-scoped or read-only component is never inventoried for writing."})
            continue
        if component.payload is None:
            components.append({**base, "status": "NO_PAYLOAD",
                               "detail": "No payload is declared; existing profile remains compatible."})
            continue

        try:
            payload_path = _safe_payload_path(root, component.payload)
            payload_files = _payload_files(payload_path, component.kind)
            destination = resolve_source(component.source)
            if _contains_symlink(destination, home):
                raise PayloadInventoryError("Destination path contains a symlink.")
            resolved_destination = destination.resolve(strict=False)
            try:
                resolved_destination.relative_to(home)
            except ValueError as exc:
                raise PayloadInventoryError("Writable destination is outside the home directory.") from exc

            if destination.exists():
                expected_directory = component.kind == "config-directory"
                if destination.is_dir() != expected_directory or destination.is_file() == expected_directory:
                    raise PayloadInventoryError("Destination type does not match the component kind.")

            for relative, data in payload_files:
                target = destination / relative if component.kind == "config-directory" else destination
                action, detail = _destination_action(target, data, destination)
                base["files"].append({
                    "path": relative,
                    "destination": str(target),
                    "action": action,
                    "detail": detail,
                })
            actions = {item["action"] for item in base["files"]}
            if "CONFLICT" in actions:
                status = "CONFLICT"
            elif "REPLACE" in actions:
                status = "CHANGES_REQUIRED"
            elif "ADD" in actions:
                status = "CHANGES_REQUIRED"
            else:
                status = "UNCHANGED"
            components.append({**base, "status": status,
                               "detail": "File comparison only; no destination was changed."})
        except (OSError, ManifestError, PayloadInventoryError) as exc:
            components.append({**base, "status": "BLOCKED", "detail": str(exc)})

    counts = {
        action: sum(file["action"] == action for component in components for file in component["files"])
        for action in ("ADD", "REPLACE", "UNCHANGED", "CONFLICT")
    }
    return {
        "schema_version": 1,
        "profile": {"id": manifest.id, "name": manifest.name},
        "components": components,
        "summary": counts,
        "dry_run": True,
    }
