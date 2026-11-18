import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rice_manager.activation import ActivationError, apply_profile_payload
from rice_manager.manifest import load_manifest


class ActivationTests(unittest.TestCase):
    def make_profile(self, home, *, kind="config-directory", scope="user", payload=True):
        profile = home / "profile"
        if kind == "config-directory":
            payload_root = profile / "payload" / "hypr"
            payload_root.mkdir(parents=True)
            (payload_root / "hyprland.conf").write_text("new config", encoding="utf-8")
        else:
            payload_root = profile / "payload" / "hyprland.conf"
            payload_root.parent.mkdir(parents=True)
            payload_root.write_text("new config", encoding="utf-8")

        component = {
            "id": "hyprland",
            "name": "Hyprland",
            "kind": kind,
            "source": "${HOME}/.config/hypr" if kind == "config-directory" else "${HOME}/.config/hyprland.conf",
            "scope": scope,
            "required": True,
            "read_only": scope == "system",
        }
        if payload:
            component["payload"] = "payload/hypr" if kind == "config-directory" else "payload/hyprland.conf"
        manifest_path = profile / "manifest.json"
        manifest_path.write_text(json.dumps({
            "schema_version": 1,
            "id": "test-rice",
            "name": "Test Rice",
            "version": "1.0.0",
            "description": "Activation test",
            "components": [component],
        }), encoding="utf-8")
        return profile, load_manifest(manifest_path)

    def run_apply(self, home, profile, manifest, *, apply=False):
        with patch("pathlib.Path.home", return_value=home):
            return apply_profile_payload(manifest, profile, apply=apply)

    def test_preview_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.make_profile(home)
            report = self.run_apply(home, profile, manifest)
            self.assertTrue(report["dry_run"])
            self.assertEqual(report["summary"]["ADD"], 1)
            self.assertFalse((home / ".config/hypr").exists())

    def test_apply_adds_payload_and_creates_safety_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.make_profile(home)
            report = self.run_apply(home, profile, manifest, apply=True)
            self.assertFalse(report["dry_run"])
            self.assertEqual(
                (home / ".config/hypr/hyprland.conf").read_text(encoding="utf-8"),
                "new config",
            )
            self.assertTrue(Path(report["safety_backup"]).is_dir())
            metadata = json.loads((Path(report["safety_backup"]) / "apply-safety.json").read_text())
            self.assertEqual(metadata["components"], [])

    def test_apply_replaces_file_and_snapshots_previous_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            destination = home / ".config/hypr"
            destination.mkdir(parents=True)
            (destination / "hyprland.conf").write_text("old config", encoding="utf-8")
            (destination / "extra.conf").write_text("keep me", encoding="utf-8")
            profile, manifest = self.make_profile(home)
            report = self.run_apply(home, profile, manifest, apply=True)
            self.assertEqual((destination / "hyprland.conf").read_text(), "new config")
            self.assertEqual((destination / "extra.conf").read_text(), "keep me")
            metadata = json.loads((Path(report["safety_backup"]) / "apply-safety.json").read_text())
            saved = Path(report["safety_backup"]) / metadata["components"][0]["backup_path"]
            self.assertEqual(saved.read_text(), "old config")

    def test_apply_file_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.make_profile(home, kind="config-file")
            report = self.run_apply(home, profile, manifest)
            self.assertEqual(report["summary"]["ADD"], 1)
            self.run_apply(home, profile, manifest, apply=True)
            self.assertEqual((home / ".config/hyprland.conf").read_text(), "new config")

    def test_conflict_blocks_entire_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            destination = home / ".config/hypr"
            destination.mkdir(parents=True)
            (destination / "hyprland.conf").symlink_to(home / "outside")
            profile, manifest = self.make_profile(home)
            with self.assertRaises(ActivationError):
                self.run_apply(home, profile, manifest, apply=True)
            self.assertTrue((destination / "hyprland.conf").is_symlink())

    def test_system_component_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.make_profile(home, scope="system")
            report = self.run_apply(home, profile, manifest, apply=True)
            self.assertEqual(report["files"], [])
            self.assertFalse((home / ".config/hypr").exists())

    def test_extra_destination_files_are_never_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            destination = home / ".config/hypr"
            destination.mkdir(parents=True)
            (destination / "keep.conf").write_text("untouched")
            profile, manifest = self.make_profile(home)
            self.run_apply(home, profile, manifest, apply=True)
            self.assertEqual((destination / "keep.conf").read_text(), "untouched")

    def test_failed_multi_file_apply_rolls_back_prior_replacements(self):
        import os
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.make_profile(home)
            (profile / "payload/hypr/zzz.conf").write_text("second file", encoding="utf-8")
            destination = home / ".config/hypr"
            destination.mkdir(parents=True)
            (destination / "hyprland.conf").write_text("original", encoding="utf-8")

            real_replace = os.replace
            calls = {"count": 0}

            def fail_second_replace(source, target):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("simulated installation failure")
                return real_replace(source, target)

            with patch("rice_manager.activation.os.replace", side_effect=fail_second_replace):
                with self.assertRaises(ActivationError):
                    self.run_apply(home, profile, manifest, apply=True)

            self.assertEqual((destination / "hyprland.conf").read_text(), "original")
            self.assertFalse((destination / "zzz.conf").exists())

    def test_payload_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.make_profile(home)
            payload_file = profile / "payload/hypr/hyprland.conf"
            payload_file.unlink()
            payload_file.symlink_to(home / "outside")
            with self.assertRaises(ActivationError):
                self.run_apply(home, profile, manifest, apply=True)


    def test_rollback_refuses_symlinked_destination_parent(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.make_profile(home)
            (profile / "payload/hypr/zzz.conf").write_text(
                "second file", encoding="utf-8"
            )

            destination = home / ".config" / "hypr"
            destination.mkdir(parents=True)
            original = destination / "hyprland.conf"
            original.write_text("original", encoding="utf-8")

            outside = home / "outside"
            outside.mkdir()

            real_replace = os.replace
            calls = {"count": 0}

            def change_parent_then_fail(source, target):
                calls["count"] += 1
                if calls["count"] == 2:
                    detached = home / "detached"
                    destination.rename(detached)
                    destination.symlink_to(
                        outside, target_is_directory=True
                    )
                    raise OSError("simulated installation failure")
                return real_replace(source, target)

            with patch(
                "rice_manager.activation.os.replace",
                side_effect=change_parent_then_fail,
            ):
                with self.assertRaises(ActivationError):
                    self.run_apply(home, profile, manifest, apply=True)

            self.assertTrue(destination.is_symlink())
            self.assertFalse((outside / "hyprland.conf").exists())


    def test_payload_replaced_with_symlink_during_staging_is_rejected(self):
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile, manifest = self.make_profile(home)
            payload_file = profile / "payload/hypr/hyprland.conf"
            outside = home / "outside"
            outside.write_text("outside secret", encoding="utf-8")

            real_copy2 = shutil.copy2
            calls = {"count": 0}

            def replace_source_during_staging(source, destination, *, follow_symlinks=True):
                if Path(source) == payload_file:
                    calls["count"] += 1
                    if calls["count"] == 1:
                        payload_file.unlink()
                        payload_file.symlink_to(outside)
                return real_copy2(source, destination, follow_symlinks=follow_symlinks)

            with patch("rice_manager.activation.shutil.copy2", side_effect=replace_source_during_staging):
                with self.assertRaises(ActivationError):
                    self.run_apply(home, profile, manifest, apply=True)

            installed = home / ".config/hypr/hyprland.conf"
            self.assertFalse(installed.is_symlink())
            self.assertFalse(installed.exists())


    def test_installed_signature_is_captured_before_replace(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            destination = home / ".config" / "hypr"
            destination.mkdir(parents=True)
            target = destination / "hyprland.conf"
            target.write_text("original", encoding="utf-8")

            profile, manifest = self.make_profile(home)

            real_replace = os.replace
            real_stat = Path.stat
            replaced = {"value": False}
            failed = {"value": False}

            def replace_then_mark(source, dest):
                result = real_replace(source, dest)
                if Path(dest) == target:
                    replaced["value"] = True
                return result

            def fail_installed_stat(path, *args, **kwargs):
                if path == target and replaced["value"] and not failed["value"]:
                    failed["value"] = True
                    raise OSError("simulated metadata failure")
                return real_stat(path, *args, **kwargs)

            with patch(
                "rice_manager.activation.os.replace",
                side_effect=replace_then_mark,
            ), patch(
                "rice_manager.activation.Path.stat",
                autospec=True,
                side_effect=fail_installed_stat,
            ):
                report = self.run_apply(home, profile, manifest, apply=True)

            self.assertTrue(report["applied"])
            self.assertEqual(target.read_text(encoding="utf-8"), "new config")
            self.assertFalse(failed["value"])


if __name__ == "__main__":
    unittest.main()
