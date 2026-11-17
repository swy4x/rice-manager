import json
import tempfile
import unittest
from pathlib import Path

from rice_manager.profiles import ProfileDiscoveryError, discover_profiles


class ProfileDiscoveryTests(unittest.TestCase):
    def make_manifest(self, directory, profile_id, name):
        profile_dir = directory / profile_id
        profile_dir.mkdir()
        data = {
            "schema_version": 1,
            "id": profile_id,
            "name": name,
            "version": "1.0.0",
            "description": "Test profile",
            "components": [{
                "id": "hyprland",
                "name": "Hyprland",
                "kind": "config-directory",
                "source": "${HOME}/.config/hypr",
                "scope": "user",
            }],
        }
        (profile_dir / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
        return profile_dir

    def test_discovers_multiple_profiles_in_name_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_manifest(root, "zeta", "Zeta")
            self.make_manifest(root, "alpha", "Alpha")

            result = discover_profiles(root)

        self.assertEqual([item["id"] for item in result], ["alpha", "zeta"])
        self.assertTrue(all(item["valid"] for item in result))
        self.assertEqual(result[0]["component_count"], 1)
        self.assertIn("summary", result[0])

    def test_reports_invalid_manifest_without_aborting_discovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_manifest(root, "valid", "Valid")
            invalid = root / "broken"
            invalid.mkdir()
            (invalid / "manifest.json").write_text("{", encoding="utf-8")

            result = discover_profiles(root)

        self.assertEqual(len(result), 2)
        by_directory = {
            Path(item["manifest"]).parent.name: item
            for item in result
        }
        self.assertTrue(by_directory["valid"]["valid"])
        self.assertFalse(by_directory["broken"]["valid"])
        self.assertIn("error", by_directory["broken"])

    def test_rejects_missing_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing"
            with self.assertRaises(ProfileDiscoveryError):
                discover_profiles(missing)


if __name__ == "__main__":
    unittest.main()
