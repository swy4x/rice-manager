# Rice Manager

**Your Linux desktop. Your rices. One manager.**

Import, preview, install and switch Linux desktop configurations.

## Features

- GitHub dotfiles importing
- Git submodule support
- Installation preview
- Quickshell configuration discovery
- Shell switching and management
- Persistent shell registry
- CLI and GUI

## Installation

```bash
git clone https://github.com/swy4x/rice-manager.git
cd rice-manager
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Launch

```bash
rice-manager-gui
```

## Tests

```bash
python -m unittest discover -s tests -v
```

## Safety

Preview before installing. Protect existing configurations. Review third-party dotfiles before running them.

Platform: Arch Linux | Python 3.11+

https://github.com/swy4x/rice-manager
