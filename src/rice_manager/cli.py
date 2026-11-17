"""Command-line interface for Rice Manager."""

from __future__ import annotations

import argparse
import json

from . import __version__
from .backup import BackupError, create_backup
from .restore import RestoreError, restore_backup
from .manifest import ManifestError, load_manifest, resolve_source
from .planner import build_switch_plan
from .profiles import ProfileDiscoveryError, discover_profiles
from .system import inspect_path, inspect_system


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rice-manager",
        description="Safety-first manager for desktop rice profiles.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    commands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser(
        "inspect",
        help="Inspect desktop configuration paths (read-only).",
    )
    inspect_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    profile_parser = commands.add_parser("profile", help="Manage profile manifests.")
    profile_commands = profile_parser.add_subparsers(dest="profile_command", required=True)
    for name, help_text in (
        ("validate", "Validate a profile manifest."),
        ("inspect", "Inspect profile component paths (read-only)."),
        ("plan", "Preview profile activation prerequisites (read-only)."),
    ):
        sub = profile_commands.add_parser(name, help=help_text)
        sub.add_argument("manifest", help="Path to a profile manifest JSON file.")
        if name == "plan":
            sub.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    list_parser = profile_commands.add_parser(
        "list", help="Discover profile manifests in a directory (read-only)."
    )
    list_parser.add_argument("directory", help="Directory containing profile subdirectories.")
    list_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    backup_parser = profile_commands.add_parser(
        "backup", help="Back up writable user components from a profile."
    )
    backup_parser.add_argument("manifest", help="Path to a profile manifest JSON file.")
    backup_parser.add_argument(
        "--destination",
        help="Backup directory (default: ~/.local/share/rice-manager/backups).",
    )
    restore_parser = profile_commands.add_parser(
        "restore", help="Preview a backup restore; use --apply to make changes."
    )
    restore_parser.add_argument("backup", help="Path to a Rice Manager backup directory.")
    restore_parser.add_argument(
        "--apply", action="store_true", help="Apply the restore after creating safety backups."
    )
    return parser


def _plan_json(plan, manifest) -> dict:
    blocked_count = sum(item.status.startswith("blocked-") for item in plan.items)
    return {
        "schema_version": 1,
        "profile": {
            "id": plan.profile_id,
            "name": plan.profile_name,
            "version": manifest.version,
            "description": manifest.description,
        },
        "items": [
            {
                "component_id": item.component_id,
                "name": item.name,
                "kind": component.kind,
                "source": component.source,
                "path": str(item.path),
                "scope": component.scope,
                "required": component.required,
                "read_only": component.read_only,
                "status": item.status,
                "detail": item.detail,
            }
            for item, component in zip(plan.items, manifest.components)
        ],
        "summary": {
            "ready": plan.ready_count,
            "skipped": plan.skipped_count,
            "blocked": blocked_count,
        },
        "blocked": plan.blocked,
        "dry_run": True,
    }


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "inspect":
        report = inspect_system()
        if args.json:
            print(json.dumps(report, indent=2))
            return

        print(f"Rice Manager {__version__} — read-only system inspection")
        print(f"Platform: {report['platform']}")
        print(f"Home: {report['home']}")
        print(f"Python: {report['python']}")
        print("\nDetected tools:")
        for name, location in report["tools"].items():
            print(f"  {name:<12} {location or 'not found'}")

        print("\nConfiguration paths:")
        for item in report["paths"]:
            state = item["kind"]
            target = f" -> {item['symlink_target']}" if item["symlink_target"] else ""
            print(f"  [{state:<9}] {item['label']}: {item['path']}{target}")
        return

    if args.command == "profile":
        try:
            if args.profile_command == "list":
                profiles = discover_profiles(args.directory)
                if args.json:
                    print(json.dumps({
                        "schema_version": 1,
                        "directory": args.directory,
                        "profiles": profiles,
                    }, indent=2))
                    return
                print(f"Discovered profiles: {len(profiles)}")
                for profile in profiles:
                    if profile["valid"]:
                        summary = profile["summary"]
                        print(
                            f"  [{profile['id']}] {profile['name']} "
                            f"— components {profile['component_count']}, "
                            f"ready {summary['ready']}, skipped {summary['skipped']}, "
                            f"blocked {summary['blocked']}"
                        )
                    else:
                        print(f"  [invalid] {profile['directory']}: {profile['error']}")
                print("Read-only discovery; no files were changed.")
                return

            if args.profile_command == "restore":
                plan = restore_backup(args.backup, apply=args.apply)
                print("Restore applied." if args.apply else "Restore preview (no files changed):")
                for item in plan.items:
                    state = "restored" if args.apply else ("replace existing" if item.target.exists() else "create")
                    print(f"  [{state}] {item.name}: {item.target}")
                if args.apply:
                    print("Existing destinations were safety-backed up before replacement.")
                else:
                    print("\nRun the same command with --apply to restore these components.")
                return

            manifest = load_manifest(args.manifest)
            if args.profile_command == "validate":
                print(f"Valid manifest: {manifest.name} ({manifest.id})")
                print(f"Version: {manifest.version}")
                print(f"Components: {len(manifest.components)}")
                return

            if args.profile_command == "plan":
                plan = build_switch_plan(manifest)
                if args.json:
                    print(json.dumps(_plan_json(plan, manifest), indent=2))
                    return

                print(f"Switch preflight: {plan.profile_name} ({plan.profile_id})")
                print("\nComponents:")
                for item in plan.items:
                    print(f"  [{item.status}] {item.name}: {item.path}")
                    print(f"      {item.detail}")
                blocked = sum(item.status.startswith("blocked-") for item in plan.items)
                print(f"\nReady: {plan.ready_count} | Skipped: {plan.skipped_count} | Blocked: {blocked}")
                print("Dry-run only: no files were created, copied, or changed.")
                print("Profile activation is not implemented yet.")
                if plan.blocked:
                    print("Preflight result: BLOCKED")
                else:
                    print("Preflight result: no blocking issues detected")
                return

            if args.profile_command == "inspect":
                print(f"Profile: {manifest.name} ({manifest.id})")
                print(f"Manifest version: {manifest.version}")
                print("\nComponents (read-only inspection):")
                for component in manifest.components:
                    path = resolve_source(component.source)
                    status = inspect_path(component.name, path)
                    required = "required" if component.required else "optional"
                    safety = "read-only" if component.read_only or component.scope == "system" else "user config"
                    print(
                        f"  [{status['kind']:<9}] {component.name}: {path} "
                        f"({required}, {safety})"
                    )
                return

            if args.profile_command == "backup":
                destination = create_backup(manifest, args.destination)
                print(f"Backup created: {destination}")
                print("Only writable user components were included; system/read-only components were skipped.")
                return

        except (ManifestError, BackupError, RestoreError, ProfileDiscoveryError) as exc:
            raise SystemExit(f"Rice Manager error: {exc}") from exc


if __name__ == "__main__":
    main()
