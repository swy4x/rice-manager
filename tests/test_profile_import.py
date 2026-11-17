import json
import tempfile
import unittest
from pathlib import Path

from rice_manager.profile_import import (
    ProfileImportError,
    import_profile,
    preview_profile_import,
)


class ProfileImportTests(unittest.TestCase):
    def make_profile(self, root, profile_id="test-rice"):
        source = root / "source"
        source.mkdir()
        data = {
            "schema_version": 1,
            "id": profile_id,
            "name": "Test Rice",
            "version": "1.0.0",
            "description": "Local test profile",
            "components": [{
                "id": "hyprland",
                "name": "Hyprland",
                "kind": "config-directory",
                "source": "${HOME}/.config/hypr",
                "scope": "user",
            }],
        }
        (source / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
        payload = source / "payload" / "hypr"
        payload.mkdir(parents=True)
        (payload / "hyprland.conf").write_text("general {}", encoding="utf-8")
        return source

    def test_preview_lists_files_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_profile(root)
            library = root / "library"
            result = preview_profile_import(source, library)
            self.assertEqual(result["profile_id"], "test-rice")
            self.assertEqual(result["file_count"], 2)
            self.assertTrue(result["dry_run"])
            self.assertFalse(library.exists())

    def test_apply_copies_profile_into_library(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_profile(root)
            library = root / "library"
            destination = import_profile(source, library)
            self.assertEqual((destination / "manifest.json").read_text(), (source / "manifest.json").read_text())
            self.assertEqual((destination / "payload" / "hypr" / "hyprland.conf").read_text(), "general {}")

    def test_existing_profile_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_profile(root)
            library = root / "library"
            (library / "test-rice").mkdir(parents=True)
            marker = library / "test-rice" / "keep.txt"
            marker.write_text("keep")
            with self.assertRaises(ProfileImportError):
                import_profile(source, library)
            self.assertEqual(marker.read_text(), "keep")

    def test_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_profile(root)
            (source / "escape").symlink_to(root / "outside")
            with self.assertRaises(ProfileImportError):
                preview_profile_import(source, root / "library")

    def test_invalid_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_profile(root)
            (source / "manifest.json").write_text("{", encoding="utf-8")
            with self.assertRaises(ProfileImportError):
                preview_profile_import(source, root / "library")


if __name__ == "__main__":
    unittest.main()
