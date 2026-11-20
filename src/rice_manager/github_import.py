
"""Read-only scanner for public GitHub dotfiles repositories."""

from __future__ import annotations

import configparser
import json
import re
import stat
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import PurePosixPath


class GitHubImportError(RuntimeError):
    """Raised when a GitHub repository cannot be scanned safely."""


MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_FILES = 5000
MAX_FILE_BYTES = 1 * 1024 * 1024 * 1024
SUPPORTED = {
    "hypr": ("Hyprland", "hyprland"),
    "quickshell": ("Quickshell", "quickshell"),
    "waybar": ("Waybar", "waybar"),
    "kitty": ("Kitty", "kitty"),
}
SUSPICIOUS_SUFFIXES = {".sh", ".bash", ".fish", ".py", ".service"}


def _download(url: str, limit: int, progress_callback=None) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Rice-Manager/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            header = response.headers.get("Content-Length")
            total = int(header) if header and header.isdigit() else None

            chunks = []
            downloaded = 0

            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break

                downloaded += len(chunk)

                if downloaded > limit:
                    raise GitHubImportError(
                        "Downloaded data exceeds the configured size limit."
                    )

                chunks.append(chunk)

                if progress_callback is not None:
                    progress_callback(downloaded, total)

    except (OSError, urllib.error.URLError) as exc:
        raise GitHubImportError(f"GitHub download failed: {exc}") from exc

    return b"".join(chunks)


def _download_to_tempfile(url: str, limit: int, progress_callback=None):
    """Stream a download into a temporary disk-backed file."""
    temporary = tempfile.TemporaryFile(mode="w+b")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Rice-Manager/0.1"},
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            header = response.headers.get("Content-Length")
            total = int(header) if header and header.isdigit() else None

            downloaded = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break

                downloaded += len(chunk)
                if downloaded > limit:
                    raise GitHubImportError(
                        f"Repository archive exceeds the {limit} byte limit."
                    )

                temporary.write(chunk)

                if progress_callback is not None:
                    progress_callback(downloaded, total)

        temporary.seek(0)
        return temporary

    except (OSError, urllib.error.URLError) as exc:
        temporary.close()
        raise GitHubImportError(f"GitHub download failed: {exc}") from exc
    except Exception:
        temporary.close()
        raise


def _repository_details(url: str) -> tuple[str, str, str]:
    parsed = urllib.parse.urlparse(url.strip())

    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise GitHubImportError("Use a public https://github.com/owner/repository URL.")

    if parsed.username or parsed.password or parsed.port:
        raise GitHubImportError("Repository URL contains unsupported address details.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise GitHubImportError("URL must point directly to a GitHub repository.")

    owner = parts[0]
    repo = parts[1].removesuffix(".git")

    if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
        raise GitHubImportError("Invalid GitHub owner name.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise GitHubImportError("Invalid GitHub repository name.")

    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    metadata = json.loads(_download(api_url, 1024 * 1024))

    branch = metadata.get("default_branch")
    full_name = metadata.get("full_name")
    if not isinstance(branch, str) or not branch:
        raise GitHubImportError("GitHub did not provide a default branch.")
    if not isinstance(full_name, str):
        raise GitHubImportError("GitHub returned invalid repository metadata.")

    return full_name, branch, metadata.get("html_url", url)



def _safe_github_repo_url(value: str, parent: str) -> tuple[str, str]:
    """Resolve a submodule URL and restrict it to public GitHub repositories."""
    parent_owner, parent_repo = parent.split("/", 1)
    base = f"https://github.com/{parent_owner}/{parent_repo}/"
    resolved = urllib.parse.urljoin(base, value.strip())
    parsed = urllib.parse.urlparse(resolved)

    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username
        or parsed.password
        or parsed.port
        or parsed.query
        or parsed.fragment
    ):
        raise GitHubImportError(
            "Submodule URL must point to a public GitHub repository."
        )

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise GitHubImportError("Invalid GitHub submodule repository URL.")

    owner, repo = parts[0], parts[1].removesuffix(".git")
    if (
        not re.fullmatch(r"[A-Za-z0-9-]+", owner)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo)
    ):
        raise GitHubImportError("Invalid GitHub submodule repository name.")

    return owner, repo


def _parse_gitmodules(data: bytes) -> list[tuple[str, str]]:
    """Parse .gitmodules without invoking Git or a shell."""
    if len(data) > 1024 * 1024:
        raise GitHubImportError(".gitmodules exceeds the allowed size.")

    parser = configparser.ConfigParser(
        interpolation=None,
        strict=True,
        delimiters=("=",),
    )
    parser.optionxform = str.lower

    try:
        parser.read_string(data.decode("utf-8"))
    except (UnicodeError, configparser.Error) as exc:
        raise GitHubImportError("Repository has an invalid .gitmodules file.") from exc

    modules = []
    seen_paths = set()

    for section in parser.sections():
        if not section.lower().startswith('submodule "'):
            continue

        path = parser.get(section, "path", fallback="").strip()
        url = parser.get(section, "url", fallback="").strip()

        if not path or not url:
            raise GitHubImportError(
                "Every submodule must declare both a path and a URL."
            )

        pure = PurePosixPath(path)
        if (
            pure.is_absolute()
            or "\\" in path
            or "\x00" in path
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise GitHubImportError("Submodule contains an unsafe path.")

        normalized = pure.as_posix()
        if normalized in seen_paths:
            raise GitHubImportError("Repository declares a duplicate submodule path.")

        seen_paths.add(normalized)
        modules.append((normalized, url))

    return modules


def _github_tree_gitlinks(owner: str, repo: str, revision: str) -> dict[str, str]:
    """Return validated path-to-commit mappings for GitHub gitlinks."""
    endpoint = (
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/"
        f"{urllib.parse.quote(revision, safe='')}?recursive=1"
    )
    try:
        payload = json.loads(_download(endpoint, 16 * 1024 * 1024))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GitHubImportError("GitHub returned an invalid repository tree.") from exc

    if payload.get("truncated"):
        raise GitHubImportError(
            "GitHub repository tree is too large to verify safely."
        )

    tree = payload.get("tree")
    if not isinstance(tree, list):
        raise GitHubImportError("GitHub returned an invalid repository tree.")

    result = {}
    for item in tree:
        if not isinstance(item, dict):
            continue
        if item.get("mode") != "160000" or item.get("type") != "commit":
            continue

        path = item.get("path")
        sha = item.get("sha")
        if (
            not isinstance(path, str)
            or not isinstance(sha, str)
            or not re.fullmatch(r"[0-9a-fA-F]{40}", sha)
        ):
            raise GitHubImportError("GitHub returned an invalid submodule gitlink.")

        pure = PurePosixPath(path)
        if (
            pure.is_absolute()
            or "\\" in path
            or "\x00" in path
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise GitHubImportError("GitHub returned an unsafe submodule path.")

        result[pure.as_posix()] = sha

    return result


def _expand_github_submodules(
    archive,
    full_name: str,
    branch: str,
    progress_callback=None,
):
    """Return a ZIP containing the main repository and its pinned submodules."""
    try:
        original_size = archive.seek(0, 2)
        archive.seek(0)
        if original_size > MAX_ARCHIVE_BYTES:
            raise GitHubImportError("Repository archive exceeds the configured size limit.")

        with zipfile.ZipFile(archive) as main_zip:
            entries = main_zip.infolist()
            if len(entries) > MAX_FILES:
                raise GitHubImportError("Repository contains too many archive entries.")

            gitmodules_entry = next(
                (
                    entry for entry in entries
                    if PurePosixPath(entry.filename).name == ".gitmodules"
                    and len(PurePosixPath(entry.filename).parts) == 2
                ),
                None,
            )
            if gitmodules_entry is None:
                archive.seek(0)
                return archive

            wrapper = PurePosixPath(gitmodules_entry.filename).parts[0]
            modules = _parse_gitmodules(main_zip.read(gitmodules_entry))
            if not modules:
                archive.seek(0)
                return archive

            owner, repo = full_name.split("/", 1)
            gitlinks = _github_tree_gitlinks(owner, repo, branch)

            if len(entries) + len(modules) > MAX_FILES:
                raise GitHubImportError("Repository contains too many archive entries.")

            occupied = {entry.filename for entry in entries}
            additions = []
            downloaded_total = original_size

            for index, (module_path, module_url) in enumerate(modules, 1):
                commit = gitlinks.get(module_path)
                if commit is None:
                    raise GitHubImportError(
                        f"Submodule '{module_path}' has no matching GitHub gitlink."
                    )

                sub_owner, sub_repo = _safe_github_repo_url(module_url, full_name)
                tree = _github_tree_gitlinks(sub_owner, sub_repo, commit)
                if tree:
                    raise GitHubImportError(
                        f"Nested submodules are not supported yet: {module_path}"
                    )

                remaining = MAX_ARCHIVE_BYTES - downloaded_total
                if remaining <= 0:
                    raise GitHubImportError(
                        "Combined repository and submodule archives exceed the size limit."
                    )

                sub_url = (
                    f"https://codeload.github.com/{sub_owner}/{sub_repo}/zip/{commit}"
                )
                sub_archive = _download_to_tempfile(
                    sub_url,
                    remaining,
                    (
                        lambda current, total, i=index, count=len(modules):
                        progress_callback(
                            "submodule-download",
                            current,
                            total,
                        )
                    ) if progress_callback is not None else None,
                )

                try:
                    sub_size = sub_archive.seek(0, 2)
                    sub_archive.seek(0)
                    downloaded_total += sub_size
                    if downloaded_total > MAX_ARCHIVE_BYTES:
                        raise GitHubImportError(
                            "Combined repository and submodule archives exceed the size limit."
                        )

                    with zipfile.ZipFile(sub_archive) as sub_zip:
                        sub_entries = sub_zip.infolist()
                        if len(entries) + len(additions) + len(sub_entries) > MAX_FILES:
                            raise GitHubImportError(
                                "Repository and submodules contain too many archive entries."
                            )

                        if any(
                            PurePosixPath(item.filename).name == ".gitmodules"
                            and not item.is_dir()
                            for item in sub_entries
                        ):
                            raise GitHubImportError(
                                f"Nested submodules are not supported yet: {module_path}"
                            )

                        for item in sub_entries:
                            item_path = PurePosixPath(item.filename)
                            if (
                                item_path.is_absolute()
                                or "\\" in item.filename
                                or "\x00" in item.filename
                                or any(part in {"", ".", ".."} for part in item_path.parts)
                            ):
                                raise GitHubImportError(
                                    "Submodule archive contains an unsafe path."
                                )
                            if item.is_dir():
                                continue

                            mode = item.external_attr >> 16
                            if stat.S_ISLNK(mode):
                                raise GitHubImportError(
                                    "Submodule archive contains a symbolic link."
                                )
                            if item.file_size > MAX_FILE_BYTES:
                                raise GitHubImportError(
                                    "Submodule contains a file exceeding the size limit."
                                )

                            parts = item_path.parts[1:]
                            if not parts:
                                continue

                            destination = PurePosixPath(
                                wrapper, module_path, *parts
                            ).as_posix()
                            if destination in occupied:
                                raise GitHubImportError(
                                    "Submodule file conflicts with a repository file."
                                )

                            occupied.add(destination)
                            additions.append((destination, sub_zip.read(item)))

                except (zipfile.BadZipFile, OSError) as exc:
                    raise GitHubImportError(
                        f"GitHub returned an invalid archive for submodule '{module_path}'."
                    ) from exc
                finally:
                    sub_archive.close()

            expanded = tempfile.TemporaryFile(mode="w+b")
            try:
                with zipfile.ZipFile(expanded, "w", zipfile.ZIP_DEFLATED) as output:
                    for item in entries:
                        if item.is_dir():
                            output.writestr(item, b"")
                        else:
                            output.writestr(item, main_zip.read(item))
                    for destination, content in additions:
                        output.writestr(destination, content)

                expanded.seek(0)
                archive.close()
                return expanded
            except Exception:
                expanded.close()
                raise

    except (zipfile.BadZipFile, OSError) as exc:
        raise GitHubImportError("GitHub returned an invalid repository archive.") from exc

def scan_github_repository(
    url: str,
    progress_callback=None,
    *,
    _keep_archive: bool = False,
) -> dict:
    """Inspect a public GitHub repository without extracting or installing it.

    progress_callback receives (phase, current_bytes, total_bytes_or_none).
    """
    full_name, branch, html_url = _repository_details(url)
    owner, repo = full_name.split("/", 1)

    archive_url = (
        f"https://codeload.github.com/{owner}/{repo}/zip/"
        f"refs/heads/{urllib.parse.quote(branch, safe='')}"
    )
    archive = _download_to_tempfile(
        archive_url,
        MAX_ARCHIVE_BYTES,
        (lambda current, total: progress_callback("download", current, total))
        if progress_callback is not None else None,
    )
    try:
        archive = _expand_github_submodules(
            archive,
            full_name,
            branch,
            progress_callback,
        )
    except Exception:
        archive.close()
        raise

    candidates: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    unsafe_entries: list[str] = []
    oversized_entries: list[str] = []
    scripts: list[str] = []
    all_files: list[str] = []

    try:
        zipped = zipfile.ZipFile(archive)
    except (zipfile.BadZipFile, OSError) as exc:
        archive.close()
        raise GitHubImportError("GitHub returned an invalid ZIP archive.") from exc

    with zipped:
        entries = zipped.infolist()
        if len(entries) > MAX_FILES:
            archive.close()
            raise GitHubImportError("Repository contains too many archive entries.")

        for entry in entries:
            raw_name = entry.filename
            path = PurePosixPath(raw_name)

            if (
                path.is_absolute()
                or "\\" in raw_name
                or "\x00" in raw_name
                or any(part in {"", ".", ".."} for part in path.parts)
            ):
                unsafe_entries.append(raw_name[:200])
                continue

            if entry.is_dir():
                continue

            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                unsafe_entries.append(raw_name[:200])
                continue

            if entry.file_size > MAX_FILE_BYTES:
                oversized_entries.append(raw_name[:200])
                continue

            # GitHub ZIP archives have one wrapper directory.
            parts = path.parts[1:]
            if not parts:
                continue

            relative = PurePosixPath(*parts).as_posix()
            all_files.append(relative)

            suffix = PurePosixPath(relative).suffix.lower()
            if suffix in SUSPICIOUS_SUFFIXES or mode & 0o111:
                scripts.append(relative)

            for component in SUPPORTED:
                root_parts = None

                # Common dotfiles layout: .config/<application>/...
                for index in range(len(parts) - 1):
                    if parts[index:index + 2] == (".config", component):
                        root_parts = parts[:index + 2]
                        break

                # Direct layout: <application>/...
                if root_parts is None and parts[0] == component:
                    root_parts = (component,)

                # A repository consisting of a Quickshell config at its root.
                if (
                    root_parts is None
                    and component == "quickshell"
                    and parts == ("shell.qml",)
                ):
                    root_parts = ()

                if root_parts is not None and len(parts) > len(root_parts):
                    root = (
                        PurePosixPath(*root_parts).as_posix()
                        if root_parts else ""
                    )
                    inner = PurePosixPath(*parts[len(root_parts):]).as_posix()
                    candidates[component][root].append(inner)

    # If shell.qml sits at the repository root, treat the repository root
    # as one Quickshell configuration (including its sibling modules/assets).
    if "shell.qml" in all_files:
        candidates["quickshell"][""] = list(all_files)

    # A repository can contain multiple independent Quickshell shells below
    # one .config/quickshell directory. Split them by the directory containing
    # each shell.qml while retaining the legacy component summary below.
    configuration_roots = {}
    for original_root, original_files in candidates.get("quickshell", {}).items():
        entrypoint_dirs = {
            path.rsplit("/", 1)[0] if "/" in path else ""
            for path in original_files
            if path.rsplit("/", 1)[-1] == "shell.qml"
        }
        assigned = set()
        for directory in sorted(entrypoint_dirs, key=len, reverse=True):
            prefix = directory + "/" if directory else ""
            selected = [
                path for path in original_files
                if path not in assigned
                and (
                    not prefix
                    or path == prefix + "shell.qml"
                    or path.startswith(prefix)
                )
            ]
            if not selected:
                continue
            assigned.update(selected)
            config_root = (
                PurePosixPath(original_root, directory).as_posix()
                if original_root and directory
                else original_root or directory
            )
            configuration_roots[config_root] = [
                path[len(prefix):] if prefix else path
                for path in sorted(selected)
            ]
        remaining = [
            path for path in original_files if path not in assigned
        ]
        if remaining:
            configuration_roots[original_root] = sorted(remaining)
        elif not entrypoint_dirs:
            configuration_roots[original_root] = sorted(original_files)

    components = []
    configurations = []
    for component, roots in sorted(candidates.items()):
        ranked = sorted(
            roots.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
        display_name, package = SUPPORTED[component]
        component_configs = []
        roots_for_config = (
            configuration_roots if component == "quickshell" else roots
        )
        ranked_configs = sorted(
            roots_for_config.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
        for source_root, root_files in ranked_configs:
            files = sorted(root_files)
            entrypoints = sorted(
                path for path in files
                if path.rsplit("/", 1)[-1] == "shell.qml"
            )
            entrypoint = (
                entrypoints[0] if len(entrypoints) == 1 else None
            )
            if component == "quickshell":
                config = {
                    "id": "quickshell",
                    "name": display_name,
                    "source_root": source_root,
                    "file_count": len(files),
                    "files": files[:100],
                    "entrypoint": entrypoint,
                    "entrypoint_candidates": entrypoints,
                    "compatibility": (
                        "compatible" if entrypoint else "partial"
                    ),
                }
                configurations.append(config)
                component_configs.append(config)

        selected_root, selected_files = ranked[0]
        selected_entrypoints = sorted(
            path for path in selected_files
            if path.rsplit("/", 1)[-1] == "shell.qml"
        )
        selected_entrypoint = (
            selected_entrypoints[0]
            if len(selected_entrypoints) == 1 else None
        )
        components.append({
            "id": component,
            "name": display_name,
            "source_root": selected_root,
            "destination": f"${{XDG_CONFIG_HOME}}/{component}",
            "payload": f"payload/{component}",
            "file_count": len(selected_files),
            "files": sorted(selected_files)[:100],
            "ambiguous_roots": [root for root, _ in ranked[1:]],
            "dependency": package,
            "entrypoint": selected_entrypoint if component == "quickshell" else None,
            "entrypoint_candidates": selected_entrypoints if component == "quickshell" else [],
        })

    quickshell = next(
        (item for item in components if item["id"] == "quickshell"),
        None,
    )
    compatible_configs = [
        item for item in configurations
        if item["compatibility"] == "compatible"
    ]
    if not configurations:
        compatibility = {
            "status": "unsupported",
            "shell_type": None,
            "entrypoint": None,
            "reason": "No Quickshell configuration was detected.",
        }
    elif not compatible_configs:
        compatibility = {
            "status": "partial",
            "shell_type": "quickshell",
            "entrypoint": None,
            "reason": "Detected Quickshell configurations, but none has exactly one shell.qml entrypoint.",
        }
    else:
        compatibility = {
            "status": "compatible",
            "shell_type": "quickshell",
            "entrypoint": (
                quickshell["entrypoint"]
                if quickshell and quickshell.get("entrypoint")
                else compatible_configs[0]["entrypoint"]
            ),
            "reason": (
                f"{len(compatible_configs)} Quickshell configuration(s) "
                "with an unambiguous shell.qml entrypoint detected."
            ),
        }

    result = {
        "compatibility": compatibility,
        "schema_version": 1,
        "repository": {
            "name": full_name,
            "url": html_url,
            "branch": branch,
        },
        "components": components,
        "configurations": configurations,
        "summary": {
            "files_scanned": len(all_files),
            "components_detected": len(components),
            "scripts_flagged": len(scripts),
            "unsafe_entries": len(unsafe_entries),
            "oversized_entries": len(oversized_entries),
        },
        "scripts": scripts[:100],
        "unsafe_entries": unsafe_entries[:100],
        "oversized_entries": oversized_entries[:100],
        "unclassified_files": max(
            0,
            len(all_files) - sum(item["file_count"] for item in components),
        ),
        "dry_run": True,
        "installation_performed": False,
    }
    if _keep_archive:
        archive.seek(0)
        result["_archive"] = archive
    else:
        archive.close()
    return result
