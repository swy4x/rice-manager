# Rice Manager

A safety-first rice and dotfile profile manager for Arch Linux, starting with Hyprland and Quickshell.

> **Status: early development.** Version 0.2 adds read-only profile manifest validation and component inspection. Backup/restore, profile activation, GitHub importing, and the Quickshell GUI are not implemented yet.

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
- Every future write operation must have a preview and a recoverable backup.
- System-wide configurations (such as `/etc/xdg`) are detected but never modified automatically.

## Current commands

Inspect the current environment:

```bash
rice-manager inspect
rice-manager inspect --json
```

Validate the example Caelestia profile manifest:

```bash
rice-manager profile validate examples/caelestia/manifest.json
```

Inspect the component paths declared by that manifest (read-only):

```bash
rice-manager profile inspect examples/caelestia/manifest.json
```

A manifest describes components; it does not copy, activate, link, or modify them. The example includes a system-scoped Caelestia path marked read-only. Adjust paths in your own manifest for your machine.

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
- [ ] Backup and restore engine
- [ ] Dry-run switch planner
- [ ] Transactional profile activation
- [ ] Quickshell GUI
- [ ] Git repository importer
- [ ] Dependency detection and optional install plans

## License

MIT. See [LICENSE](LICENSE).
