"""Command-line interface for Rice Manager."""

from __future__ import annotations

import argparse
import json

from . import __version__
from .system import inspect_system


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
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
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


if __name__ == "__main__":
    main()
