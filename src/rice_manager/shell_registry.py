"""Registry for user-installed Quickshell environments."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path


class ShellRegistryError(RuntimeError):
    """Raised when the installed-shell registry is invalid or unsafe."""


def _config_home() -> Path:
    return Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    ).expanduser().absolute()


def _registry_path() -> Path:
    data_home = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")
    ).expanduser().absolute()
    return data_home / "rice-manager" / "installed-shells.json"


def _validate_record(record: dict) -> dict:
    if not isinstance(record, dict):
        raise ShellRegistryError("Invalid installed-shell record.")

    shell_id = record.get("id")
    name = record.get("name")
    raw_path = record.get("path")
    repository = record.get("repository")

    if not isinstance(shell_id, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,63}", shell_id
    ):
        raise ShellRegistryError("Invalid installed-shell ID.")

    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ShellRegistryError("Invalid installed-shell name.")

    if not isinstance(raw_path, str):
        raise ShellRegistryError("Invalid installed-shell path.")

    path = Path(raw_path).expanduser().absolute()
    config_root = (_config_home() / "quickshell").resolve()

    if path.is_symlink():
        raise ShellRegistryError("Installed shell entrypoint is a symlink.")

    try:
        path.relative_to(config_root)
    except ValueError as exc:
        raise ShellRegistryError(
            "Installed shell must be inside the user Quickshell directory."
        ) from exc

    if not path.is_file():
        raise ShellRegistryError(
            f"Installed shell entrypoint is missing: {path}"
        )

    if not isinstance(repository, str) or not repository.startswith(
        "https://github.com/"
    ):
        raise ShellRegistryError("Invalid repository URL.")

    return {
        "id": shell_id,
        "name": name.strip(),
        "path": str(path),
        "repository": repository,
        "type": "quickshell",
    }


def load_installed_shells() -> dict:
    """Load and validate registered user-installed shells."""
    path = _registry_path()

    if path.is_symlink():
        raise ShellRegistryError("Registry file must not be a symlink.")

    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ShellRegistryError(
            f"Could not read installed-shell registry: {exc}"
        ) from exc

    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ShellRegistryError("Unsupported shell registry format.")

    records = data.get("shells")

    if not isinstance(records, list):
        raise ShellRegistryError("Invalid shell registry entries.")

    result = {}

    for record in records:
        validated = _validate_record(record)
        shell_id = validated["id"]

        if shell_id in result or shell_id in {"cartoon-shell", "caelestia"}:
            raise ShellRegistryError(
                f"Duplicate or reserved shell ID: {shell_id}"
            )

        result[shell_id] = {
            "name": validated["name"],
            "path": Path(validated["path"]),
            "repository": validated["repository"],
            "type": "quickshell",
        }

    return result


def register_installed_shell(record: dict) -> dict:
    """Register one already-installed Quickshell configuration."""
    validated = _validate_record(record)

    if validated["id"] in {"cartoon-shell", "caelestia"}:
        raise ShellRegistryError("That shell ID is reserved.")

    existing = load_installed_shells()

    if validated["id"] in existing:
        raise ShellRegistryError(
            f"Shell is already registered: {validated['id']}"
        )

    existing[validated["id"]] = {
        "name": validated["name"],
        "path": Path(validated["path"]),
        "repository": validated["repository"],
        "type": "quickshell",
    }

    registry = _registry_path()

    if registry.is_symlink():
        raise ShellRegistryError("Registry file must not be a symlink.")

    registry.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": 1,
        "shells": [
            {
                "id": shell_id,
                "name": item["name"],
                "path": str(item["path"]),
                "repository": item["repository"],
            }
            for shell_id, item in sorted(existing.items())
        ],
    }

    fd, temporary = tempfile.mkstemp(
        prefix=".installed-shells-",
        dir=registry.parent,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, registry)
    except OSError as exc:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise ShellRegistryError(
            f"Could not save shell registry: {exc}"
        ) from exc

    return validated


def unregister_installed_shell(shell_id: str) -> dict:
    """Remove one registered shell without touching its files."""
    if not isinstance(shell_id, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,63}", shell_id
    ):
        raise ShellRegistryError("Invalid installed-shell ID.")

    if shell_id in {"cartoon-shell", "caelestia"}:
        raise ShellRegistryError("Built-in shells cannot be unregistered.")

    existing = load_installed_shells()
    if shell_id not in existing:
        raise ShellRegistryError(f"Shell is not registered: {shell_id}")

    removed = existing.pop(shell_id)
    registry = _registry_path()

    if registry.is_symlink():
        raise ShellRegistryError("Registry file must not be a symlink.")

    registry.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "shells": [
            {
                "id": key,
                "name": item["name"],
                "path": str(item["path"]),
                "repository": item["repository"],
            }
            for key, item in sorted(existing.items())
        ],
    }

    fd, temporary = tempfile.mkstemp(
        prefix=".installed-shells-",
        dir=registry.parent,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, registry)
    except OSError as exc:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise ShellRegistryError(
            f"Could not update shell registry: {exc}"
        ) from exc

    return removed
