import io
import json
import unittest
import zipfile
from unittest.mock import patch

from rice_manager.github_import import (
    GitHubImportError,
    scan_github_repository,
    _download,
)


def make_archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(f"example-main/{name}", content)
    return buffer.getvalue()


class GitHubCompatibilityTests(unittest.TestCase):
    def scan_files(self, files):
        metadata = json.dumps({
            "default_branch": "main",
            "full_name": "example/rice",
            "html_url": "https://github.com/example/rice",
        }).encode()

        archive = make_archive(files)

        with patch(
            "rice_manager.github_import._download",
            return_value=metadata,
        ), patch(
            "rice_manager.github_import._download_to_tempfile",
            return_value=io.BytesIO(archive),
        ):
            return scan_github_repository("https://github.com/example/rice")

    def test_quickshell_with_root_entrypoint_is_compatible(self):
        result = self.scan_files({
            ".config/quickshell/shell.qml": "import QtQuick",
            ".config/quickshell/modules/bar.qml": "Item {}",
        })

        self.assertEqual(result["compatibility"]["status"], "compatible")
        self.assertEqual(result["compatibility"]["entrypoint"], "shell.qml")

    def test_quickshell_with_nested_entrypoint_is_compatible(self):
        result = self.scan_files({
            ".config/quickshell/ii/shell.qml": "Item {}",
            ".config/quickshell/ii/modules/bar.qml": "Item {}",
        })

        self.assertEqual(result["compatibility"]["status"], "compatible")
        self.assertEqual(result["compatibility"]["entrypoint"], "ii/shell.qml")

    def test_quickshell_without_root_entrypoint_is_partial(self):
        result = self.scan_files({
            ".config/quickshell/modules/bar.qml": "Item {}",
        })

        self.assertEqual(result["compatibility"]["status"], "partial")
        self.assertIsNone(result["compatibility"]["entrypoint"])

    def test_root_level_shell_entrypoint_detects_repository_root(self):
        result = self.scan_files({
            "shell.qml": "Item {}",
            "modules/bar.qml": "Item {}",
        })
        configs = result["configurations"]
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["source_root"], "")
        self.assertEqual(configs[0]["file_count"], 2)
        self.assertEqual(result["compatibility"]["status"], "compatible")

    def test_detects_multiple_quickshell_configurations(self):
        result = self.scan_files({
            ".config/quickshell/alpha/shell.qml": "Item {}",
            ".config/quickshell/alpha/bar.qml": "Item {}",
            ".config/quickshell/beta/shell.qml": "Item {}",
            ".config/quickshell/beta/baz.qml": "Item {}",
        })
        roots = {item["source_root"] for item in result["configurations"]}
        self.assertEqual(
            roots,
            {".config/quickshell/alpha", ".config/quickshell/beta"},
        )
        self.assertEqual(result["compatibility"]["status"], "compatible")

    def test_repository_without_quickshell_is_unsupported(self):
        result = self.scan_files({
            ".config/hypr/hyprland.conf": "general {}",
        })

        self.assertEqual(result["compatibility"]["status"], "unsupported")
        self.assertIsNone(result["compatibility"]["shell_type"])


if __name__ == "__main__":
    unittest.main()


class DownloadProgressTests(unittest.TestCase):
    class FakeResponse:
        def __init__(self, data, content_length=None):
            self.stream = io.BytesIO(data)
            self.headers = {}
            if content_length is not None:
                self.headers["Content-Length"] = str(content_length)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            return self.stream.read(min(size, 3))

    def test_scan_forwards_download_progress(self):
        archive = make_archive({
            ".config/quickshell/shell.qml": "Item {}",
        })
        updates = []

        def download(url, limit, progress_callback=None):
            if progress_callback is not None:
                progress_callback(len(archive), len(archive))
            return io.BytesIO(archive)

        with patch(
            "rice_manager.github_import._repository_details",
            return_value=(
                "example/rice", "main", "https://github.com/example/rice"
            ),
        ), patch(
            "rice_manager.github_import._download_to_tempfile",
            side_effect=download,
        ):
            result = scan_github_repository(
                "https://github.com/example/rice",
                progress_callback=lambda *event: updates.append(event),
            )

        self.assertEqual(result["compatibility"]["status"], "compatible")
        self.assertTrue(updates)
        self.assertEqual(updates[-1][0], "download")
        self.assertEqual(updates[-1][1], len(archive))

    @patch("rice_manager.github_import.urllib.request.urlopen")
    def test_download_reports_progress(self, mock_urlopen):
        mock_urlopen.return_value = self.FakeResponse(b"abcdef", 6)
        updates = []

        result = _download(
            "https://example.com/archive.zip",
            100,
            lambda downloaded, total: updates.append((downloaded, total)),
        )

        self.assertEqual(result, b"abcdef")
        self.assertEqual(updates, [(3, 6), (6, 6)])

    @patch("rice_manager.github_import.urllib.request.urlopen")
    def test_download_enforces_size_limit(self, mock_urlopen):
        mock_urlopen.return_value = self.FakeResponse(b"abcdef", 6)

        with self.assertRaises(GitHubImportError):
            _download("https://example.com/archive.zip", 5)


class GitHubSubmoduleTests(unittest.TestCase):
    def make_zip(self, wrapper, files):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, content in files.items():
                archive.writestr(f"{wrapper}/{name}", content)
        return buffer.getvalue()

    def scan_with_submodule(self, *, include_gitlink=True):
        from unittest.mock import call

        from rice_manager.github_import import MAX_ARCHIVE_BYTES

        commit = "e31ec4cb4ebf6a46b267f5c42eabf6874916fa16"
        module_path = ".config/quickshell/modules/shapes"

        main = self.make_zip("rice-main", {
            ".gitmodules": (
                '[submodule "shapes"]\n'
                f"\tpath = {module_path}\n"
                "\turl = https://github.com/end-4/rounded-polygon-qmljs.git\n"
            ),
            ".config/quickshell/shell.qml": "Item {}",
        })
        sub = self.make_zip("rounded-polygon-qmljs-" + commit, {
            "Shape.qml": "Item {}",
        })

        parent_tree = {
            "tree": (
                [{
                    "path": module_path,
                    "mode": "160000",
                    "type": "commit",
                    "sha": commit,
                }] if include_gitlink else []
            ),
            "truncated": False,
        }
        sub_tree = {"tree": [], "truncated": False}

        def download(url, limit, progress_callback=None):
            if "/repos/example/rice/git/trees/" in url:
                return json.dumps(parent_tree).encode()
            if "/repos/end-4/rounded-polygon-qmljs/git/trees/" in url:
                return json.dumps(sub_tree).encode()
            raise AssertionError(f"Unexpected API request: {url}")

        downloads = []

        def download_archive(url, limit, progress_callback=None):
            downloads.append(url)
            return io.BytesIO(main if len(downloads) == 1 else sub)

        with patch(
            "rice_manager.github_import._repository_details",
            return_value=(
                "example/rice", "main", "https://github.com/example/rice"
            ),
        ), patch(
            "rice_manager.github_import._download",
            side_effect=download,
        ), patch(
            "rice_manager.github_import._download_to_tempfile",
            side_effect=download_archive,
        ):
            if include_gitlink:
                report = scan_github_repository(
                    "https://github.com/example/rice",
                    _keep_archive=True,
                )
                try:
                    with zipfile.ZipFile(report["_archive"]) as archive:
                        names = set(archive.namelist())
                    return report, names, downloads, commit
                finally:
                    report["_archive"].close()

            return scan_github_repository("https://github.com/example/rice")

    def test_downloads_submodule_at_pinned_commit_and_scans_its_files(self):
        report, names, downloads, commit = self.scan_with_submodule()

        self.assertEqual(report["compatibility"]["status"], "compatible")
        self.assertIn(
            "rice-main/.config/quickshell/modules/shapes/Shape.qml",
            names,
        )
        self.assertTrue(downloads[1].endswith(f"/zip/{commit}"))

        config = report["configurations"][0]
        self.assertIn("modules/shapes/Shape.qml", config["files"])

    def test_rejects_submodule_without_matching_gitlink(self):
        with self.assertRaisesRegex(GitHubImportError, "no matching GitHub gitlink"):
            self.scan_with_submodule(include_gitlink=False)
