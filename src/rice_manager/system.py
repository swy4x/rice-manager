"""Read-only discovery of desktop configuration locations."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Any


def _config_home() -> Path:
    """Use XDG_CONFIG_HOME when it is an absolute path, otherwise the default."""
    fallback = Path.home() / ".config"
    configured = os.environ.get("XDG_CONFIG_HOME")
    if not configured:
        return fallback
    candidate = Path(configured).expanduser()
    return candidate if candidate.is_absolute() else fallback


def inspect_path(label: str, path: Path) -> dict[str, Any]:
    """Describe a path without reading or changing its contents."""
    expanded = path.expanduser()
    result: dict[str, Any] = {
        "label": label,
        "path": str(expanded),
        "exists": expanded.exists() or expanded.is_symlink(),
        "kind": "missing",
        "symlink_target": None,
    }

    if expanded.is_symlink():
        result["kind"] = "symlink"
        try:
            result["symlink_target"] = str(expanded.resolve(strict=False))
        except OSError:
            result["symlink_target"] = "unresolvable"
    elif expanded.is_dir():
        result["kind"] = "directory"
    elif expanded.is_file():
        result["kind"] = "file"

    return result


def inspect_system() -> dict[str, Any]:
    """Collect a conservative, read-only summary of the current system."""
    home = Path.home()
    config = _config_home()

    candidates = [
        ("Hyprland user config", config / "hypr"),
        ("Quickshell user config", config / "quickshell"),
        ("Waybar user config", config / "waybar"),
        ("System Caelestia config", Path("/etc/xdg/quickshell/caelestia")),
        ("XDG config directory", config),
    ]

    tools = ("hyprctl", "qs", "quickshell", "git", "python")
    return {
        "platform": platform.platform(),
        "home": str(home),
        "config_home": str(config),
        "python": platform.python_version(),
        "tools": {name: shutil.which(name) for name in tools},
        "paths": [inspect_path(label, path) for label, path in candidates],
    }
