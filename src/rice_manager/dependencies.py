"""Read-only Arch Linux package dependency checks."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from .manifest import Manifest


def check_dependencies(manifest: Manifest) -> dict[str, Any]:
    """Compare explicitly declared package names with the local pacman database.

    This function only queries the package database. It never installs or changes
    packages, and it never invokes a shell.
    """
    packages = list(manifest.dependencies)
    report: dict[str, Any] = {
        "schema_version": 1,
        "profile": {"id": manifest.id, "name": manifest.name},
        "package_manager": "pacman",
        "status": "not-required" if not packages else "unavailable",
        "dependencies": [],
        "installed": [],
        "missing": [],
        "install_command": None,
        "dry_run": True,
    }
    if not packages:
        return report

    pacman = shutil.which("pacman")
    if pacman is None:
        report["dependencies"] = [
            {"name": package, "status": "unverified"} for package in packages
        ]
        return report

    try:
        result = subprocess.run(
            [pacman, "-Q"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        report["dependencies"] = [
            {"name": package, "status": "unverified"} for package in packages
        ]
        return report

    if result.returncode != 0:
        report["dependencies"] = [
            {"name": package, "status": "unverified"} for package in packages
        ]
        return report

    installed_names = {
        line.split(maxsplit=1)[0]
        for line in result.stdout.splitlines()
        if line.split(maxsplit=1)
    }
    installed = [package for package in packages if package in installed_names]
    missing = [package for package in packages if package not in installed_names]
    report.update({
        "status": "checked",
        "dependencies": [
            {
                "name": package,
                "status": "installed" if package in installed_names else "missing",
            }
            for package in packages
        ],
        "installed": installed,
        "missing": missing,
        "install_command": (
            "sudo pacman -S --needed " + " ".join(missing) if missing else None
        ),
    })
    return report
