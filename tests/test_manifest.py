import json
import tempfile
import unittest
from pathlib import Path

from rice_manager.manifest import ManifestError, load_manifest, resolve_source


class ManifestTests(unittest.TestCase):
    def write_manifest(self, data):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "manifest.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def valid_data(self):
        return {
            "schema_version": 1,
            "id": "test-rice",
            "name": "Test Rice",
            "version": "1.0.0",
            "description": "Test profile",
            "components": [{
                "id": "hyprland",
                "name": "Hyprland",
                "kind": "config-directory",
                "source": "${XDG_CONFIG_HOME}/hypr",
                "scope": "user",
            }],
        }

    def test_load_valid_manifest(self):
        manifest = load_manifest(self.write_manifest(self.valid_data()))
        self.assertEqual(manifest.id, "test-rice")
        self.assertEqual(manifest.components[0].id, "hyprland")

    def test_reject_duplicate_component_ids(self):
        data = self.valid_data()
        data["components"].append(dict(data["components"][0]))
        with self.assertRaises(ManifestError):
            load_manifest(self.write_manifest(data))

    def test_reject_unknown_variables(self):
        with self.assertRaises(ManifestError):
            resolve_source("${UNSAFE}/config")

    def test_reject_unknown_component_fields(self):
        data = self.valid_data()
        data["components"][0]["command"] = "echo unsafe"
        with self.assertRaises(ManifestError):
            load_manifest(self.write_manifest(data))


if __name__ == "__main__":
    unittest.main()
