"""Command-line interface for Rice Manager."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .backup import BackupError, create_backup
from .activation import ActivationError, apply_profile_payload
from .dependencies import check_dependencies
from .restore import RestoreError, restore_backup
from .manifest import ManifestError, load_manifest, resolve_source
from .planner import build_switch_plan
from .payload_inventory import PayloadInventoryError, build_payload_inventory
from .profiles import ProfileDiscoveryError, discover_profiles
from .profile_import import ProfileImportError, import_profile, preview_profile_import, preview_profile_removal, remove_imported_profile
from .github_import import GitHubImportError, scan_github_repository
from .system import inspect_path, inspect_system
from .shell_switch import ShellSwitchError, switch_shell, start_selected_shell


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rice-manager",
        description="Safety-first manager for desktop rice profiles.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    commands = parser.add_subparsers(dest="command", required=True)
    switch_parser = commands.add_parser(
        "switch",
        help="Preview or switch desktop shells.",
    )
    switch_parser.add_argument(
        "target",
        help="Shell ID (built-in or installed GitHub shell).",
    )
    switch_parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the shell switch.",
    )
    commands.add_parser("shell-start", help="Start the saved desktop shell at login.")

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
        ("deps", "Check declared package dependencies (read-only)."),
        ("inventory", "Compare profile payload files with destinations (read-only)."),
    ):
        sub = profile_commands.add_parser(name, help=help_text)
        sub.add_argument("manifest", help="Path to a profile manifest JSON file.")
        if name in {"plan", "deps", "inventory"}:
            sub.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
        if name == "inventory":
            sub.add_argument("--profile-dir", help="Profile directory (default: manifest directory).")
    scan_parser = profile_commands.add_parser(
        "scan", help="Scan a public GitHub dotfiles repository (read-only)."
    )
    scan_parser.add_argument("url", help="Public GitHub repository URL.")
    scan_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    apply_parser = profile_commands.add_parser(
        "apply", help="Preview or explicitly apply a profile payload transaction."
    )
    apply_parser.add_argument("manifest", help="Path to a profile manifest JSON file.")
    apply_parser.add_argument("--profile-dir", help="Profile directory (default: manifest directory).")
    apply_parser.add_argument("--apply", action="store_true", help="Install the reviewed payload files.")
    apply_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    list_parser = profile_commands.add_parser(
        "list", help="Discover profile manifests in a directory (read-only)."
    )
    list_parser.add_argument("directory", help="Directory containing profile subdirectories.")
    list_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    import_parser = profile_commands.add_parser(
        "import", help="Preview or import a local profile directory into the private library."
    )
    import_parser.add_argument("source", help="Local profile directory containing manifest.json.")
    import_parser.add_argument("--library", help="Profile library directory (default: ~/.local/share/rice-manager/profiles).")
    import_parser.add_argument("--apply", action="store_true", help="Copy the profile after reviewing the preview.")
    import_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    remove_parser = profile_commands.add_parser(
        "remove", help="Preview or remove one imported profile from the private library."
    )
    remove_parser.add_argument("profile_id", help="ID of the imported profile to remove.")
    remove_parser.add_argument("--library", help="Profile library directory (default: ~/.local/share/rice-manager/profiles).")
    remove_parser.add_argument("--apply", action="store_true", help="Permanently remove the profile after reviewing the preview.")
    remove_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
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


def _print_dependency_report(report: dict) -> None:
    profile = report["profile"]
    print(f"Dependency check: {profile['name']} ({profile['id']})")
    if report["status"] == "not-required":
        print("No package dependencies declared.")
    elif report["status"] == "unavailable":
        print("Package check unavailable; dependencies could not be verified.")
    else:
        for item in report["dependencies"]:
            print(f"  [{item['status']}] {item['name']}")
        print(
            f"\nInstalled: {len(report['installed'])} | "
            f"Missing: {len(report['missing'])}"
        )
        if report["install_command"]:
            print("\nSuggested command (not executed):")
            print(f"  {report['install_command']}")
    print("Read-only check: no packages were installed or changed.")


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "shell-start":
        try:
            start_selected_shell()
        except ShellSwitchError as exc:
            raise SystemExit(
                f"Rice Manager error: {exc}"
            ) from exc
        return

    if args.command == "switch":
        try:
            report = switch_shell(
                args.target,
                apply=args.apply,
            )
        except ShellSwitchError as exc:
            raise SystemExit(
                f"Rice Manager error: {exc}"
            ) from exc

        mode = "applied" if args.apply else "preview"
        print(f"Shell switch {mode}: {report['name']}")
        print(
            "Currently running: "
            + (
                ", ".join(report["currently_running"])
                or "none"
            )
        )

        if not args.apply:
            print("Preview only. No processes or files changed.")
            print("Use --apply to perform the switch.")
        else:
            print("Active shell selection saved.")
        return

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

            if args.profile_command == "import":
                plan = preview_profile_import(args.source, args.library)
                if args.apply:
                    destination = import_profile(args.source, args.library)
                    plan["destination"] = str(destination)
                    plan["dry_run"] = False
                if args.json:
                    print(json.dumps(plan, indent=2))
                    return
                print("Profile import preview (no files changed):" if not args.apply else "Profile imported:")
                print(f"  Profile: {plan['profile_name']} ({plan['profile_id']})")
                print(f"  Source: {plan['source']}")
                print(f"  Destination: {plan['destination']}")
                print(f"  Files: {plan['file_count']} | Total bytes: {plan['total_bytes']}")
                for item in plan["files"]:
                    print(f"    {item['path']} ({item['size']} bytes)")
                if not args.apply:
                    print("\nRun the same command with --apply only after reviewing this file list.")
                return

            if args.profile_command == "remove":
                report = preview_profile_removal(args.profile_id, args.library)
                if args.apply:
                    destination = remove_imported_profile(args.profile_id, args.library)
                    report["destination"] = str(destination)
                    report["dry_run"] = False
                    report["removed"] = True
                if args.json:
                    print(json.dumps(report, indent=2))
                elif args.apply:
                    print(f"Imported profile removed: {report['profile_id']}")
                else:
                    print("Profile removal preview (no files changed):")
                    print(f"  Profile: {report['profile_name']} ({report['profile_id']})")
                    print(f"  Directory: {report['destination']}")
                    print("\nRun the same command with --apply only after reviewing this target.")
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

            if args.profile_command == "scan":
                report = scan_github_repository(args.url)
                if args.json:
                    print(json.dumps(report, indent=2))
                    return

                repository = report["repository"]
                summary = report["summary"]

                print(f"GitHub repository scan: {repository["name"]}")
                print(f"URL: {repository["url"]}")
                print(f"Default branch: {repository["branch"]}")
                print(f"\nFiles scanned: {summary["files_scanned"]}")
                print(f"Components detected: {summary["components_detected"]}")

                for component in report["components"]:
                    print(f"\n  {component["name"]}")
                    print(f"    Source: {component["source_root"]}")
                    print(f"    Destination: {component["destination"]}")
                    print(f"    Files: {component["file_count"]}")
                    print(f"    Dependency: {component["dependency"]}")

                print("\nRead-only scan. No files installed or changed.")
                return

            manifest = load_manifest(args.manifest)
            if args.profile_command == "apply":
                profile_directory = args.profile_dir or str(Path(args.manifest).expanduser().parent)
                report = apply_profile_payload(manifest, profile_directory, apply=args.apply)
                if args.json:
                    print(json.dumps(report, indent=2))
                    return
                if args.apply and report["applied"]:
                    title = "Payload installed:"
                elif args.apply:
                    title = "No changes required:"
                else:
                    title = "Payload apply preview (no files changed):"
                print(f"{title} {manifest.name} ({manifest.id})")
                for item in report["files"]:
                    print(f"  [{item['action']}] {item['component']}: {item['destination']}")
                summary = report["summary"]
                print(f"\\nADD: {summary['ADD']} | REPLACE: {summary['REPLACE']} | UNCHANGED: {summary['UNCHANGED']}")
                if args.apply:
                    print(f"Safety snapshot: {report.get('safety_backup', 'not needed')}")
                    print("Extra destination files were left untouched.")
                else:
                    print("\\nNo files were changed. Review this list, then rerun with --apply to install.")
                return

            if args.profile_command == "inventory":
                profile_directory = args.profile_dir or str(Path(args.manifest).expanduser().parent)
                report = build_payload_inventory(manifest, profile_directory)
                if args.json:
                    print(json.dumps(report, indent=2))
                    return
                print(f"Payload inventory: {manifest.name} ({manifest.id})")
                for component in report["components"]:
                    print(f"  [{component['status']}] {component['name']}: {component['destination']}")
                    for item in component["files"]:
                        print(f"    [{item['action']}] {item['path']}")
                summary = report["summary"]
                print("\nADD: {ADD} | REPLACE: {REPLACE} | UNCHANGED: {UNCHANGED} | CONFLICT: {CONFLICT}".format(**summary))
                print("Dry-run only: no files were created, copied, replaced, or deleted.")
                return

            if args.profile_command == "deps":
                report = check_dependencies(manifest)
                if args.json:
                    print(json.dumps(report, indent=2))
                else:
                    _print_dependency_report(report)
                return

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

        except (ManifestError, BackupError, RestoreError, ActivationError, ProfileDiscoveryError, ProfileImportError, PayloadInventoryError, GitHubImportError) as exc:
            raise SystemExit(f"Rice Manager error: {exc}") from exc


if __name__ == "__main__":
    main()
