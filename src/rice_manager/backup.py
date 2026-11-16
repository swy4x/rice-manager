"""Create safe, non-destructive snapshots of user-scoped profile components."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .manifest import Manifest, ManifestError, resolve_source


class BackupError(RuntimeError):
    """Raised when a profile backup cannot be completed safely."""


def _kind(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "config-directory"
    if path.is_file():
        return "config-file"
    return "missing"


def _overlaps(first: Path, second: Path) -> bool:
    first = first.resolve(strict=False)
    second = second.resolve(strict=False)
    return first == second or first in second.parents or second in first.parents


def create_backup(manifest: Manifest, backup_root: str | Path | None = None) -> Path:
    """Snapshot eligible user components into a new, uniquely named directory.

    System-scoped and explicitly read-only components are never copied.
    Existing backups are never overwritten. The backup is published only after
    every selected component and the metadata file have been copied successfully.
    """
    root = Path(backup_root).expanduser() if backup_root else (
        Path.home() / ".local" / "share" / "rice-manager" / "backups"
    )
    root = root.absolute()

    selected = [
        component for component in manifest.components
        if component.scope == "user" and not component.read_only
    ]
    if not selected:
        raise BackupError("This profile has no writable user components to back up.")

    sources: list[tuple[object, Path, str]] = []
    for component in selected:
        source = resolve_source(component.source)
        actual_kind = _kind(source)
        if actual_kind == "missing":
            if component.required:
                raise BackupError(f"Required component is missing: {component.name} ({source})")
            continue
        expected = component.kind
        if actual_kind != expected:
            raise BackupError(
                f"Component type mismatch for {component.name}: "
                f"expected {expected}, found {actual_kind}."
            )
        if _overlaps(source, root):
            raise BackupError(
                f"Backup destination overlaps source component {component.name}; choose another location."
            )
        sources.append((component, source, actual_kind))

    if not sources:
        raise BackupError("No existing user components were found to back up.")

    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{manifest.id}-staging-", dir=root))
    try:
        entries = []
        for component, source, actual_kind in sources:
            destination = staging / "components" / component.id
            destination.parent.mkdir(parents=True, exist_ok=True)
            if actual_kind == "symlink":
                os.symlink(os.readlink(source), destination)
            elif actual_kind == "config-directory":
                shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)
            else:
                shutil.copy2(source, destination, follow_symlinks=False)
            entries.append({
                "component_id": component.id,
                "name": component.name,
                "source": str(source),
                "backup_path": str(Path("components") / component.id),
                "kind": actual_kind,
            })

        metadata = {
            "schema_version": 1,
            "profile_id": manifest.id,
            "profile_name": manifest.name,
            "profile_version": manifest.version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "components": entries,
            "restore_supported": False,
        }
        (staging / "backup.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        final = root / f"{manifest.id}-{timestamp}"
        suffix = 1
        while final.exists():
            final = root / f"{manifest.id}-{timestamp}-{suffix}"
            suffix += 1
        staging.rename(final)
        return final
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
