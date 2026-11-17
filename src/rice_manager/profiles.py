"""Read-only discovery of profile manifests in a directory."""

from __future__ import annotations

from pathlib import Path

from .manifest import ManifestError, load_manifest
from .planner import build_switch_plan


class ProfileDiscoveryError(ValueError):
    """Raised when a profile directory cannot be inspected."""


def discover_profiles(directory: str | Path) -> list[dict]:
    """Discover immediate child directories containing manifest.json files."""
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise ProfileDiscoveryError(f"Profile directory does not exist or is not a directory: {root}")

    discovered: list[dict] = []
    try:
        entries = sorted(root.iterdir(), key=lambda item: item.name.casefold())
    except OSError as exc:
        raise ProfileDiscoveryError(f"Cannot read profile directory: {exc}") from exc

    for entry in entries:
        if entry.is_symlink() or not entry.is_dir():
            continue
        manifest_path = entry / "manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            continue

        try:
            manifest = load_manifest(manifest_path)
            plan = build_switch_plan(manifest)
            discovered.append({
                "valid": True,
                "id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "manifest": str(manifest_path),
                "component_count": len(manifest.components),
                "summary": {
                    "ready": plan.ready_count,
                    "skipped": plan.skipped_count,
                    "blocked": sum(item.status.startswith("blocked-") for item in plan.items),
                },
                "blocked": plan.blocked,
            })
        except ManifestError as exc:
            discovered.append({
                "valid": False,
                "directory": entry.name,
                "manifest": str(manifest_path),
                "error": str(exc),
            })

    return discovered
