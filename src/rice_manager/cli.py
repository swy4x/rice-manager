"""Command-line interface for Rice Manager."""

from __future__ import annotations

import argparse
import json

from . import __version__
from .manifest import ManifestError, load_manifest, resolve_source
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

    profile_parser = commands.add_parser("profile", help="Validate or inspect a profile manifest.")
    profile_commands = profile_parser.add_subparsers(dest="profile_command", required=True)
    for name, help_text in (
        ("validate", "Validate a profile manifest."),
        ("inspect", "Validate a manifest and inspect its component paths (read-only)."),
    ):
        sub = profile_commands.add_parser(name, help=help_text)
        sub.add_argument("manifest", help="Path to a profile manifest JSON file.")
    return parser


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
            manifest = load_manifest(args.manifest)
        except ManifestError as exc:
            raise SystemExit(f"Manifest error: {exc}") from exc

        if args.profile_command == "validate":
            print(f"Valid manifest: {manifest.name} ({manifest.id})")
            print(f"Version: {manifest.version}")
            print(f"Components: {len(manifest.components)}")
            return

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


if __name__ == "__main__":
    main()
