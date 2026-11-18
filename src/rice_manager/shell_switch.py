"""Safe process switching between Cartoon Shell and Caelestia."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path


class ShellSwitchError(RuntimeError):
    pass


def _shells():
    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    ).expanduser()

    return {
        "cartoon-shell": {
            "name": "Cartoon Shell",
            "path": config_home / "quickshell/cartoon-shell/shell.qml",
        },
        "caelestia": {
            "name": "Caelestia",
            "path": Path("/etc/xdg/quickshell/caelestia/shell.qml"),
        },
    }


def _state_path():
    state_home = Path(
        os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")
    ).expanduser()
    return state_home / "rice-manager/active-shell.json"


def _instances():
    qs = shutil.which("qs")
    if not qs:
        raise ShellSwitchError("Quickshell command qs was not found.")

    result = subprocess.run(
        [qs, "list", "--all", "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ShellSwitchError(result.stderr.strip() or "Could not list Quickshell instances.")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ShellSwitchError("Quickshell returned invalid JSON.") from exc

    if not isinstance(data, list):
        raise ShellSwitchError("Unexpected Quickshell instance list.")
    return data


def _running_shells():
    result = {"cartoon-shell": [], "caelestia": []}

    for instance in _instances():
        config_path = str(instance.get("config_path", ""))

        for shell_id, config in _shells().items():
            if config_path == str(config["path"]):
                result[shell_id].append(instance)

    return result


def _active_shell():
    path = _state_path()

    if path.is_symlink():
        raise ShellSwitchError("Refusing symlinked shell state file.")

    if not path.exists():
        return None

    try:
        active = json.loads(path.read_text())["active"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ShellSwitchError(f"Could not read shell state: {exc}") from exc

    if active not in _shells():
        raise ShellSwitchError("Unknown shell in saved state.")
    return active


def _save_active(shell_id):
    path = _state_path()

    if path.is_symlink():
        raise ShellSwitchError("Refusing symlinked shell state file.")

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps({"active": shell_id}, indent=2) + "\n")
    temporary.replace(path)


def _start_shell(shell_id):
    config = _shells()[shell_id]

    if shell_id == "cartoon-shell":
        executable = shutil.which("qs")
        if not executable:
            raise ShellSwitchError("Quickshell command qs was not found.")
        if not config["path"].is_file():
            raise ShellSwitchError(f"Cartoon Shell config not found: {config["path"]}")
        command = [
            executable,
            "--path",
            str(config["path"].parent),
            "--daemonize",
        ]
    else:
        executable = shutil.which("caelestia")
        if not executable:
            raise ShellSwitchError("Caelestia command was not found.")
        command = [executable, "shell", "-d"]

    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise ShellSwitchError(f"Could not start {config["name"]}: {exc}") from exc


def _stop_running_shells():
    qs = shutil.which("qs")
    caelestia = shutil.which("caelestia")
    running = _running_shells()

    # Stop Cartoon Shell instances by their exact Quickshell instance IDs.
    for instance in running["cartoon-shell"]:
        result = subprocess.run(
            [qs, "kill", "--id", str(instance["id"])],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise ShellSwitchError(
                result.stderr.strip() or "Could not stop Cartoon Shell."
            )

    # Caelestia provides its own shell stop command.
    if running["caelestia"]:
        if not caelestia:
            raise ShellSwitchError("Caelestia command was not found.")
        result = subprocess.run(
            [caelestia, "shell", "-k"],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise ShellSwitchError(
                result.stderr.strip() or "Could not stop Caelestia."
            )


def switch_shell(target, apply=False):
    available = _shells()

    if target not in available:
        raise ShellSwitchError(f"Unknown shell: {target}")

    config = available[target]

    if target == "cartoon-shell" and not config["path"].is_file():
        raise ShellSwitchError(f"Cartoon Shell config not found: {config["path"]}")

    if target == "caelestia" and not shutil.which("caelestia"):
        raise ShellSwitchError("Caelestia command was not found.")

    running = _running_shells()
    current = [key for key, value in running.items() if value]

    report = {
        "name": config["name"],
        "currently_running": current,
        "applied": False,
    }

    if not apply:
        return report

    # If the requested shell is already running, only save the selection.
    if running[target]:
        _save_active(target)
        report["applied"] = True
        return report

    previous = current[0] if current else None

    _stop_running_shells()

    try:
        _start_shell(target)

        # Wait for Quickshell to register the new instance.
        for _ in range(20):
            time.sleep(0.25)
            if _running_shells()[target]:
                _save_active(target)
                report["applied"] = True
                return report

        raise ShellSwitchError(
            f"{config["name"]} did not appear in the running Quickshell list."
        )

    except Exception:
        # Best-effort recovery if the new shell could not be started.
        if previous:
            try:
                _start_shell(previous)
            except Exception:
                pass
        raise


def start_selected_shell():
    target = _active_shell() or "cartoon-shell"

    if not _running_shells()[target]:
        _start_shell(target)
