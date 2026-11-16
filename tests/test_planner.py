import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rice_manager.manifest import load_manifest
from rice_manager.planner import build_switch_plan


class SwitchPlannerTests(unittest.TestCase):
    def make_manifest(self, home, components):
        path = home / "manifest.json"
        path.write_text(json.dumps({
            "schema_version": 1, "id": "test-rice", "name": "Test Rice",
            "version": "1.0.0", "description": "Planner test",
            "components": components,
        }), encoding="utf-8")
        return load_manifest(path)

    def component(self, **overrides):
        data = {
            "id": "hyprland", "name": "Hyprland",
            "kind": "config-directory", "source": "${HOME}/.config/hypr",
            "scope": "user", "required": True, "read_only": False,
        }
        data.update(overrides)
        return data

    def test_ready_when_required_directory_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp); (home / ".config/hypr").mkdir(parents=True)
            manifest = self.make_manifest(home, [self.component()])
            with patch("rice_manager.planner.Path.home", return_value=home):
                plan = build_switch_plan(manifest)
            self.assertFalse(plan.blocked)
            self.assertEqual(plan.items[0].status, "ready")

    def test_blocks_missing_required_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp); manifest = self.make_manifest(home, [self.component()])
            with patch("rice_manager.planner.Path.home", return_value=home):
                plan = build_switch_plan(manifest)
            self.assertTrue(plan.blocked)
            self.assertEqual(plan.items[0].status, "blocked-required-missing")

    def test_missing_optional_component_is_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            component = self.component(id="optional", required=False)
            manifest = self.make_manifest(home, [component])
            with patch("rice_manager.planner.Path.home", return_value=home):
                plan = build_switch_plan(manifest)
            self.assertEqual(plan.items[0].status, "missing-optional")
            self.assertFalse((home / ".config/hypr").exists())

    def test_system_component_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            component = self.component(scope="system", source="/etc/xdg/example")
            manifest = self.make_manifest(home, [component])
            with patch("rice_manager.planner.Path.home", return_value=home):
                plan = build_switch_plan(manifest)
            self.assertEqual(plan.items[0].status, "skipped")

    def test_type_mismatch_blocks_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp); (home / ".config").mkdir()
            (home / ".config/hypr").write_text("not a directory")
            manifest = self.make_manifest(home, [self.component()])
            with patch("rice_manager.planner.Path.home", return_value=home):
                plan = build_switch_plan(manifest)
            self.assertEqual(plan.items[0].status, "blocked-type-mismatch")


if __name__ == "__main__":
    unittest.main()
