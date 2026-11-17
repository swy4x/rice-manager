import subprocess
import unittest
from unittest.mock import patch

from rice_manager.dependencies import check_dependencies
from rice_manager.manifest import Manifest


def sample_manifest(dependencies):
    return Manifest(
        id="test-rice",
        name="Test Rice",
        version="1.0.0",
        description="Test profile",
        components=(),
        dependencies=tuple(dependencies),
    )


class DependencyTests(unittest.TestCase):
    @patch("rice_manager.dependencies.shutil.which", return_value="/usr/bin/pacman")
    @patch("rice_manager.dependencies.subprocess.run")
    def test_reports_installed_and_missing_packages(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            args=["pacman", "-Q"],
            returncode=0,
            stdout="hyprland 0.57.2-1\nqt6-wayland 6.9.0-1\n",
            stderr="",
        )
        report = check_dependencies(sample_manifest(["hyprland", "qt6-wayland", "waybar"]))
        self.assertEqual(report["status"], "checked")
        self.assertEqual(report["installed"], ["hyprland", "qt6-wayland"])
        self.assertEqual(report["missing"], ["waybar"])
        self.assertEqual(report["dependencies"][2]["status"], "missing")
        self.assertEqual(report["install_command"], "sudo pacman -S --needed waybar")
        run.assert_called_once_with(
            ["/usr/bin/pacman", "-Q"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("rice_manager.dependencies.shutil.which", return_value=None)
    def test_reports_unverified_when_pacman_is_unavailable(self, _which):
        report = check_dependencies(sample_manifest(["hyprland"]))
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["dependencies"], [
            {"name": "hyprland", "status": "unverified"}
        ])
        self.assertIsNone(report["install_command"])

    @patch("rice_manager.dependencies.shutil.which", return_value="/usr/bin/pacman")
    @patch("rice_manager.dependencies.subprocess.run")
    def test_reports_unverified_when_package_query_fails(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            args=["pacman", "-Q"], returncode=1, stdout="", stderr="database error"
        )
        report = check_dependencies(sample_manifest(["hyprland"]))
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["dependencies"][0]["status"], "unverified")

    @patch("rice_manager.dependencies.shutil.which")
    @patch("rice_manager.dependencies.subprocess.run")
    def test_empty_dependency_list_does_not_query_pacman(self, run, which):
        report = check_dependencies(sample_manifest([]))
        self.assertEqual(report["status"], "not-required")
        self.assertEqual(report["dependencies"], [])
        which.assert_not_called()
        run.assert_not_called()

    @patch("rice_manager.dependencies.shutil.which", return_value="/usr/bin/pacman")
    @patch("rice_manager.dependencies.subprocess.run")
    def test_all_installed_has_no_install_command(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            args=["pacman", "-Q"], returncode=0, stdout="hyprland 1.0\n", stderr=""
        )
        report = check_dependencies(sample_manifest(["hyprland"]))
        self.assertEqual(report["missing"], [])
        self.assertIsNone(report["install_command"])


if __name__ == "__main__":
    unittest.main()
