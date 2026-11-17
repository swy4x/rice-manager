"""Preview-first import of local profile directories into the private library."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .manifest import ManifestError, load_manifest


class ProfileImportError(RuntimeError):
    """Raised when a profile cannot be imported safely."""


def _inventory(source: Path) -> list[dict[str, int | str]]:
    if source.is_symlink() or not source.is_dir():
        raise ProfileImportError("Import source must be a real directory, not a symlink.")
    manifest_path = source / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ProfileImportError("Import source must contain a regular manifest.json file.")

    entries: list[dict[str, int | str]] = []
    for path in sorted(source.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink():
            raise ProfileImportError(f"Symlinks are not allowed in imported profiles: {path.relative_to(source)}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ProfileImportError(f"Unsupported filesystem entry: {path.relative_to(source)}")
        entries.append({"path": path.relative_to(source).as_posix(), "size": path.stat().st_size})
    return entries


def preview_profile_import(source: str | Path, library: str | Path | None = None) -> dict:
    """Validate and inventory a profile without writing any files."""
    source_path = Path(source).expanduser().absolute()
    try:
        files = _inventory(source_path)
        manifest = load_manifest(source_path / "manifest.json")
    except ManifestError as exc:
        raise ProfileImportError(str(exc)) from exc

    library_path = Path(library).expanduser() if library else (
        Path.home() / ".local" / "share" / "rice-manager" / "profiles"
    )
    library_path = library_path.absolute()
    if source_path == library_path or source_path in library_path.parents or library_path in source_path.parents:
        raise ProfileImportError("Import source and profile library must not contain one another.")
    destination = library_path / manifest.id
    if destination.exists() or destination.is_symlink():
        raise ProfileImportError(f"Profile already exists in the library: {destination}")

    return {
        "profile_id": manifest.id,
        "profile_name": manifest.name,
        "source": str(source_path),
        "library": str(library_path),
        "destination": str(destination),
        "files": files,
        "file_count": len(files),
        "total_bytes": sum(int(item["size"]) for item in files),
        "dry_run": True,
    }


def import_profile(source: str | Path, library: str | Path | None = None) -> Path:
    """Copy a validated profile into the library, publishing it atomically."""
    plan = preview_profile_import(source, library)
    source_path = Path(plan["source"])
    library_path = Path(plan["library"])
    destination = Path(plan["destination"])
    library_path.mkdir(parents=True, exist_ok=True)
    if library_path.is_symlink() or not library_path.is_dir():
        raise ProfileImportError("Profile library must be a real directory.")

    staging = Path(tempfile.mkdtemp(prefix=f".{plan['profile_id']}-import-", dir=library_path))
    try:
        for item in plan["files"]:
            relative = Path(str(item["path"]))
            source_file = source_path / relative
            target_file = staging / relative
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file, follow_symlinks=False)
        if destination.exists() or destination.is_symlink():
            raise ProfileImportError(f"Profile already exists in the library: {destination}")
        staging.rename(destination)
        return destination
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def preview_profile_removal(
    profile_id: str,
    library: str | Path | None = None,
) -> dict:
    """Validate and describe one profile removal without changing files."""
    import re

    if not isinstance(profile_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", profile_id):
        raise ProfileImportError("Profile ID must contain lowercase letters, numbers, and hyphens.")

    library_path = Path(library).expanduser() if library else (
        Path.home() / ".local" / "share" / "rice-manager" / "profiles"
    )
    library_path = library_path.absolute()
    if library_path.is_symlink() or not library_path.is_dir():
        raise ProfileImportError("Profile library must be an existing real directory.")

    destination = library_path / profile_id
    if destination.is_symlink() or not destination.is_dir():
        raise ProfileImportError(f"Imported profile does not exist as a real directory: {destination}")

    manifest_path = destination / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ProfileImportError("Refusing to remove a library entry without a regular manifest.json.")

    try:
        manifest = load_manifest(manifest_path)
    except ManifestError as exc:
        raise ProfileImportError(f"Refusing to remove an invalid profile: {exc}") from exc
    if manifest.id != profile_id:
        raise ProfileImportError("Profile directory name does not match its manifest ID.")

    return {
        "profile_id": manifest.id,
        "profile_name": manifest.name,
        "destination": str(destination),
        "dry_run": True,
        "removed": False,
    }


def remove_imported_profile(
    profile_id: str,
    library: str | Path | None = None,
) -> Path:
    """Remove one validated profile directory from the private profile library."""
    plan = preview_profile_removal(profile_id, library)
    destination = Path(plan["destination"])
    try:
        shutil.rmtree(destination)
    except OSError as exc:
        raise ProfileImportError(f"Could not remove imported profile: {exc}") from exc
    return destination
