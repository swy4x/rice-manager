import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rice_manager import shell_switch


class DynamicShellTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.shell_dir = self.root / "quickshell" / "test-shell"
        self.shell_dir.mkdir(parents=True)
        self.entrypoint = self.shell_dir / "shell.qml"
        self.entrypoint.write_text("Item {}", encoding="utf-8")

        self.config = {
            "name": "Test Shell",
            "path": self.entrypoint,
            "repository": "https://github.com/example/test-shell",
            "type": "quickshell",
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_running_shells_discovers_dynamic_shell(self):
        instance = {
            "id": "test-instance",
            "config_path": str(self.entrypoint),
        }

        with (
            patch.object(shell_switch, "_shells", return_value={
                "test-shell": self.config,
            }),
            patch.object(shell_switch, "_instances", return_value=[instance]),
        ):
            result = shell_switch._running_shells()

        self.assertEqual(result["test-shell"], [instance])

    @patch.object(shell_switch.shutil, "which", return_value="/usr/bin/qs")
    @patch.object(shell_switch.subprocess, "Popen")
    @patch.object(shell_switch, "_shells")
    def test_dynamic_shell_starts_with_quickshell_path(
        self, mock_shells, mock_popen, mock_which
    ):
        mock_shells.return_value = {"test-shell": self.config}

        shell_switch._start_shell("test-shell")

        command = mock_popen.call_args.args[0]
        self.assertEqual(command, [
            "/usr/bin/qs",
            "--path", str(self.shell_dir),
            "--daemonize",
            "--no-duplicate",
        ])

    @patch.object(shell_switch.shutil, "which", return_value="/usr/bin/qs")
    @patch.object(shell_switch.subprocess, "run")
    @patch.object(shell_switch, "_shells")
    def test_dynamic_shell_stops_only_its_instance(
        self, mock_shells, mock_run, mock_which
    ):
        mock_shells.return_value = {"test-shell": self.config}
        mock_run.return_value.returncode = 0

        shell_switch._stop_shell("test-shell", [
            {"id": "test-instance"},
        ])

        command = mock_run.call_args.args[0]
        self.assertEqual(command, [
            "/usr/bin/qs", "kill", "--id", "test-instance",
        ])

    @patch.object(shell_switch, "_running_shells")
    @patch.object(shell_switch, "_shells")
    def test_preview_does_not_start_or_stop_shells(
        self, mock_shells, mock_running
    ):
        mock_shells.return_value = {"test-shell": self.config}
        mock_running.return_value = {"test-shell": []}

        with (
            patch.object(shell_switch, "_start_shell") as start,
            patch.object(shell_switch, "_stop_shell") as stop,
        ):
            report = shell_switch.switch_shell("test-shell", apply=False)

        self.assertFalse(report["applied"])
        start.assert_not_called()
        stop.assert_not_called()

    @patch.object(shell_switch.shutil, "which", return_value="/usr/bin/caelestia")
    @patch.object(shell_switch.subprocess, "run")
    @patch.object(shell_switch, "_shells")
    def test_caelestia_keeps_special_stop_command(
        self, mock_shells, mock_run, mock_which
    ):
        mock_run.return_value.returncode = 0
        mock_shells.return_value = {
            "caelestia": {
                "name": "Caelestia",
                "path": self.entrypoint,
                "type": "caelestia",
            }
        }

        shell_switch._stop_shell(
            "caelestia",
            [{"id": "caelestia-instance"}],
        )

        self.assertEqual(
            mock_run.call_args.args[0],
            ["/usr/bin/caelestia", "shell", "-k"],
        )


    @patch.object(shell_switch.shutil, "which", return_value="/usr/bin/qs")
    @patch.object(shell_switch.subprocess, "run")
    def test_instances_handles_no_running_instances(
        self, mock_run, mock_which
    ):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "No running instances.\n"

        self.assertEqual(shell_switch._instances(), [])


    def test_failed_old_shell_stop_rolls_back_new_shell_and_selection(self):
        old_instance = {"id": "old-instance"}
        target_instance = {"id": "target-instance"}
        shells = {
            "old-shell": {**self.config, "name": "Old Shell"},
            "test-shell": self.config,
        }
        running_before = {
            "old-shell": [old_instance],
            "test-shell": [],
        }
        running_after_start = {
            "old-shell": [old_instance],
            "test-shell": [target_instance],
        }

        def stop_side_effect(shell_id, instances):
            if shell_id == "old-shell":
                raise shell_switch.ShellSwitchError("old shell stop failed")

        with (
            patch.object(shell_switch, "_shells", return_value=shells),
            patch.object(
                shell_switch, "_running_shells",
                side_effect=[
                    running_before,
                    running_after_start,
                    {"old-shell": [], "test-shell": [target_instance]},
                    {"old-shell": [old_instance], "test-shell": [target_instance]},
                    {"old-shell": [old_instance], "test-shell": [target_instance]},
                    {"old-shell": [old_instance], "test-shell": []},
                ],
            ),
            patch.object(shell_switch, "_active_shell", return_value="old-shell"),
            patch.object(shell_switch, "_start_shell") as start,
            patch.object(shell_switch, "_stop_shell", side_effect=stop_side_effect) as stop,
            patch.object(shell_switch, "_save_active") as save_active,
            patch.object(shell_switch, "_restore_active") as restore_active,
        ):
            with self.assertRaisesRegex(
                shell_switch.ShellSwitchError,
                "Shell switch failed: old shell stop failed",
            ):
                shell_switch.switch_shell("test-shell", apply=True)

        start.assert_any_call("test-shell")
        start.assert_any_call("old-shell")
        stop.assert_any_call("old-shell", [old_instance])
        stop.assert_any_call("test-shell", [target_instance])
        save_active.assert_called_once_with("test-shell")
        restore_active.assert_called_once_with("old-shell")


if __name__ == "__main__":
    unittest.main()
