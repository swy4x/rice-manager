"""Read-only preview of shell deletion plans."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .shell_switch import ShellSwitchError, _running_shells, _shells


class ShellDeletionError(RuntimeError):
    pass


CAELESTIA_PACKAGES = (
    "caelestia-shell",
    "caelestia-cli",
    "caelestia-firefox-theme",
)


def preview_shell_deletion(shell_id: str) -> dict:
    """Describe a removal plan without changing anything."""
    try:
        shells = _shells()
        running = _running_shells()
    except ShellSwitchError as exc:
        raise ShellDeletionError(
            f"Cannot safely inspect shell status: {exc}"
        ) from exc

    if shell_id not in shells:
        raise ShellDeletionError(f"Unknown shell: {shell_id}")

    config = shells[shell_id]

    if running.get(shell_id):
        raise ShellDeletionError(
            f"{config['name']} is running. Switch to another shell first."
        )

    paths = []
    packages = []
    protected_packages = []

    if shell_id in {"cartoon-shell", "caelestia"}:
        shell_path = Path(config["path"]).parent
    else:
        config_home = Path(
            os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        ).expanduser().absolute()
        shell_path = config_home / "quickshell" / shell_id

    if shell_path.exists():
        paths.append(str(shell_path))

    if shell_id == "caelestia":
        protected_packages.append("quickshell-git")

        result = subprocess.run(
            ["pacman", "-Q", *CAELESTIA_PACKAGES],
            capture_output=True,
            text=True,
            check=False,
        )

        installed = {
            line.split()[0]
            for line in result.stdout.splitlines()
            if line.split()
        }

        packages = [
            name for name in CAELESTIA_PACKAGES if name in installed
        ]

    elif shell_id not in {"cartoon-shell", "caelestia"}:
        paths.append("Rice Manager installed-shell registry entry")

    return {
        "id": shell_id,
        "name": config["name"],
        "paths": paths,
        "packages": packages,
        "protected_packages": protected_packages,
        "running": False,
        "dry_run": True,
        "deletion_performed": False,
    }
