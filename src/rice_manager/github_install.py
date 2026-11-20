
"""Safe staging and preview of public GitHub Quickshell repositories."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .shell_registry import (
    register_installed_shell,
    unregister_installed_shell,
    load_installed_shells,
    ShellRegistryError,
)


from .github_import import (
    GitHubImportError,
    MAX_ARCHIVE_BYTES,
    MAX_FILES,
    MAX_FILE_BYTES,
    _download,
    _download_to_tempfile,
    _repository_details,
    scan_github_repository,
)


def _has_any_symlink(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            return True
    return False


class GitHubInstallError(RuntimeError):
    """Raised when a GitHub shell cannot be staged safely."""


def _safe_archive_path(raw_name: str) -> PurePosixPath:
    if (
        not raw_name
        or raw_name.startswith("/")
        or "\\" in raw_name
        or "\x00" in raw_name
    ):
        raise GitHubInstallError("Archive contains an unsafe path.")

    parts = raw_name.split("/")

    # ZIP directory entries may have one trailing slash.
    if parts[-1] == "":
        parts.pop()

    if (
        not parts
        or ":" in parts[0]
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise GitHubInstallError(
            f"Archive contains an unsafe path: {raw_name[:200]}"
        )

    return PurePosixPath(*parts)


def _resolve_archive_symlink(zipped, entry, source_root, entries_by_name):
    archive_path = _safe_archive_path(entry.filename)
    parts = archive_path.parts
    root_parts = PurePosixPath(source_root).parts

    if parts[1:1 + len(root_parts)] != root_parts:
        raise GitHubInstallError("Symbolic link is outside the Quickshell root.")

    try:
        target = zipped.read(entry).decode("utf-8")
    except (UnicodeDecodeError, OSError, RuntimeError) as exc:
        raise GitHubInstallError("Invalid symbolic link target.") from exc

    if not target or target.startswith("/") or "\\" in target or "\x00" in target:
        raise GitHubInstallError("Unsafe symbolic link target.")

    resolved = list(parts[:-1])
    for part in target.split("/"):
        if part in {"", "."}:
            raise GitHubInstallError("Unsafe symbolic link target.")
        if part == "..":
            if len(resolved) <= 1:
                raise GitHubInstallError("Symbolic link escapes archive root.")
            resolved.pop()
        else:
            resolved.append(part)

    target_path = PurePosixPath(*resolved)
    if (
        target_path.parts[0] != parts[0]
        or target_path.parts[1:1 + len(root_parts)] != root_parts
    ):
        raise GitHubInstallError("Symbolic link escapes Quickshell root.")

    target_entry = entries_by_name.get(target_path.as_posix())
    if target_entry is None or target_entry.is_dir():
        raise GitHubInstallError("Symbolic link target is missing.")

    target_mode = target_entry.external_attr >> 16
    if stat.S_ISLNK(target_mode):
        raise GitHubInstallError("Chained symbolic links are not supported.")
    if stat.S_IFMT(target_mode) not in (0, stat.S_IFREG):
        raise GitHubInstallError("Symbolic link target is not a regular file.")

    return target_entry


def _validate_archive_symlinks(report, archive, source_root=None):
    unsafe = report.get("unsafe_entries", [])
    if report["summary"]["unsafe_entries"] != len(unsafe):
        raise GitHubInstallError("Repository has too many unsafe archive entries.")
    if not unsafe:
        return

    component = next(
        item for item in report["components"] if item["id"] == "quickshell"
    )
    selected_root = (
        source_root if source_root is not None else component["source_root"]
    )
    root_parts = PurePosixPath(selected_root).parts if selected_root else ()
    with zipfile.ZipFile(archive) as zipped:
        entries = {entry.filename: entry for entry in zipped.infolist()}
        for raw_name in unsafe:
            entry = entries.get(raw_name)
            if entry is None:
                raise GitHubInstallError("Repository contains unsafe archive entries.")
            if not stat.S_ISLNK(entry.external_attr >> 16):
                raise GitHubInstallError("Repository contains unsafe archive entries.")
            archive_parts = _safe_archive_path(raw_name).parts
            if archive_parts[1:1 + len(root_parts)] != root_parts:
                continue
            _resolve_archive_symlink(
                zipped, entry, selected_root, entries
            )


def _repository_archive(url: str, progress_callback=None):
    archive = None
    try:
        report = scan_github_repository(
            url,
            progress_callback=(
                lambda phase, current, total: progress_callback(
                    phase, current, total
                )
            ) if progress_callback is not None else None,
            _keep_archive=True,
        )
        archive = report.pop("_archive", None)
        if archive is None:
            # Compatibility path for callers/tests supplying a prebuilt report.
            import urllib.parse
            repository = report["repository"]
            owner, repo = repository["name"].split("/", 1)
            archive_url = (
                f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/"
                f"{urllib.parse.quote(repository['branch'], safe='')}"
            )
            archive = _download_to_tempfile(
                archive_url,
                MAX_ARCHIVE_BYTES,
                (lambda current, total: progress_callback(
                    "download", current, total
                )) if progress_callback is not None else None,
            )

        if report["compatibility"]["status"] != "compatible":
            raise GitHubInstallError(
                "Repository is not fully compatible with Rice Manager: "
                + report["compatibility"]["reason"]
            )

        archive.seek(0)
        return report, archive

    except Exception as exc:
        if archive is not None:
            archive.close()
        if isinstance(exc, GitHubInstallError):
            raise
        if isinstance(exc, (GitHubImportError, KeyError, ValueError, OSError)):
            raise GitHubInstallError(str(exc)) from exc
        raise


def prepare_github_shell(
    url: str,
    staging_root: str | Path | None = None,
    *,
    source_root: str | None = None,
    progress_callback=None,
) -> dict:
    """Safely extract one detected Quickshell configuration into staging.

    This function does not install files, execute scripts, or activate a shell.
    """
    report, archive = _repository_archive(url, progress_callback)
    try:
        configurations = report.get("configurations") or []
        if source_root is not None:
            component = next(
                (item for item in configurations
                 if item.get("source_root") == source_root),
                None,
            )
        else:
            component = next(
                (item for item in configurations
                 if item.get("source_root") ==
                 next((c for c in report["components"]
                       if c["id"] == "quickshell"), {}).get("source_root")),
                None,
            )
            if component is None:
                component = next(
                    (item for item in configurations
                     if item.get("compatibility") == "compatible"),
                    None,
                )
        if component is None and not configurations:
            legacy = next(
                (item for item in report["components"]
                 if item["id"] == "quickshell"),
                None,
            )
            if legacy is not None:
                component = legacy

        if component is None:
            raise GitHubInstallError("No Quickshell configuration was detected.")

        source_root = component.get("source_root", "")
        if not isinstance(source_root, str):
            raise GitHubInstallError("Invalid Quickshell source root.")
        _validate_archive_symlinks(report, archive, source_root)
        entrypoint_name = component.get("entrypoint")
        if (
            not isinstance(entrypoint_name, str)
            or _safe_archive_path(entrypoint_name).as_posix() != entrypoint_name
            or PurePosixPath(entrypoint_name).name != "shell.qml"
        ):
            raise GitHubInstallError(
                "Exactly one safe shell.qml entrypoint is required."
            )

        source_root_path = PurePosixPath(source_root)
        root = (
            Path(staging_root).expanduser()
            if staging_root is not None
            else Path.home()
            / ".local/share/rice-manager/github-shells"
        )
        root = root.absolute()

        if _has_any_symlink(root):
            raise GitHubInstallError(
                "Staging path contains a symlinked directory component."
            )

        root.mkdir(parents=True, exist_ok=True)

        if _has_any_symlink(root) or not root.is_dir():
            raise GitHubInstallError(
                "Staging directory must be a real directory."
            )

        repository_name = report["repository"]["name"].split("/", 1)[1]
        safe_name = "".join(
            char.lower() if char.isalnum() else "-"
            for char in repository_name
        ).strip("-")[:40] or "github-shell"

        identity = hashlib.sha256(
            (
                report["repository"]["url"] + "\\0" + source_root
            ).encode("utf-8")
        ).hexdigest()[:10]

        stage_id = f"{safe_name}-{identity}"
        destination = root / stage_id

        if destination.exists() or destination.is_symlink():
            raise GitHubInstallError(
                f"This repository is already staged: {destination}"
            )

        try:
            zipped = zipfile.ZipFile(archive)
        except (zipfile.BadZipFile, OSError) as exc:
            raise GitHubInstallError(
                "GitHub returned an invalid ZIP archive."
            ) from exc

        staging = Path(
            tempfile.mkdtemp(prefix=".github-stage-", dir=root)
        )

        extracted = 0
        total_bytes = 0
        seen_paths: set[str] = set()
        file_records: list[dict] = []
        skipped_oversized: list[str] = []

        try:
            with zipped, archive:
                entries = zipped.infolist()

                if len(entries) > MAX_FILES:
                    raise GitHubInstallError(
                        "Repository contains too many archive entries."
                    )

                for entry in entries:
                    archive_path = _safe_archive_path(entry.filename)

                    if entry.is_dir():
                        continue

                    mode = entry.external_attr >> 16

                    parts = archive_path.parts

                    # GitHub ZIP archives contain one wrapper directory.
                    if len(parts) < 2:
                        continue

                    relative_parts = parts[1:]

                    if relative_parts[:len(source_root_path.parts)] != source_root_path.parts:
                        continue

                    if len(relative_parts) <= len(source_root_path.parts):
                        continue

                    inner_parts = relative_parts[len(source_root_path.parts):]
                    relative = PurePosixPath(*inner_parts)

                    if relative.is_absolute() or any(
                        part in {"", ".", ".."} for part in relative.parts
                    ):
                        raise GitHubInstallError(
                            "Unsafe configuration file path."
                        )

                    relative_name = relative.as_posix()

                    content_entry = entry
                    if stat.S_ISLNK(mode):
                        archive_entries = {
                            item.filename: item for item in entries
                        }
                        content_entry = _resolve_archive_symlink(
                            zipped, entry, source_root, archive_entries
                        )

                    if relative_name in seen_paths:
                        raise GitHubInstallError(
                            f"Duplicate archive path: {relative_name}"
                        )

                    seen_paths.add(relative_name)

                    if content_entry.file_size < 0:
                        raise GitHubInstallError(
                            f"Invalid file size: {relative_name}"
                        )

                    if content_entry.file_size > MAX_FILE_BYTES:
                        if relative_name == entrypoint_name:
                            raise GitHubInstallError(
                                "Required shell.qml exceeds the 1 GiB file limit."
                            )
                        skipped_oversized.append(relative_name)
                        continue

                    if total_bytes + content_entry.file_size > MAX_ARCHIVE_BYTES:
                        raise GitHubInstallError(
                            "Extracted configuration exceeds size limit."
                        )

                    target = staging.joinpath(*relative.parts)

                    if target.exists() or target.is_symlink():
                        raise GitHubInstallError(
                            f"Duplicate staging destination: {relative_name}"
                        )

                    target.parent.mkdir(parents=True, exist_ok=True)

                    if target.parent.is_symlink():
                        raise GitHubInstallError(
                            "Staging path contains a symbolic link."
                        )

                    actual_size = 0
                    digest = hashlib.sha256()

                    with zipped.open(content_entry) as source, target.open("xb") as output:
                        while True:
                            chunk = source.read(64 * 1024)

                            if not chunk:
                                break

                            actual_size += len(chunk)

                            if (
                                actual_size > MAX_FILE_BYTES
                                or actual_size > content_entry.file_size
                                or total_bytes + actual_size > MAX_ARCHIVE_BYTES
                            ):
                                raise GitHubInstallError(
                                    f"Extracted file exceeds size limit: {relative_name}"
                                )

                            output.write(chunk)
                            digest.update(chunk)

                    if actual_size != content_entry.file_size:
                        raise GitHubInstallError(
                            f"Archive size mismatch: {relative_name}"
                        )

                    total_bytes += actual_size
                    file_records.append({
                        "path": relative_name,
                        "size": actual_size,
                        "sha256": digest.hexdigest(),
                    })

                    # Do not preserve executable permissions from the repository.
                    target.chmod(0o600)
                    extracted += 1
                    if progress_callback is not None:
                        progress_callback(
                            "extract", extracted, len(entries)
                        )

            entrypoint = staging.joinpath(
                *PurePosixPath(entrypoint_name).parts
            )

            if not entrypoint.is_file() or entrypoint.is_symlink():
                raise GitHubInstallError(
                    "Staged shell.qml entrypoint is missing or unsafe."
                )

            metadata = {
                "schema_version": 1,
                "stage_id": stage_id,
                "repository": report["repository"],
                "source_root": component["source_root"],
                "entrypoint": entrypoint_name,
                "file_count": extracted,
                "total_bytes": total_bytes,
                "files": file_records,
                "skipped_oversized": skipped_oversized,
                "scripts_flagged": report["summary"]["scripts_flagged"],
                "installation_performed": False,
            }

            (staging / ".rice-manager-stage.json").write_text(
                json.dumps(metadata, indent=2) + "\n",
                encoding="utf-8",
            )
            (staging / ".rice-manager-stage.json").chmod(0o600)

            if destination.exists() or destination.is_symlink():
                raise GitHubInstallError(
                    "Staging destination already exists."
                )

            staging.rename(destination)

            return {
                **metadata,
                "staging_path": str(destination),
                "dry_run": True,
            }

        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    finally:
        archive.close()

def preview_github_install(
    staging_path: str | Path,
    config_home: str | Path | None = None,
) -> dict:
    """Describe a staged shell installation without changing user files."""
    staging = Path(staging_path).expanduser().absolute()

    if _has_any_symlink(staging) or not staging.is_dir():
        raise GitHubInstallError(
            "Staging path must be a real directory."
        )

    metadata_path = staging / ".rice-manager-stage.json"

    if metadata_path.is_symlink() or not metadata_path.is_file():
        raise GitHubInstallError(
            "Staging metadata is missing or unsafe."
        )

    try:
        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise GitHubInstallError(
            "Could not read staging metadata."
        ) from exc

    if not isinstance(metadata, dict):
        raise GitHubInstallError("Invalid staging metadata.")

    if metadata.get("schema_version") != 1:
        raise GitHubInstallError("Unsupported staging metadata version.")

    entrypoint_name = metadata.get("entrypoint")
    if (
        not isinstance(entrypoint_name, str)
        or _safe_archive_path(entrypoint_name).as_posix() != entrypoint_name
        or PurePosixPath(entrypoint_name).name != "shell.qml"
    ):
        raise GitHubInstallError("Invalid staged shell entrypoint.")

    repository = metadata.get("repository")
    if not isinstance(repository, dict):
        raise GitHubInstallError("Invalid repository metadata.")

    repository_name = repository.get("name")
    repository_url = repository.get("url")
    branch = repository.get("branch")

    if (
        not isinstance(repository_name, str)
        or repository_name.count("/") != 1
        or not all(repository_name.split("/"))
        or repository_url != f"https://github.com/{repository_name}"
        or not isinstance(branch, str)
        or not branch
    ):
        raise GitHubInstallError("Invalid repository identity in staging metadata.")

    safe_name = "".join(
        char.lower() if char.isalnum() else "-"
        for char in repository_name.split("/", 1)[1]
    ).strip("-")[:40] or "github-shell"

    source_root = metadata.get("source_root", "")
    if not isinstance(source_root, str):
        raise GitHubInstallError("Invalid staged source root.")
    identity = hashlib.sha256(
        (repository_url + "\\0" + source_root).encode("utf-8")
    ).hexdigest()[:10]
    expected_stage_id = f"{safe_name}-{identity}"

    if metadata.get("stage_id") != expected_stage_id or staging.name != expected_stage_id:
        raise GitHubInstallError("Staging directory identity does not match metadata.")

    manifest = metadata.get("files")
    if not isinstance(manifest, list) or len(manifest) > MAX_FILES:
        raise GitHubInstallError("Invalid staged file manifest.")

    expected = {}
    for record in manifest:
        if not isinstance(record, dict):
            raise GitHubInstallError("Invalid file manifest entry.")

        relative_name = record.get("path")
        size = record.get("size")
        digest = record.get("sha256")

        if (
            not isinstance(relative_name, str)
            or _safe_archive_path(relative_name).as_posix() != relative_name
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or size > MAX_FILE_BYTES
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or relative_name in expected
        ):
            raise GitHubInstallError("Invalid file manifest entry.")

        expected[relative_name] = (size, digest)

    files = []
    actual = {}

    for path in sorted(staging.rglob("*")):
        if path.is_symlink():
            raise GitHubInstallError(
                "Staged configuration contains a symbolic link."
            )

        if path.is_dir():
            continue

        if not path.is_file():
            raise GitHubInstallError(
                "Staged configuration contains an unsupported file."
            )

        relative = path.relative_to(staging).as_posix()

        if relative == ".rice-manager-stage.json":
            continue

        digest = hashlib.sha256()
        actual_size = 0

        with path.open("rb") as source:
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                actual_size += len(chunk)
                if actual_size > MAX_FILE_BYTES:
                    raise GitHubInstallError("Staged file exceeds size limit.")
                digest.update(chunk)

        actual[relative] = (actual_size, digest.hexdigest())
        files.append({
            "path": relative,
            "size": actual_size,
            "sha256": digest.hexdigest(),
        })

    if actual != expected:
        raise GitHubInstallError(
            "Staged files do not match their integrity manifest."
        )

    if entrypoint_name not in actual:
        raise GitHubInstallError("Staged shell.qml entrypoint is missing.")

    if len(files) != metadata.get("file_count"):
        raise GitHubInstallError("Staged file count does not match metadata.")

    total_bytes = sum(item["size"] for item in files)
    if total_bytes != metadata.get("total_bytes") or total_bytes > MAX_ARCHIVE_BYTES:
        raise GitHubInstallError("Staged total size does not match metadata.")

    skipped_oversized = metadata.get("skipped_oversized", [])
    if (
        not isinstance(skipped_oversized, list)
        or len(skipped_oversized) > MAX_FILES
        or any(
            not isinstance(name, str)
            or _safe_archive_path(name).as_posix() != name
            or name == entrypoint_name
            or name in expected
            for name in skipped_oversized
        )
        or len(set(skipped_oversized)) != len(skipped_oversized)
    ):
        raise GitHubInstallError("Invalid skipped-file manifest.")

    scripts_flagged = metadata.get("scripts_flagged")
    if not isinstance(scripts_flagged, int) or isinstance(scripts_flagged, bool) or scripts_flagged < 0:
        raise GitHubInstallError("Invalid script warning count.")

    base = (
        Path(config_home).expanduser()
        if config_home is not None
        else Path(
            os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        ).expanduser()
    ).absolute()

    destination = base / "quickshell" / expected_stage_id

    if _has_any_symlink(destination):
        raise GitHubInstallError(
            "Installation destination contains a symlinked path component."
        )

    if destination.exists() or destination.is_symlink():
        raise GitHubInstallError(
            f"Installation destination already exists: {destination}"
        )

    return {
        "repository": repository,
        "stage_id": expected_stage_id,
        "entrypoint": entrypoint_name,
        "source": str(staging),
        "destination": str(destination),
        "files": files,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "scripts_flagged": scripts_flagged,
        "skipped_oversized": skipped_oversized,
        "dry_run": True,
        "installation_performed": False,
    }


def install_github_shell(
    staging_path: str | Path,
    config_home: str | Path | None = None,
    *,
    confirm: bool = False,
    progress_callback=None,
) -> dict:
    "Install a verified staged shell after explicit user confirmation."
    if confirm is not True:
        raise GitHubInstallError(
            "Installation requires explicit confirmation."
        )

    preview = preview_github_install(staging_path, config_home)
    staging = Path(preview["source"])
    destination = Path(preview["destination"])
    parent = destination.parent

    if _has_any_symlink(parent):
        raise GitHubInstallError(
            "Installation parent contains a symlinked path component."
        )

    parent.mkdir(parents=True, exist_ok=True)

    if _has_any_symlink(parent) or not parent.is_dir():
        raise GitHubInstallError("Unsafe installation directory.")

    if destination.exists() or destination.is_symlink():
        raise GitHubInstallError(
            f"Installation destination already exists: {destination}"
        )

    temporary = Path(
        tempfile.mkdtemp(prefix=".rice-manager-install-", dir=parent)
    )
    installed = False
    copied_total = 0

    try:
        for item in preview["files"]:
            relative = PurePosixPath(item["path"])
            source = staging.joinpath(*relative.parts)
            target = temporary.joinpath(*relative.parts)

            if _has_any_symlink(source) or not source.is_file():
                raise GitHubInstallError(
                    f"Staged file is missing or unsafe: {item['path']}"
                )

            target.parent.mkdir(parents=True, exist_ok=True)

            if _has_any_symlink(target.parent):
                raise GitHubInstallError(
                    "Temporary installation contains a symlinked path."
                )

            digest = hashlib.sha256()
            copied_size = 0

            with source.open("rb") as source_file, target.open("xb") as target_file:
                while True:
                    chunk = source_file.read(64 * 1024)
                    if not chunk:
                        break
                    copied_size += len(chunk)
                    if copied_size > item["size"]:
                        raise GitHubInstallError(
                            f"Staged file changed during installation: {item['path']}"
                        )
                    digest.update(chunk)
                    target_file.write(chunk)

            if (
                copied_size != item["size"]
                or digest.hexdigest() != item["sha256"]
            ):
                raise GitHubInstallError(
                    f"Staged file integrity check failed: {item['path']}"
                )

            target.chmod(0o600)
            copied_total += copied_size
            if progress_callback is not None:
                progress_callback(
                    "install", copied_total, preview["total_bytes"]
                )

        if _has_any_symlink(temporary):
            raise GitHubInstallError(
                "Temporary installation contains a symlink."
            )

        entrypoint = temporary.joinpath(
            *PurePosixPath(preview["entrypoint"]).parts
        )
        if not entrypoint.is_file() or entrypoint.is_symlink():
            raise GitHubInstallError("Installed shell entrypoint is invalid.")

        temporary.rename(destination)
        installed = True

        repository = preview["repository"]
        register_installed_shell({
            "id": preview["stage_id"],
            "name": repository["name"].split("/", 1)[1],
            "path": str(destination.joinpath(*PurePosixPath(preview["entrypoint"]).parts)),
            "repository": repository["url"],
        })

    except Exception as exc:
        if installed:
            shutil.rmtree(destination, ignore_errors=True)
        if isinstance(exc, GitHubInstallError):
            raise
        if isinstance(exc, ShellRegistryError):
            raise GitHubInstallError(
                f"Shell registration failed; installation rolled back: {exc}"
            ) from exc
        raise GitHubInstallError(
            f"Installation failed: {exc}"
        ) from exc

    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)

    return {
        **preview,
        "destination": str(destination),
        "dry_run": False,
        "installation_performed": True,
        "registered": True,
    }



def delete_github_shell(shell_id: str, *, confirm: bool = False) -> dict:
    """Safely remove one registered GitHub shell installation."""
    if confirm is not True:
        raise GitHubInstallError(
            "Deleting a shell requires explicit confirmation."
        )

    if not isinstance(shell_id, str) or not shell_id:
        raise GitHubInstallError("Invalid shell ID.")

    if shell_id in {"cartoon-shell", "caelestia"}:
        raise GitHubInstallError("Built-in shells cannot be deleted.")

    try:
        installed = load_installed_shells()
    except ShellRegistryError as exc:
        raise GitHubInstallError(str(exc)) from exc

    if shell_id not in installed:
        raise GitHubInstallError("This shell is not registered.")

    # Verify the shell is stopped before deleting its files.
    try:
        from .shell_switch import ShellSwitchError, _running_shells
        running = _running_shells()
    except ShellSwitchError as exc:
        raise GitHubInstallError(
            f"Cannot safely verify running shells: {exc}"
        ) from exc

    if running.get(shell_id):
        raise GitHubInstallError(
            "Cannot delete a shell while it is running. "
            "Switch to another shell first."
        )

    record = installed[shell_id]
    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    ).expanduser().absolute()

    managed_root = config_home / "quickshell"
    shell_dir = managed_root / shell_id

    record_path = Path(record["path"]).absolute()
    try:
        relative_entrypoint = record_path.relative_to(shell_dir)
    except ValueError as exc:
        raise GitHubInstallError(
            "Registered shell path does not match its managed installation."
        ) from exc

    if (
        relative_entrypoint.is_absolute()
        or not relative_entrypoint.parts
        or relative_entrypoint.name != "shell.qml"
    ):
        raise GitHubInstallError("Registered shell entrypoint is invalid.")

    if _has_any_symlink(managed_root) or _has_any_symlink(shell_dir):
        raise GitHubInstallError(
            "Refusing to delete a shell with symlinked path components."
        )

    if not shell_dir.is_dir() or shell_dir.is_symlink():
        raise GitHubInstallError("Managed shell directory is missing or unsafe.")

    if (
        not record_path.is_file()
        or record_path.is_symlink()
        or _has_any_symlink(record_path)
    ):
        raise GitHubInstallError("Managed shell entrypoint is missing or unsafe.")

    # Create a same-filesystem quarantine path before changing the registry.
    quarantine = Path(
        tempfile.mkdtemp(prefix=".rice-manager-delete-", dir=managed_root)
    )
    quarantine.rmdir()

    # Remove the registry entry while its entrypoint still exists.
    try:
        unregister_installed_shell(shell_id)
    except Exception as exc:
        if isinstance(exc, ShellRegistryError):
            raise GitHubInstallError(
                f"Shell deletion was not started: {exc}"
            ) from exc
        raise GitHubInstallError(
            f"Shell deletion was not started: {exc}"
        ) from exc

    # Move the directory out of the managed location.
    try:
        shell_dir.rename(quarantine)
    except OSError as exc:
        try:
            register_installed_shell({
                "id": shell_id,
                "name": record["name"],
                "path": str(record["path"]),
                "repository": record["repository"],
            })
        except Exception as restore_error:
            raise GitHubInstallError(
                "Could not move the shell and registry restoration failed. "
                f"The installation remains at {shell_dir}. "
                f"Restoration error: {restore_error}"
            ) from exc

        raise GitHubInstallError(
            f"Shell deletion was rolled back: {exc}"
        ) from exc

    try:
        shutil.rmtree(quarantine)
    except OSError as exc:
        raise GitHubInstallError(
            "The shell was unregistered, but its quarantined files could "
            f"not be removed: {quarantine}. Details: {exc}"
        ) from exc

    return {
        "id": shell_id,
        "name": record["name"],
        "deleted": True,
    }
