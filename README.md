# Rice Manager

A safety-first rice and dotfile profile manager for Arch Linux, starting with Hyprland and Quickshell.

> **Status: early development.** Version 0.7 connects the Quickshell dashboard to the Python read-only preflight planner. Profile activation and GitHub importing are not implemented yet.

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
rice-manager profile plan examples/caelestia/manifest.json
rice-manager profile plan examples/caelestia/manifest.json --json
```

Back up writable user components:

```bash
rice-manager profile backup examples/caelestia/manifest.json
```

Backups default to `~/.local/share/rice-manager/backups`. An alternate destination can be provided with `--destination /path/to/backups`. Only existing `user` components not marked `read_only` are copied. System-scoped components are always skipped. Missing required components or type mismatches abort the operation. Backups are staged and published only after successful copying.

A backup contains `backup.json` metadata and a `components/` directory. Preview a restore first; preview mode never changes files:

```bash
rice-manager profile restore /path/to/backup
```

Apply only after reviewing the paths:

```bash
rice-manager profile restore /path/to/backup --apply
```

When applying, existing destinations are copied to a timestamped `pre-restore-*` safety snapshot before replacement. Restore refuses destinations outside your home directory, symlink destinations, invalid metadata, and unsafe backup paths. System-wide configuration is not restored.

The `profile plan` command is a dry-run preflight only. It checks user component paths, required components, declared file/directory types, and unsafe destinations. System-scoped and read-only components are skipped. It does not install profile files or switch the active desktop; profile payload storage and transactional activation are future work.

## Quickshell UI prototype

The Quickshell dashboard reads the example manifest through the Python CLI and displays live read-only preflight results. It does not execute profile actions. Run it directly from the repository without installing or changing your Quickshell configuration:

```bash
qs -p ./ui
```

This uses Quickshell's standard floating application window. The UI invokes `rice-manager profile plan --json` as a child process (without a shell) and parses its output. The prototype is isolated under `ui/`; it does not touch `~/.config/quickshell` or the system Caelestia files. Click the status badge to refresh the preflight.

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
- [x] Read-only profile activation preflight planner
- [ ] Transactional profile activation
- [x] Initial Quickshell UI prototype
- [x] Connect GUI to Python core (read-only preflight)
- [ ] Git repository importer
- [ ] Dependency detection and optional install plans

## License

MIT. See [LICENSE](LICENSE).
