# Rice Manager

A safety-first rice and dotfile profile manager for Arch Linux, starting with Hyprland and Quickshell.

> **Status: early development.** The current version is a read-only system inspection prototype. Profile activation, backup/restore, GitHub importing, and the Quickshell GUI are not implemented yet.

## Goals

- Keep multiple desktop rice profiles isolated.
- Inspect a system and discover relevant configuration locations.
- Back up managed files before any change.
- Preview changes before applying them.
- Switch profiles transactionally, with rollback on failure.
- Provide a Quickshell interface backed by a small Python core.

## Safety principles

- No automatic deletion of user files.
- No silent replacement of existing configuration.
- No `sudo` operations in the manager.
- No shell evaluation of imported dotfiles.
- Every future write operation must have a preview and a recoverable backup.
- System-wide configurations (such as `/etc/xdg`) are detected but never modified automatically.

## Current prototype

The initial CLI only inspects the environment:

```bash
python -m rice_manager inspect
python -m rice_manager inspect --json
```

It reports selected configuration paths and whether they are directories, files, or symlinks. It does not modify the system.

## Development

Requirements: Python 3.11 or newer. The prototype uses only the Python standard library.

```bash
git clone https://github.com/swy4x/rice-manager.git
cd rice-manager
python -m rice_manager inspect
```

For local development, install the package in editable mode:

```bash
python -m pip install -e .
rice-manager inspect
```

## Roadmap

- [x] Repository initialized
- [x] Read-only environment inspection CLI
- [ ] Profile manifest and validation
- [ ] Backup and restore engine
- [ ] Dry-run switch planner
- [ ] Transactional profile activation
- [ ] Quickshell GUI
- [ ] Git repository importer
- [ ] Dependency detection and optional install plans

## License

MIT. See [LICENSE](LICENSE).
