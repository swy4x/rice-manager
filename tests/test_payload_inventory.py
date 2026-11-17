import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rice_manager.manifest import load_manifest
from rice_manager.payload_inventory import build_payload_inventory


class PayloadInventoryTests(unittest.TestCase):
    def setup_profile(self, home, component_overrides=None):
        profile = home / "profile"
        (profile / "payload" / "hypr").mkdir(parents=True)
        (profile / "payload" / "hypr" / "hyprland.conf").write_text("new config")
        component = {
            "id": "hyprland", "name": "Hyprland",
            "kind": "config-directory", "source": "${HOME}/.config/hypr",
            "scope": "user", "required": True, "read_only": False,
            "payload": "payload/hypr",
        }
        component.update(component_overrides or {})
        manifest_path = profile / "manifest.json"
        manifest_path.write_text(json.dumps({
            "schema_version": 1, "id": "test-rice", "name": "Test Rice",
            "version": "1.0.0", "description": "Inventory test",
            "components": [component],
        }))
        return profile, load_manifest(manifest_path)

    def inventory(self, home, profile, manifest):
        with patch("rice_manager.manifest.Path.home", return_value=home):
            return build_payload_inventory(manifest, profile)

    def test_missing_destination_file_is_add(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.setup_profile(home)
            report = self.inventory(home, profile, manifest)
            self.assertEqual(report["summary"]["ADD"], 1)
            self.assertEqual(report["components"][0]["files"][0]["action"], "ADD")
            self.assertTrue(report["dry_run"])

    def test_different_destination_file_is_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            destination = home / ".config/hypr"
            destination.mkdir(parents=True)
            (destination / "hyprland.conf").write_text("old config")
            profile, manifest = self.setup_profile(home)
            report = self.inventory(home, profile, manifest)
            self.assertEqual(report["summary"]["REPLACE"], 1)
            self.assertEqual((destination / "hyprland.conf").read_text(), "old config")

    def test_matching_destination_file_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            destination = home / ".config/hypr"
            destination.mkdir(parents=True)
            (destination / "hyprland.conf").write_text("new config")
            profile, manifest = self.setup_profile(home)
            report = self.inventory(home, profile, manifest)
            self.assertEqual(report["summary"]["UNCHANGED"], 1)

    def test_destination_symlink_is_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            destination = home / ".config/hypr"
            destination.mkdir(parents=True)
            outside = home / "outside"
            outside.write_text("untouched")
            (destination / "hyprland.conf").symlink_to(outside)
            profile, manifest = self.setup_profile(home)
            report = self.inventory(home, profile, manifest)
            self.assertEqual(report["summary"]["CONFLICT"], 1)
            self.assertEqual(outside.read_text(), "untouched")

    def test_payload_symlink_blocks_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.setup_profile(home)
            payload_file = profile / "payload/hypr/hyprland.conf"
            payload_file.unlink()
            payload_file.symlink_to(home / "secret")
            report = self.inventory(home, profile, manifest)
            self.assertEqual(report["components"][0]["status"], "BLOCKED")

    def test_system_component_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.setup_profile(home, {
                "scope": "system", "source": "/etc/xdg/example",
            })
            report = self.inventory(home, profile, manifest)
            self.assertEqual(report["components"][0]["status"], "SKIPPED_PROTECTED")

    def test_legacy_component_without_payload_is_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.setup_profile(home)
            raw = json.loads((profile / "manifest.json").read_text())
            del raw["components"][0]["payload"]
            (profile / "manifest.json").write_text(json.dumps(raw))
            manifest = load_manifest(profile / "manifest.json")
            report = self.inventory(home, profile, manifest)
            self.assertEqual(report["components"][0]["status"], "NO_PAYLOAD")


if __name__ == "__main__":
    unittest.main()
