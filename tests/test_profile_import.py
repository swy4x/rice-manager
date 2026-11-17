import json
import tempfile
import unittest
from pathlib import Path

from rice_manager.profile_import import (
    ProfileImportError,
    import_profile,
    preview_profile_import,
    remove_imported_profile,
    preview_profile_removal,
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

    def test_remove_preview_does_not_delete_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_profile(root)
            library = root / "library"
            destination = import_profile(source, library)
            result = preview_profile_removal("test-rice", library)
            self.assertTrue(result["dry_run"])
            self.assertFalse(result["removed"])
            self.assertEqual(result["profile_name"], "Test Rice")
            self.assertTrue(destination.exists())

    def test_remove_deletes_only_validated_library_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_profile(root)
            library = root / "library"
            destination = import_profile(source, library)
            removed = remove_imported_profile("test-rice", library)
            self.assertEqual(removed, destination)
            self.assertFalse(destination.exists())

    def test_remove_rejects_path_traversal_profile_id(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ProfileImportError):
                remove_imported_profile("../outside", Path(temp))

    def test_remove_rejects_symlinked_profile_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library = root / "library"
            library.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (outside / "keep.txt").write_text("keep", encoding="utf-8")
            (library / "test-rice").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ProfileImportError):
                remove_imported_profile("test-rice", library)
            self.assertEqual((outside / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_remove_rejects_manifest_id_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_profile(root)
            library = root / "library"
            destination = import_profile(source, library)
            manifest_path = destination / "manifest.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["id"] = "other-rice"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ProfileImportError):
                remove_imported_profile("test-rice", library)
            self.assertTrue(destination.exists())

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
