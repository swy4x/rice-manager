"""Read-only preflight planner for future profile activation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .manifest import Manifest, resolve_source


@dataclass(frozen=True)
class SwitchPlanItem:
    component_id: str
    name: str
    path: Path
    status: str
    detail: str


@dataclass(frozen=True)
class SwitchPlan:
    profile_id: str
    profile_name: str
    items: tuple[SwitchPlanItem, ...]

    @property
    def blocked(self) -> bool:
        return any(item.status.startswith("blocked-") for item in self.items)

    @property
    def ready_count(self) -> int:
        return sum(item.status == "ready" for item in self.items)

    @property
    def skipped_count(self) -> int:
        return sum(item.status == "skipped" for item in self.items)


def _kind(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "config-directory"
    if path.is_file():
        return "config-file"
    return "missing"


def build_switch_plan(manifest: Manifest) -> SwitchPlan:
    """Inspect activation prerequisites without creating, copying, or changing files.

    Manifest source paths are the intended user configuration destinations. This
    planner deliberately does not activate profiles: profile payload storage and
    transactional installation are separate future features.
    """
    home = Path.home().resolve()
    items: list[SwitchPlanItem] = []

    for component in manifest.components:
        path = resolve_source(component.source)

        if component.scope == "system" or component.read_only:
            items.append(SwitchPlanItem(
                component.id, component.name, path, "skipped",
                "System-scoped or read-only component; Rice Manager will not modify it.",
            ))
            continue

        # Refuse symlink destinations and paths that resolve outside the home.
        if path.is_symlink():
            items.append(SwitchPlanItem(
                component.id, component.name, path, "blocked-symlink",
                "Destination is a symlink; inspect and manage it manually.",
            ))
            continue

        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(home)
        except ValueError:
            items.append(SwitchPlanItem(
                component.id, component.name, path, "blocked-outside-home",
                "Writable destinations outside the home directory are not supported.",
            ))
            continue

        actual = _kind(path)
        if actual == "missing":
            if component.required:
                status = "blocked-required-missing"
                detail = "Required configuration is missing."
            else:
                status = "missing-optional"
                detail = "Optional configuration is missing; no directory or file will be created."
        elif actual != component.kind:
            status = "blocked-type-mismatch"
            detail = f"Expected {component.kind}, found {actual}."
        else:
            status = "ready"
            detail = "Destination exists and matches the declared component type."

        items.append(SwitchPlanItem(
            component.id, component.name, path, status, detail
        ))

    return SwitchPlan(manifest.id, manifest.name, tuple(items))
