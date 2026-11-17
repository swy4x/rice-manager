"""Preview-first restore engine with safety snapshots."""
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class RestoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class RestoreItem:
    component_id: str
    name: str
    source: Path
    target: Path
    kind: str


@dataclass(frozen=True)
class RestorePlan:
    backup: Path
    items: tuple[RestoreItem, ...]


_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _kind(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "config-directory"
    if path.is_file():
        return "config-file"
    return "missing"


def _has_any_symlink(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _has_symlink(path: Path, stop: Path) -> bool:
    try:
        relative = path.relative_to(stop)
    except ValueError:
        return True
    current = stop
    for part in relative.parts:
        if part in {"", ".", ".."}:
            return True
        current = current / part
        if current.is_symlink():
            return True
    return False


def _copy(source: Path, dest: Path, kind: str) -> None:
    if kind == "config-directory":
        shutil.copytree(source, dest, symlinks=True, copy_function=shutil.copy2)
    elif kind == "config-file":
        shutil.copy2(source, dest, follow_symlinks=False)
    else:
        raise RestoreError(f"Unsupported component type: {kind}")


def inspect_backup(backup_dir: str | Path) -> RestorePlan:
    root = Path(backup_dir).expanduser().absolute()
    if root.is_symlink() or _has_any_symlink(root) or not root.is_dir():
        raise RestoreError("Backup path must be an existing directory without symlinked path components.")
    metadata_path = root / "backup.json"
    if metadata_path.is_symlink() or not metadata_path.is_file():
        raise RestoreError("Backup metadata must be a regular, non-symlink file.")
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RestoreError(f"Cannot read backup metadata: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RestoreError(f"Invalid backup metadata JSON: {exc.msg}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise RestoreError("Unsupported or invalid backup metadata schema.")
    profile_id, entries = data.get("profile_id"), data.get("components")
    if not isinstance(profile_id, str) or not _ID.fullmatch(profile_id):
        raise RestoreError("Invalid profile ID in backup metadata.")
    if not isinstance(entries, list) or not entries:
        raise RestoreError("Backup contains no restorable components.")

    home = Path.home().resolve()
    items, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise RestoreError("Invalid component entry.")
        cid, name = entry.get("component_id"), entry.get("name")
        target_text, rel, kind = entry.get("source"), entry.get("backup_path"), entry.get("kind")
        if not isinstance(cid, str) or not _ID.fullmatch(cid) or cid in seen:
            raise RestoreError("Invalid or duplicate component ID.")
        seen.add(cid)
        if not isinstance(name, str) or not name.strip():
            raise RestoreError(f"Invalid component name: {cid}")
        if not isinstance(target_text, str) or not Path(target_text).is_absolute():
            raise RestoreError(f"Invalid restore destination: {cid}")
        if kind not in {"config-directory", "config-file"} or rel != f"components/{cid}":
            raise RestoreError(f"Invalid backup component declaration: {cid}")
        target = Path(target_text)
        resolved_target = target.resolve(strict=False)
        if (resolved_target == home or not _inside(resolved_target, home)
                or _has_symlink(target, home)):
            raise RestoreError(f"Refusing unsafe or symlinked destination path: {target}")
        source = root / rel
        if (_has_symlink(source, root) or not _inside(source.resolve(strict=False), root.resolve())):
            raise RestoreError(f"Unsafe or symlinked backup component path: {rel}")
        if _kind(source) != kind:
            raise RestoreError(f"Backup component missing or wrong type: {cid}")
        items.append(RestoreItem(cid, name, source, target, kind))

    for i, item in enumerate(items):
        for other in items[i + 1:]:
            if item.target == other.target or _inside(item.target, other.target) or _inside(other.target, item.target):
                raise RestoreError("Backup contains overlapping restore destinations.")
    return RestorePlan(root, tuple(items))


def restore_backup(backup_dir: str | Path, *, apply: bool = False) -> RestorePlan:
    plan = inspect_backup(backup_dir)
    if not apply:
        return plan

    home = Path.home().resolve()
    safety_root = home / ".local/share/rice-manager/backups"
    if (_has_symlink(safety_root, home)
            or not _inside(safety_root.resolve(strict=False), home)):
        raise RestoreError("Rice Manager safety-backup path is unsafe (symlink or outside home).")
    safety_root = safety_root.resolve(strict=False)
    for item in plan.items:
        if _has_symlink(item.target, home):
            raise RestoreError(f"Refusing symlinked destination path: {item.target}")
        if item.target.exists() and _kind(item.target) != item.kind:
            raise RestoreError(f"Destination type mismatch: {item.target}")
        parent = item.target.parent
        if parent.exists() and not parent.is_dir():
            raise RestoreError(f"Destination parent is not a directory: {parent}")
        if (not _inside(parent.resolve(strict=False), home)
                or _has_symlink(parent, home)):
            raise RestoreError(f"Destination parent is unsafe or symlinked: {parent}")
        if item.target == safety_root or _inside(item.target, safety_root) or _inside(safety_root, item.target):
            raise RestoreError("Restore destination overlaps Rice Manager's safety-backup directory.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safety_root.mkdir(parents=True, exist_ok=True)
    if safety_root.is_symlink() or _has_symlink(safety_root, home) or not safety_root.is_dir():
        raise RestoreError("Rice Manager safety-backup directory became unsafe.")
    safety = Path(tempfile.mkdtemp(prefix=f"pre-restore-{stamp}-", dir=safety_root))
    stages, moved = [], []
    try:
        saved = []
        for item in plan.items:
            if item.target.exists():
                dest = safety / "components" / item.component_id
                dest.parent.mkdir(parents=True, exist_ok=True)
                _copy(item.target, dest, item.kind)
                saved.append({"component_id": item.component_id, "source": str(item.target),
                              "backup_path": f"components/{item.component_id}", "kind": item.kind})
        (safety / "safety-backup.json").write_text(json.dumps({
            "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "components": saved,
        }, indent=2) + "\n", encoding="utf-8")

        for item in plan.items:
            item.target.parent.mkdir(parents=True, exist_ok=True)
            if (not _inside(item.target.parent.resolve(), home)
                    or _has_symlink(item.target.parent, home)):
                raise RestoreError(f"Destination parent escapes home or contains a symlink: {item.target.parent}")
            stage_dir = Path(tempfile.mkdtemp(prefix=".rice-manager-stage-", dir=item.target.parent))
            payload = stage_dir / "payload"
            _copy(item.source, payload, item.kind)
            stages.append((item, stage_dir, payload))

        for item, stage_dir, payload in stages:
            rollback = None
            if item.target.exists():
                rollback = item.target.parent / f".{item.target.name}.rice-manager-rollback-{stamp}"
                if rollback.exists():
                    raise RestoreError(f"Rollback path already exists: {rollback}")
                item.target.rename(rollback)
            try:
                payload.rename(item.target)
            except Exception:
                if rollback is not None and rollback.exists():
                    rollback.rename(item.target)
                raise
            moved.append((item, rollback))

        for _, rollback in moved:
            if rollback is not None:
                if rollback.is_dir() and not rollback.is_symlink():
                    shutil.rmtree(rollback)
                else:
                    rollback.unlink()
        return plan
    except Exception as exc:
        for item, rollback in reversed(moved):
            if item.target.exists():
                if item.target.is_dir() and not item.target.is_symlink():
                    shutil.rmtree(item.target)
                else:
                    item.target.unlink()
            if rollback is not None and rollback.exists():
                rollback.rename(item.target)
        if isinstance(exc, RestoreError):
            raise
        raise RestoreError(f"Restore failed; safety snapshot retained at {safety}: {exc}") from exc
    finally:
        for _, stage_dir, _ in stages:
            shutil.rmtree(stage_dir, ignore_errors=True)
