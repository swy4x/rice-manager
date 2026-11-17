import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rice_manager.restore import RestoreError, inspect_backup, restore_backup


class RestoreTests(unittest.TestCase):
    def make_backup(self, base, target):
        backup = base / "backup"
        comp = backup / "components" / "hyprland"
        comp.mkdir(parents=True)
        (comp / "hyprland.conf").write_text("restored", encoding="utf-8")
        (backup / "backup.json").write_text(json.dumps({
            "schema_version": 1, "profile_id": "test-rice",
            "components": [{"component_id": "hyprland", "name": "Hyprland",
                "source": str(target), "backup_path": "components/hyprland",
                "kind": "config-directory"}],
        }), encoding="utf-8")
        return backup

    def test_preview_does_not_change_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; home.mkdir()
            target = home / ".config/hypr"; backup = self.make_backup(base, target)
            with patch("rice_manager.restore.Path.home", return_value=home):
                plan = restore_backup(backup)
            self.assertEqual(len(plan.items), 1)
            self.assertFalse(target.exists())

    def test_apply_restores_missing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; home.mkdir()
            target = home / ".config/hypr"; backup = self.make_backup(base, target)
            with patch("rice_manager.restore.Path.home", return_value=home):
                restore_backup(backup, apply=True)
            self.assertEqual((target / "hyprland.conf").read_text(), "restored")

    def test_existing_destination_is_safety_backed_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; home.mkdir()
            target = home / ".config/hypr"; target.mkdir(parents=True)
            (target / "old.conf").write_text("keep")
            backup = self.make_backup(base, target)
            with patch("rice_manager.restore.Path.home", return_value=home):
                restore_backup(backup, apply=True)
            self.assertTrue((target / "hyprland.conf").exists())
            saved = list((home / ".local/share/rice-manager/backups").glob(
                "pre-restore-*/components/hyprland/old.conf"))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].read_text(), "keep")

    def test_rejects_destination_outside_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; home.mkdir()
            backup = self.make_backup(base, base / "outside/config")
            with patch("rice_manager.restore.Path.home", return_value=home):
                with self.assertRaises(RestoreError):
                    inspect_backup(backup)

    def test_rejects_symlinked_backup_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; home.mkdir()
            backup = self.make_backup(base, home / ".config/hypr")
            linked = base / "backup-link"
            linked.symlink_to(backup, target_is_directory=True)
            with patch("rice_manager.restore.Path.home", return_value=home):
                with self.assertRaises(RestoreError):
                    inspect_backup(linked)

    def test_rejects_symlinked_backup_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; home.mkdir()
            backup = self.make_backup(base, home / ".config/hypr")
            metadata = backup / "backup.json"
            data = metadata.read_text()
            metadata.unlink()
            outside = base / "metadata.json"
            outside.write_text(data)
            metadata.symlink_to(outside)
            with patch("rice_manager.restore.Path.home", return_value=home):
                with self.assertRaises(RestoreError):
                    inspect_backup(backup)

    def test_rejects_symlinked_backup_components_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; home.mkdir()
            backup = self.make_backup(base, home / ".config/hypr")
            components = backup / "components"
            moved = backup / "components-real"
            components.rename(moved)
            components.symlink_to(moved, target_is_directory=True)
            with patch("rice_manager.restore.Path.home", return_value=home):
                with self.assertRaises(RestoreError):
                    inspect_backup(backup)

    def test_rejects_symlinked_destination_parent_inside_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; home.mkdir()
            real_config = home / "real-config"; real_config.mkdir()
            (home / ".config").symlink_to(real_config, target_is_directory=True)
            backup = self.make_backup(base, home / ".config/hypr")
            with patch("rice_manager.restore.Path.home", return_value=home):
                with self.assertRaises(RestoreError):
                    inspect_backup(backup)

    def test_rejects_traversal_backup_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; home.mkdir()
            backup = self.make_backup(base, home / ".config/hypr")
            meta = backup / "backup.json"
            data = json.loads(meta.read_text())
            data["components"][0]["backup_path"] = "../../outside"
            meta.write_text(json.dumps(data))
            with patch("rice_manager.restore.Path.home", return_value=home):
                with self.assertRaises(RestoreError):
                    inspect_backup(backup)


if __name__ == "__main__":
    unittest.main()
