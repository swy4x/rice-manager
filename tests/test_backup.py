import json
import tempfile
import unittest
from pathlib import Path

from rice_manager.backup import BackupError, create_backup
from rice_manager.manifest import Component, Manifest


class BackupTests(unittest.TestCase):
    def make_manifest(self, user_source, system_source):
        return Manifest(
            id="test-rice",
            name="Test Rice",
            version="1.0.0",
            description="Test profile",
            components=(
                Component("hyprland", "Hyprland", "config-directory", str(user_source), "user", True),
                Component("system-theme", "System theme", "config-directory", str(system_source), "system", False, True),
            ),
        )

    def test_backup_copies_user_component_and_skips_system(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "config" / "hypr"
            source.mkdir(parents=True)
            (source / "hyprland.conf").write_text("general {}", encoding="utf-8")
            system = base / "system"
            system.mkdir()
            (system / "theme.conf").write_text("untouched", encoding="utf-8")

            result = create_backup(self.make_manifest(source, system), base / "backups")
            saved = result / "components" / "hyprland" / "hyprland.conf"
            metadata = json.loads((result / "backup.json").read_text(encoding="utf-8"))

            self.assertEqual(saved.read_text(encoding="utf-8"), "general {}")
            self.assertEqual(len(metadata["components"]), 1)
            self.assertEqual(metadata["components"][0]["component_id"], "hyprland")
            self.assertFalse((result / "components" / "system-theme").exists())

    def test_required_missing_component_aborts(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            missing = base / "missing"
            system = base / "system"
            system.mkdir()
            with self.assertRaises(BackupError):
                create_backup(self.make_manifest(missing, system), base / "backups")

    def test_rejects_symlinked_backup_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "config" / "hypr"
            source.mkdir(parents=True)
            (source / "hyprland.conf").write_text("general {}")
            system = base / "system"
            system.mkdir()
            real_backups = base / "real-backups"
            real_backups.mkdir()
            linked_backups = base / "linked-backups"
            linked_backups.symlink_to(real_backups, target_is_directory=True)
            with self.assertRaises(BackupError):
                create_backup(self.make_manifest(source, system), linked_backups)

    def test_rejects_symlinked_component_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            real_config = base / "real-config"
            (real_config / "hypr").mkdir(parents=True)
            (real_config / "hypr/hyprland.conf").write_text("general {}")
            linked_config = base / ".config"
            linked_config.symlink_to(real_config, target_is_directory=True)
            system = base / "system"
            system.mkdir()
            with self.assertRaises(BackupError):
                create_backup(self.make_manifest(linked_config / "hypr", system), base / "backups")

    def test_no_user_components_aborts(self):
        manifest = Manifest(
            id="system-only", name="System only", version="1", description="",
            components=(Component("sys", "System", "config-directory", "/tmp", "system"),),
        )
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(BackupError):
                create_backup(manifest, Path(temp) / "backups")


if __name__ == "__main__":
    unittest.main()
