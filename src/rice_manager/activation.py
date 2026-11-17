"""Explicit, transactional installation of profile payload files."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .manifest import Manifest, ManifestError, resolve_source
from .payload_inventory import (
    PayloadInventoryError,
    _payload_files,
    _safe_payload_path,
    build_payload_inventory,
)


class ActivationError(RuntimeError):
    """Raised when a profile payload cannot be installed safely."""


def _has_symlink(path: Path, home: Path) -> bool:
    try:
        relative = path.relative_to(home)
    except ValueError:
        return True
    current = home
    for part in relative.parts:
        if part in {"", ".", ".."}:
            return True
        current = current / part
        if current.is_symlink():
            return True
    return False


def _remove_empty_directories(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            path.rmdir()
        except OSError:
            pass


def apply_profile_payload(
    manifest: Manifest,
    profile_directory: str | Path,
    *,
    apply: bool = False,
    backup_root: str | Path | None = None,
) -> dict:
    """Preview or transactionally install declared payload files.

    Only user-scoped, writable payload files are eligible. Existing files are
    snapshotted before replacement. Extra destination files are never removed.
    The operation requires apply=True; the default is a read-only preview.
    """
    profile_input = Path(profile_directory).expanduser()
    if profile_input.is_symlink() or not profile_input.is_dir():
        raise ActivationError("Profile directory must be a real directory.")
    profile_root = profile_input.resolve(strict=True)

    try:
        inventory = build_payload_inventory(manifest, profile_root)
    except (PayloadInventoryError, ManifestError, OSError) as exc:
        raise ActivationError(str(exc)) from exc

    blocked = [
        component for component in inventory["components"]
        if component["status"] in {"BLOCKED", "CONFLICT"}
    ]
    if blocked:
        names = ", ".join(item["name"] for item in blocked)
        raise ActivationError(
            f"Preview contains blocked or conflicting components ({names}); no files were changed."
        )

    home = Path.home().resolve()
    operations: list[dict] = []
    for component, result in zip(manifest.components, inventory["components"]):
        if result["status"] in {"SKIPPED_PROTECTED", "NO_PAYLOAD", "UNCHANGED"}:
            continue
        payload_root = _safe_payload_path(profile_root, component.payload)
        for item in result["files"]:
            if item["action"] == "UNCHANGED":
                continue
            relative = Path(item["path"])
            source = payload_root if component.kind == "config-file" else payload_root / relative
            target = Path(item["destination"])
            if source.is_symlink() or not source.is_file():
                raise ActivationError(f"Payload file is missing or unsafe: {source}")
            if _has_symlink(target, home):
                raise ActivationError(f"Destination path contains a symlink or escapes home: {target}")
            resolved_target = target.resolve(strict=False)
            try:
                resolved_target.relative_to(home)
            except ValueError as exc:
                raise ActivationError(f"Destination is outside home: {target}") from exc
            if target.exists() and not target.is_file():
                raise ActivationError(f"Destination is not a regular file: {target}")
            operations.append({
                "component_id": component.id,
                "component_name": component.name,
                "relative_path": relative.as_posix(),
                "source": source,
                "target": target,
                "action": item["action"],
            })

    targets = [item["target"] for item in operations]
    if len(set(targets)) != len(targets):
        raise ActivationError("Multiple payload entries resolve to the same destination.")
    report = {
        "schema_version": 1,
        "profile": {"id": manifest.id, "name": manifest.name},
        "files": [
            {
                "component_id": item["component_id"],
                "component": item["component_name"],
                "path": item["relative_path"],
                "destination": str(item["target"]),
                "action": item["action"],
            }
            for item in operations
        ],
        "summary": {
            "ADD": sum(item["action"] == "ADD" for item in operations),
            "REPLACE": sum(item["action"] == "REPLACE" for item in operations),
            "UNCHANGED": inventory["summary"]["UNCHANGED"],
        },
        "dry_run": not apply,
    }
    if not apply or not operations:
        return report

    safety_root = Path(backup_root).expanduser() if backup_root else (
        home / ".local" / "share" / "rice-manager" / "backups"
    )
    safety_root = safety_root.absolute()
    try:
        safety_root.relative_to(home)
    except ValueError as exc:
        raise ActivationError("Safety backup directory must be inside home.") from exc
    if _has_symlink(safety_root, home):
        raise ActivationError("Safety backup directory contains a symlink.")
    for target in targets:
        if target == safety_root or safety_root in target.parents or target in safety_root.parents:
            raise ActivationError("A destination overlaps the safety backup directory.")

    # Revalidate every destination immediately before preparing the transaction.
    for target in targets:
        if _has_symlink(target, home):
            raise ActivationError(f"Destination path contains a symlink: {target}")
        parent = target.parent
        if parent.exists() and not parent.is_dir():
            raise ActivationError(f"Destination parent is not a directory: {parent}")
        if target.exists() and not target.is_file():
            raise ActivationError(f"Destination is not a regular file: {target}")

    created_directories: list[Path] = []
    staged_files: list[tuple[Path, Path]] = []
    installed: list[dict] = []
    safety_directory: Path | None = None
    try:
        # Create missing destination parents while recording them for cleanup.
        for target in targets:
            missing: list[Path] = []
            current = target.parent
            while not current.exists():
                missing.append(current)
                current = current.parent
            for directory in reversed(missing):
                if directory.is_symlink() or not directory.parent.is_dir():
                    raise ActivationError(f"Unsafe destination parent: {directory}")
                directory.mkdir()
                created_directories.append(directory)

        safety_root.mkdir(parents=True, exist_ok=True)
        if safety_root.is_symlink() or not safety_root.is_dir():
            raise ActivationError("Safety backup directory is not a real directory.")
        safety_directory = Path(tempfile.mkdtemp(
            prefix=f"pre-apply-{manifest.id}-", dir=safety_root
        ))

        saved_components: list[dict] = []
        original_states: list[dict] = []
        for index, item in enumerate(operations):
            target = item["target"]
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ActivationError(f"Destination changed during apply preparation: {target}")
            if target.exists():
                before = target.stat(follow_symlinks=False)
                saved_path = safety_directory / "components" / item["component_id"] / f"{index}-{target.name}"
                saved_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved_path, follow_symlinks=False)
                after = target.stat(follow_symlinks=False)
                before_signature = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                after_signature = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                if before_signature != after_signature:
                    raise ActivationError(f"Destination changed while it was being backed up: {target}")
                original_states.append({
                    "existed": True,
                    "signature": before_signature,
                    "backup": saved_path,
                })
                saved_components.append({
                    "component_id": item["component_id"],
                    "component": item["component_name"],
                    "destination": str(target),
                    "backup_path": str(saved_path.relative_to(safety_directory)),
                })
            else:
                original_states.append({"existed": False, "signature": None, "backup": None})

        metadata = {
            "schema_version": 1,
            "profile_id": manifest.id,
            "profile_name": manifest.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "components": saved_components,
            "note": "File-level pre-apply safety snapshot; extra destination files were not changed.",
        }
        (safety_directory / "apply-safety.json").write_text(
            json.dumps(metadata, indent=2) + "\\n", encoding="utf-8"
        )

        # Stage every payload file beside its destination so os.replace is atomic.
        for item in operations:
            source = item["source"]
            if source.is_symlink() or not source.is_file():
                raise ActivationError(f"Payload changed during apply preparation: {source}")
            target = item["target"]
            fd, temp_name = tempfile.mkstemp(prefix=".rice-manager-stage-", dir=target.parent)
            os.close(fd)
            staged = Path(temp_name)
            try:
                shutil.copy2(source, staged, follow_symlinks=False)
            except Exception:
                staged.unlink(missing_ok=True)
                raise
            staged_files.append((staged, target))

        for index, (staged, target) in enumerate(staged_files):
            original = original_states[index]
            if target.is_symlink():
                raise ActivationError(f"Destination changed during installation: {target}")
            currently_exists = target.exists()
            if currently_exists != original["existed"]:
                raise ActivationError(f"Destination changed during installation: {target}")
            if currently_exists:
                current = target.stat(follow_symlinks=False)
                signature = (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                if signature != original["signature"]:
                    raise ActivationError(f"Destination changed during installation: {target}")
            os.replace(staged, target)
            installed_stat = target.stat(follow_symlinks=False)
            installed.append({
                "target": target,
                "existed": original["existed"],
                "backup": original["backup"],
                "installed_signature": (
                    installed_stat.st_dev, installed_stat.st_ino,
                    installed_stat.st_size, installed_stat.st_mtime_ns,
                ),
            })

        report["dry_run"] = False
        report["safety_backup"] = str(safety_directory)
        report["message"] = "Payload installed. Existing files were snapshotted; extra files were left untouched."
        return report
    except Exception as exc:
        rollback_errors: list[str] = []
        for item in reversed(installed):
            target = item["target"]
            try:
                if target.is_symlink():
                    raise OSError("destination became a symlink during rollback")
                if target.exists():
                    current = target.stat(follow_symlinks=False)
                    signature = (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                    if signature != item["installed_signature"]:
                        raise OSError("destination changed after installation; refusing to overwrite it")
                if item["existed"] and item["backup"] is not None:
                    fd, temp_name = tempfile.mkstemp(prefix=".rice-manager-rollback-", dir=target.parent)
                    os.close(fd)
                    rollback_stage = Path(temp_name)
                    try:
                        shutil.copy2(item["backup"], rollback_stage, follow_symlinks=False)
                        os.replace(rollback_stage, target)
                    finally:
                        rollback_stage.unlink(missing_ok=True)
                elif target.exists():
                    target.unlink()
            except Exception as rollback_exc:
                rollback_errors.append(f"{target}: {rollback_exc}")
        for staged, _ in staged_files:
            staged.unlink(missing_ok=True)
        _remove_empty_directories(created_directories)
        if rollback_errors:
            raise ActivationError(
                f"Apply failed ({exc}); rollback was incomplete. Safety snapshot retained at "
                f"{safety_directory}. " + "; ".join(rollback_errors)
            ) from exc
        raise ActivationError(
            f"Apply failed and changes were rolled back: {exc}. "
            f"Safety snapshot retained at {safety_directory}."
        ) from exc
    finally:
        for staged, _ in staged_files:
            staged.unlink(missing_ok=True)
