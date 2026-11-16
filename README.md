# Rice Manager

A safety-first rice and dotfile profile manager for Arch Linux, starting with Hyprland and Quickshell.

> **Status: early development.** Version 0.4 adds preview-first backup restoration with automatic safety snapshots of existing user configuration. Profile activation, GitHub importing, and the Quickshell GUI are not implemented yet.

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
- No shell evaluation of imported dotfiles or manifest values.
- Backups are explicit and never overwrite an existing backup.
- System-wide configurations (such as `/etc/xdg`) are detected but never modified or backed up automatically.
- Restore is limited to destinations inside the user's home directory. System-wide and read-only configuration is never restored.

## Commands

Inspect the current environment:

```bash
rice-manager inspect
rice-manager inspect --json
```

Validate and inspect the example profile:

```bash
rice-manager profile validate examples/caelestia/manifest.json
rice-manager profile inspect examples/caelestia/manifest.json
```

Back up writable user components:

```bash
rice-manager profile backup examples/caelestia/manifest.json
```

Backups default to `~/.local/share/rice-manager/backups`. An alternate destination can be provided with `--destination /path/to/backups`. Only existing `user` components not marked `read_only` are copied. System-scoped components are always skipped. Missing required components or type mismatches abort the operation. Backups are staged and published only after successful copying.

A backup contains `backup.json` metadata and a `components/` directory. Preview a restore first; preview mode never changes files:\n\n```bash\nrice-manager profile restore /path/to/backup\n```\n\nApply only after reviewing the paths:\n\n```bash\nrice-manager profile restore /path/to/backup --apply\n```\n\nWhen applying, existing destinations are copied to a timestamped `pre-restore-*` safety snapshot before replacement. Restore refuses destinations outside your home directory, symlink destinations, invalid metadata, and unsafe backup paths. System-wide configuration is not restored.

## Manifest format

Manifest schema version 1 is JSON. Each component declares an ID, display name, kind, source path, and scope (`user` or `system`). Optional flags mark required components and read-only sources. The only supported path variables are `${HOME}`, `${XDG_CONFIG_HOME}`, and `${XDG_DATA_HOME}`; they are expanded as literal paths, never as shell code.

## Development

Requirements: Python 3.11 or newer. Runtime uses only the Python standard library.

```bash
git clone https://github.com/swy4x/rice-manager.git
cd rice-manager
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
rice-manager inspect
```

Run tests:

```bash
python -m unittest discover -s tests
```

## Roadmap

- [x] Repository initialized
- [x] Read-only environment inspection CLI
- [x] Profile manifest and validation
- [x] Explicit user-component backup engine
- [x] Preview-first restore engine
- [ ] Dry-run switch planner
- [ ] Transactional profile activation
- [ ] Quickshell GUI
- [ ] Git repository importer
- [ ] Dependency detection and optional install plans

## License

MIT. See [LICENSE](LICENSE).
