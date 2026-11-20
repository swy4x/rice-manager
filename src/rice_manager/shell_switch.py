"""Safe process switching between Cartoon Shell and Caelestia."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .shell_registry import (
    ShellRegistryError,
    load_installed_shells,
)


class ShellSwitchError(RuntimeError):
    pass



def _shells():
    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    ).expanduser()

    shells = {
        "cartoon-shell": {
            "name": "Cartoon Shell",
            "path": config_home / "quickshell/cartoon-shell/shell.qml",
            "type": "quickshell",
        },
        "caelestia": {
            "name": "Caelestia",
            "path": Path("/etc/xdg/quickshell/caelestia/shell.qml"),
            "type": "caelestia",
        },
    }

    try:
        shells.update(load_installed_shells())
    except ShellRegistryError as exc:
        raise ShellSwitchError(str(exc)) from exc

    return shells

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
        raise ShellSwitchError(
            result.stderr.strip() or "Could not list Quickshell instances."
        )

    output = result.stdout.strip()

    if output == "No running instances.":
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ShellSwitchError("Quickshell returned invalid JSON.") from exc

    if not isinstance(data, list):
        raise ShellSwitchError("Unexpected Quickshell instance list.")

    for instance in data:
        if not isinstance(instance, dict) or not instance.get("id"):
            raise ShellSwitchError("Invalid Quickshell instance information.")

    return data



def _running_shells():
    shells = _shells()
    result = {shell_id: [] for shell_id in shells}

    for instance in _instances():
        config_path = str(instance.get("config_path", ""))

        for shell_id, config in shells.items():
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
    fd, temporary = tempfile.mkstemp(prefix=".active-shell-", dir=path.parent)

    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"active": shell_id}, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except OSError as exc:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise ShellSwitchError(f"Could not save shell selection: {exc}") from exc




def _restore_active(shell_id):
    """Restore the previous saved selection, including an absent state file."""
    path = _state_path()

    if path.is_symlink():
        raise ShellSwitchError("Refusing symlinked shell state file.")

    if shell_id is None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise ShellSwitchError(
                f"Could not restore previous shell selection: {exc}"
            ) from exc
    else:
        _save_active(shell_id)


def _start_shell(shell_id):
    config = _shells()[shell_id]

    if not config["path"].is_file():
        raise ShellSwitchError(
            f"{config['name']} config not found: {config['path']}"
        )

    if config.get("type") == "caelestia":
        executable = shutil.which("caelestia")
        if not executable:
            raise ShellSwitchError("Caelestia command was not found.")
        command = [executable, "shell", "-d"]
    else:
        executable = shutil.which("qs")
        if not executable:
            raise ShellSwitchError("Quickshell command qs was not found.")
        command = [
            executable,
            "--path", str(config["path"].parent),
            "--daemonize",
            "--no-duplicate",
        ]

    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise ShellSwitchError(
            f"Could not start {config['name']}: {exc}"
        ) from exc


def _stop_shell(shell_id, instances):
    if not instances:
        return

    config = _shells()[shell_id]

    if config.get("type") == "caelestia":
        executable = shutil.which("caelestia")
        if not executable:
            raise ShellSwitchError("Caelestia command was not found.")

        result = subprocess.run(
            [executable, "shell", "-k"],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise ShellSwitchError(
                result.stderr.strip() or "Could not stop Caelestia."
            )
        return

    qs = shutil.which("qs")
    if not qs:
        raise ShellSwitchError("Quickshell command qs was not found.")

    for instance in instances:
        result = subprocess.run(
            [qs, "kill", "--id", str(instance["id"])],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise ShellSwitchError(
                result.stderr.strip()
                or f"Could not stop {config['name']}."
            )


def _wait_for_shell_state(shell_id, should_run):
    for attempt in range(20):
        instances = _running_shells().get(shell_id, [])
        if bool(instances) == should_run:
            return instances
        if attempt < 19:
            time.sleep(0.25)

    state = "start" if should_run else "stop"
    raise ShellSwitchError(
        f"{_shells()[shell_id]['name']} did not {state} during rollback."
    )


def switch_shell(target, apply=False):
    available = _shells()

    if target not in available:
        raise ShellSwitchError(f"Unknown shell: {target}")

    config = available[target]

    if target == "cartoon-shell" and not config["path"].is_file():
        raise ShellSwitchError(f"Cartoon Shell config not found: {config['path']}")

    if target == "caelestia":
        if not shutil.which("caelestia"):
            raise ShellSwitchError("Caelestia command was not found.")
        if not config["path"].is_file():
            raise ShellSwitchError(f"Caelestia config not found: {config['path']}")

    running = _running_shells()
    current = [key for key, value in running.items() if value]

    report = {
        "name": config["name"],
        "currently_running": current,
        "applied": False,
    }

    if not apply:
        return report

    previous_active = _active_shell()
    target_started = False

    if not running[target]:
        _start_shell(target)
        target_started = True

        for _ in range(20):
            time.sleep(0.25)
            running = _running_shells()
            if running[target]:
                break
        else:
            raise ShellSwitchError(
                f"{config['name']} did not start. Existing shell was left running."
            )

    stopped_shells = []

    try:
        _save_active(target)

        for shell_id, instances in running.items():
            if shell_id != target and instances:
                # A stop command may partially stop a shell before failing.
                stopped_shells.append(shell_id)
                _stop_shell(shell_id, instances)

    except Exception as exc:
        rollback_errors = []

        for shell_id in reversed(stopped_shells):
            try:
                if not _running_shells().get(shell_id, []):
                    _start_shell(shell_id)
                _wait_for_shell_state(shell_id, True)
            except Exception as rollback_exc:
                rollback_errors.append(
                    f"Could not verify restoration of "
                    f"{available[shell_id]['name']}: {rollback_exc}"
                )

        if target_started:
            try:
                target_instances = _running_shells().get(target, [])
                if target_instances:
                    _stop_shell(target, target_instances)
                _wait_for_shell_state(target, False)
            except Exception as rollback_exc:
                rollback_errors.append(
                    f"Could not verify stopping newly started "
                    f"{config['name']}: {rollback_exc}"
                )

        try:
            _restore_active(previous_active)
        except Exception as rollback_exc:
            rollback_errors.append(str(rollback_exc))

        message = f"Shell switch failed: {exc}. Rollback attempted."
        if rollback_errors:
            message += " Rollback problems: " + "; ".join(rollback_errors)

        raise ShellSwitchError(message) from exc

    report["applied"] = True
    report["currently_running"] = [target]
    return report


def start_selected_shell():
    target = _active_shell() or "cartoon-shell"
    if not _running_shells()[target]:
        _start_shell(target)
    return target
