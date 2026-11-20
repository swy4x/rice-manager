import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rice_manager.shell_registry import (
    ShellRegistryError,
    load_installed_shells,
    register_installed_shell,
)


class ShellRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "config"
        self.data = self.root / "data"
        self.shell_dir = self.config / "quickshell" / "test-shell"
        self.shell_dir.mkdir(parents=True)
        self.entrypoint = self.shell_dir / "shell.qml"
        self.entrypoint.write_text("Item {}", encoding="utf-8")

        self.env = patch.dict(os.environ, {
            "XDG_CONFIG_HOME": str(self.config),
            "XDG_DATA_HOME": str(self.data),
        })
        self.env.start()

        self.record = {
            "id": "test-shell",
            "name": "Test Shell",
            "path": str(self.entrypoint),
            "repository": "https://github.com/example/test-shell",
        }

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_registry_starts_empty(self):
        self.assertEqual(load_installed_shells(), {})

    def test_register_and_load_shell(self):
        register_installed_shell(self.record)

        result = load_installed_shells()

        self.assertIn("test-shell", result)
        self.assertEqual(result["test-shell"]["name"], "Test Shell")
        self.assertEqual(result["test-shell"]["path"], self.entrypoint)

    def test_rejects_reserved_shell_id(self):
        record = dict(self.record, id="caelestia")

        with self.assertRaises(ShellRegistryError):
            register_installed_shell(record)

    def test_rejects_invalid_shell_id(self):
        record = dict(self.record, id="../unsafe")

        with self.assertRaises(ShellRegistryError):
            register_installed_shell(record)

    def test_rejects_path_outside_quickshell(self):
        outside = self.root / "outside.qml"
        outside.write_text("Item {}")
        record = dict(self.record, path=str(outside))

        with self.assertRaises(ShellRegistryError):
            register_installed_shell(record)

    def test_rejects_missing_entrypoint(self):
        self.entrypoint.unlink()

        with self.assertRaises(ShellRegistryError):
            register_installed_shell(self.record)

    def test_rejects_duplicate_registration(self):
        register_installed_shell(self.record)

        with self.assertRaises(ShellRegistryError):
            register_installed_shell(self.record)

    def test_rejects_symlinked_registry(self):
        registry_dir = self.data / "rice-manager"
        registry_dir.mkdir(parents=True)
        outside = self.root / "outside.json"
        outside.write_text('{"schema_version": 1, "shells": []}')
        registry = registry_dir / "installed-shells.json"
        registry.symlink_to(outside)

        with self.assertRaises(ShellRegistryError):
            load_installed_shells()

    def test_registry_file_has_expected_schema(self):
        register_installed_shell(self.record)

        registry = (
            self.data / "rice-manager" / "installed-shells.json"
        )
        data = json.loads(registry.read_text())

        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(len(data["shells"]), 1)


if __name__ == "__main__":
    unittest.main()
