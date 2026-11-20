
import io
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from rice_manager.github_install import (
    GitHubInstallError,
    prepare_github_shell,
    preview_github_install,
    install_github_shell,
    delete_github_shell,
)


class GitHubInstallTests(unittest.TestCase):
    def make_archive(self, files):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, content in files.items():
                archive.writestr(f"rice-main/{name}", content)
        return buffer.getvalue()

    def report(self):
        return {
            "compatibility": {
                "status": "compatible",
                "reason": "Quickshell entrypoint detected.",
            },
            "repository": {
                "name": "example/rice",
                "url": "https://github.com/example/rice",
                "branch": "main",
            },
            "components": [{
                "id": "quickshell",
                "source_root": ".config/quickshell",
                "entrypoint": "shell.qml",
            }],
            "summary": {
                "unsafe_entries": 0,
                "oversized_entries": 0,
                "scripts_flagged": 0,
            },
        }

    def prepare(self, root, files):
        archive = self.make_archive(files)

        with patch(
            "rice_manager.github_install.scan_github_repository",
            return_value=self.report(),
        ), patch(
            "rice_manager.github_install._download_to_tempfile",
            return_value=io.BytesIO(archive),
        ):
            return prepare_github_shell(
                "https://github.com/example/rice",
                root / "staging",
            )

    def test_stages_quickshell_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.prepare(root, {
                ".config/quickshell/shell.qml": "import QtQuick\nItem {}",
                ".config/quickshell/modules/bar.qml": "Item {}",
            })

            staged = Path(result["staging_path"])

            self.assertTrue((staged / "shell.qml").is_file())
            self.assertTrue((staged / "modules/bar.qml").is_file())
            self.assertEqual(result["file_count"], 2)
            self.assertTrue(result["dry_run"])
            self.assertFalse(result["installation_performed"])

    def test_stages_nested_entrypoint_and_previews_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self.report()
            report["components"][0]["entrypoint"] = "ii/shell.qml"

            archive = self.make_archive({
                ".config/quickshell/ii/shell.qml": "Item {}",
                ".config/quickshell/ii/modules/bar.qml": "Item {}",
            })

            with patch(
                "rice_manager.github_install.scan_github_repository",
                return_value=report,
            ), patch(
                "rice_manager.github_install._download_to_tempfile",
                return_value=io.BytesIO(archive),
            ):
                result = prepare_github_shell(
                    "https://github.com/example/rice",
                    root / "staging",
                )

            staged = Path(result["staging_path"])
            self.assertEqual(result["entrypoint"], "ii/shell.qml")
            self.assertTrue((staged / "ii/shell.qml").is_file())
            self.assertTrue((staged / "ii/modules/bar.qml").is_file())

            preview = preview_github_install(
                result["staging_path"],
                root / "config",
            )
            self.assertEqual(preview["entrypoint"], "ii/shell.qml")
            self.assertEqual(
                {item["path"] for item in preview["files"]},
                {"ii/shell.qml", "ii/modules/bar.qml"},
            )

    def test_skips_oversized_optional_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            with patch("rice_manager.github_install.MAX_FILE_BYTES", 20):
                result = self.prepare(root, {
                    ".config/quickshell/shell.qml": "Item {}",
                    ".config/quickshell/wallpaper.bin": "x" * 21,
                })

                self.assertEqual(
                    result["skipped_oversized"],
                    ["wallpaper.bin"],
                )
                self.assertTrue(
                    (Path(result["staging_path"]) / "shell.qml").is_file()
                )
                self.assertFalse(
                    (Path(result["staging_path"]) / "wallpaper.bin").exists()
                )

                preview = preview_github_install(
                    result["staging_path"],
                    root / "config",
                )
                self.assertEqual(
                    preview["skipped_oversized"],
                    ["wallpaper.bin"],
                )
                self.assertEqual(preview["file_count"], 1)

    def test_multiple_quickshell_roots_stage_independently_with_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self.report()
            report["configurations"] = [
                {
                    "id": "quickshell",
                    "source_root": ".config/quickshell/alpha",
                    "entrypoint": "shell.qml",
                    "compatibility": "compatible",
                },
                {
                    "id": "quickshell",
                    "source_root": ".config/quickshell/beta",
                    "entrypoint": "shell.qml",
                    "compatibility": "compatible",
                },
            ]
            archive = self.make_archive({
                ".config/quickshell/alpha/shell.qml": "Alpha {}",
                ".config/quickshell/beta/shell.qml": "Beta {}",
            })
            updates = []

            with patch(
                "rice_manager.github_install.scan_github_repository",
                return_value=report,
            ), patch(
                "rice_manager.github_install._download_to_tempfile",
                return_value=io.BytesIO(archive),
            ):
                alpha = prepare_github_shell(
                    "https://github.com/example/rice",
                    root / "staging",
                    source_root=".config/quickshell/alpha",
                    progress_callback=lambda *event: updates.append(event),
                )

            with patch(
                "rice_manager.github_install.scan_github_repository",
                return_value=report,
            ), patch(
                "rice_manager.github_install._download_to_tempfile",
                return_value=io.BytesIO(archive),
            ):
                beta = prepare_github_shell(
                    "https://github.com/example/rice",
                    root / "staging",
                    source_root=".config/quickshell/beta",
                )

            self.assertNotEqual(alpha["stage_id"], beta["stage_id"])
            self.assertEqual(
                (Path(alpha["staging_path"]) / "shell.qml").read_text(),
                "Alpha {}",
            )
            self.assertEqual(
                (Path(beta["staging_path"]) / "shell.qml").read_text(),
                "Beta {}",
            )
            self.assertTrue(any(event[0] == "extract" for event in updates))

    def test_preview_does_not_install_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.prepare(root, {
                ".config/quickshell/shell.qml": "Item {}",
            })

            config_home = root / "config"
            preview = preview_github_install(
                result["staging_path"],
                config_home,
            )

            self.assertTrue(preview["dry_run"])
            self.assertFalse(preview["installation_performed"])
            self.assertFalse(Path(preview["destination"]).exists())
            self.assertEqual(preview["file_count"], 1)

    def test_rejects_archive_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            with self.assertRaises(GitHubInstallError):
                self.prepare(root, {
                    ".config/quickshell/shell.qml": "Item {}",
                    "../outside.txt": "unsafe",
                })

    def test_rejects_repository_without_entrypoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self.report()
            report["components"][0]["entrypoint"] = None
            report["compatibility"]["status"] = "partial"

            with patch(
                "rice_manager.github_install.scan_github_repository",
                return_value=report,
            ):
                with self.assertRaises(GitHubInstallError):
                    prepare_github_shell(
                        "https://github.com/example/rice",
                        root / "staging",
                    )

    def test_rejects_existing_staging_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging_root = root / "staging"
            staging_root.mkdir()
            existing = staging_root / "rice-"
            existing.mkdir()

            # A separate test below covers destination collisions using
            # the deterministic stage ID generated by the installer.
            result = self.prepare(root, {
                ".config/quickshell/shell.qml": "Item {}",
            })
            self.assertTrue(Path(result["staging_path"]).is_dir())


    def test_preview_rejects_modified_staged_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.prepare(root, {
                ".config/quickshell/shell.qml": "Item {}",
            })

            staged = Path(result["staging_path"])
            (staged / "shell.qml").write_text("Modified content")

            with self.assertRaises(GitHubInstallError):
                preview_github_install(staged, root / "config")

    def test_preview_rejects_unexpected_staged_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.prepare(root, {
                ".config/quickshell/shell.qml": "Item {}",
            })

            staged = Path(result["staging_path"])
            (staged / "unexpected.qml").write_text("Item {}")

            with self.assertRaises(GitHubInstallError):
                preview_github_install(staged, root / "config")

    def test_preview_rejects_missing_staged_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.prepare(root, {
                ".config/quickshell/shell.qml": "Item {}",
                ".config/quickshell/modules/bar.qml": "Item {}",
            })

            staged = Path(result["staging_path"])
            (staged / "modules/bar.qml").unlink()

            with self.assertRaises(GitHubInstallError):
                preview_github_install(staged, root / "config")


    def test_install_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.prepare(root, {
                ".config/quickshell/shell.qml": "Item {}",
            })

            with self.assertRaises(GitHubInstallError):
                install_github_shell(
                    result["staging_path"],
                    root / "config",
                )

    def test_install_copies_and_registers_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_home = root / "config"
            data_home = root / "data"
            result = self.prepare(root, {
                ".config/quickshell/shell.qml": "Item {}",
                ".config/quickshell/modules/bar.qml": "Item {}",
            })

            with patch.dict("os.environ", {
                "XDG_CONFIG_HOME": str(config_home),
                "XDG_DATA_HOME": str(data_home),
            }):
                installed = install_github_shell(
                    result["staging_path"],
                    config_home,
                    confirm=True,
                )

            destination = Path(installed["destination"])
            self.assertTrue(installed["installation_performed"])
            self.assertTrue(installed["registered"])
            self.assertTrue((destination / "shell.qml").is_file())
            self.assertTrue((destination / "modules/bar.qml").is_file())
            self.assertTrue(
                (data_home / "rice-manager" / "installed-shells.json").is_file()
            )

    def test_install_rolls_back_when_registration_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_home = root / "config"
            result = self.prepare(root, {
                ".config/quickshell/shell.qml": "Item {}",
            })

            with patch(
                "rice_manager.github_install.register_installed_shell",
                side_effect=RuntimeError("simulated registry failure"),
            ):
                with self.assertRaises(GitHubInstallError):
                    install_github_shell(
                        result["staging_path"],
                        config_home,
                        confirm=True,
                    )

            destination = (
                config_home / "quickshell" / Path(result["staging_path"]).name
            )
            self.assertFalse(destination.exists())


    def test_install_rejects_file_changed_after_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_home = root / "config"
            result = self.prepare(root, {
                ".config/quickshell/shell.qml": "Original {}",
            })

            from rice_manager.github_install import preview_github_install

            def tampered_preview(*args, **kwargs):
                preview = preview_github_install(*args, **kwargs)
                (Path(preview["source"]) / "shell.qml").write_text("Tampered {}")
                return preview

            with patch(
                "rice_manager.github_install.preview_github_install",
                side_effect=tampered_preview,
            ):
                with self.assertRaises(GitHubInstallError):
                    install_github_shell(
                        result["staging_path"],
                        config_home,
                        confirm=True,
                    )

            destination = (
                config_home / "quickshell" / Path(result["staging_path"]).name
            )
            self.assertFalse(destination.exists())


    def install_for_deletion(self, root):
        config_home = root / "config"
        data_home = root / "data"
        staged = self.prepare(root, {
            ".config/quickshell/shell.qml": "Item {}",
        })

        with patch.dict("os.environ", {
            "XDG_CONFIG_HOME": str(config_home),
            "XDG_DATA_HOME": str(data_home),
        }):
            installed = install_github_shell(
                staged["staging_path"],
                config_home,
                confirm=True,
            )

        return installed, config_home, data_home

    def test_delete_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            installed, config_home, data_home = self.install_for_deletion(root)

            with patch.dict("os.environ", {
                "XDG_CONFIG_HOME": str(config_home),
                "XDG_DATA_HOME": str(data_home),
            }):
                with self.assertRaises(GitHubInstallError):
                    delete_github_shell(installed["stage_id"])

            self.assertTrue(Path(installed["destination"]).is_dir())

    def test_delete_removes_installation_and_registry_entry(self):
        from rice_manager.shell_registry import load_installed_shells

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            installed, config_home, data_home = self.install_for_deletion(root)

            with patch.dict("os.environ", {
                "XDG_CONFIG_HOME": str(config_home),
                "XDG_DATA_HOME": str(data_home),
            }), patch(
                "rice_manager.shell_switch._running_shells",
                return_value={installed["stage_id"]: []},
            ):
                result = delete_github_shell(
                    installed["stage_id"],
                    confirm=True,
                )
                self.assertEqual(load_installed_shells(), {})

            self.assertTrue(result["deleted"])
            self.assertFalse(Path(installed["destination"]).exists())

    def test_delete_rolls_back_when_registry_update_fails(self):
        from rice_manager.shell_registry import ShellRegistryError

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            installed, config_home, data_home = self.install_for_deletion(root)

            with patch.dict("os.environ", {
                "XDG_CONFIG_HOME": str(config_home),
                "XDG_DATA_HOME": str(data_home),
            }), patch(
                "rice_manager.shell_switch._running_shells",
                return_value={installed["stage_id"]: []},
            ), patch(
                "rice_manager.github_install.unregister_installed_shell",
                side_effect=ShellRegistryError("simulated failure"),
            ):
                with self.assertRaises(GitHubInstallError):
                    delete_github_shell(
                        installed["stage_id"],
                        confirm=True,
                    )

            self.assertTrue(Path(installed["destination"]).is_dir())

    def test_delete_refuses_running_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            installed, config_home, data_home = self.install_for_deletion(root)

            with patch.dict("os.environ", {
                "XDG_CONFIG_HOME": str(config_home),
                "XDG_DATA_HOME": str(data_home),
            }), patch(
                "rice_manager.shell_switch._running_shells",
                return_value={
                    installed["stage_id"]: [{"id": "running-instance"}]
                },
            ):
                with self.assertRaisesRegex(
                    GitHubInstallError, "while it is running"
                ):
                    delete_github_shell(
                        installed["stage_id"],
                        confirm=True,
                    )

            self.assertTrue(Path(installed["destination"]).is_dir())

    def test_delete_refuses_builtin_shell(self):
        with self.assertRaises(GitHubInstallError):
            delete_github_shell("cartoon-shell", confirm=True)

        with self.assertRaises(GitHubInstallError):
            delete_github_shell("caelestia", confirm=True)


    def _make_symlink_test_archive(self, links):
        buffer = io.BytesIO()
        unsafe = []

        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "rice-main/.config/quickshell/shell.qml", "Item {}"
            )
            archive.writestr(
                "rice-main/.config/quickshell/assets/target.svg", "<svg/>"
            )

            for name, target in links.items():
                archive_name = (
                    "rice-main/.config/quickshell/assets/" + name
                )
                info = zipfile.ZipInfo(archive_name)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, target)
                unsafe.append(archive_name)

        report = self.report()
        report["summary"]["unsafe_entries"] = len(unsafe)
        report["unsafe_entries"] = unsafe

        return buffer.getvalue(), report

    def test_internal_relative_symlink_is_staged_as_regular_file(self):
        archive, report = self._make_symlink_test_archive({
            "alias.svg": "target.svg",
        })

        with tempfile.TemporaryDirectory() as temp:
            with patch(
                "rice_manager.github_install.scan_github_repository",
                return_value=report,
            ), patch(
                "rice_manager.github_install._download_to_tempfile",
                return_value=io.BytesIO(archive),
            ):
                result = prepare_github_shell(
                    "https://github.com/example/dots",
                    Path(temp) / "staging",
                )

            alias = Path(result["staging_path"]) / "assets/alias.svg"
            self.assertTrue(alias.is_file())
            self.assertFalse(alias.is_symlink())
            self.assertEqual(alias.read_text(), "<svg/>")

    def test_symlink_escaping_quickshell_root_is_rejected(self):
        archive, report = self._make_symlink_test_archive({
            "escape.svg": "../../../../outside.svg",
        })

        with tempfile.TemporaryDirectory() as temp:
            with patch(
                "rice_manager.github_install.scan_github_repository",
                return_value=report,
            ), patch(
                "rice_manager.github_install._download_to_tempfile",
                return_value=io.BytesIO(archive),
            ):
                with self.assertRaises(GitHubInstallError):
                    prepare_github_shell(
                        "https://github.com/example/dots",
                        Path(temp) / "staging",
                    )

    def test_chained_symlinks_are_rejected(self):
        archive, report = self._make_symlink_test_archive({
            "alias.svg": "other.svg",
            "other.svg": "target.svg",
        })

        with tempfile.TemporaryDirectory() as temp:
            with patch(
                "rice_manager.github_install.scan_github_repository",
                return_value=report,
            ), patch(
                "rice_manager.github_install._download_to_tempfile",
                return_value=io.BytesIO(archive),
            ):
                with self.assertRaises(GitHubInstallError):
                    prepare_github_shell(
                        "https://github.com/example/dots",
                        Path(temp) / "staging",
                    )


if __name__ == "__main__":
    unittest.main()
