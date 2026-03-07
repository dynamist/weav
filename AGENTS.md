# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

weav is a Jinja2 template compiler CLI. It renders templates with data from YAML files, supporting multiple data sources with deep merge, key-value parameters, and flexible template search paths.

Note: The `weav` package on PyPI is unrelated to this project.

## Common Commands

```bash
# Install dependencies
uv sync --group dev

# Run the CLI
uv run weav --help
uv run weav template.j2 --data config.yaml
uv run weav template.j2 --keyval name=World

# Run tests
uv run pytest                        # quick test with coverage
uv run pytest tests/test_cli.py      # run single test file
uv run pytest -k test_name           # run specific test
uv run tox                           # test Python 3.11-3.12 + lint + type

# Lint and format
uv run ruff check weav tests         # lint
uv run ruff format weav tests        # format
uv run tox -e lint                   # lint via tox
uv run tox -e format                 # auto-fix and format

# Type checking
uv run mypy weav
uv run tox -e type

# Merge PRs (rebase only - merge and squash are disabled)
gh pr merge --rebase --delete-branch
```

## Architecture

### CLI Layer (`cli.py`)
- Uses `typer` for argument parsing with type-annotated function signatures
- Single command interface: `weav TEMPLATE [OPTIONS]`
- Shell completion for template names via `complete_template()` callback
- Entry point: `app = typer.Typer()` → `main()`

### Template Layer (`template.py`)
- `compile_template()` - main entry point for rendering
- `find_template()` - locates templates in search paths
- `get_template_paths()` - returns search order:
  1. Package bundled templates (`weav/templates/`)
  2. `./templates` in current directory
  3. `~/.local/share/weav/templates` (user data)
  4. `~/Documents/weav/templates` (user documents)
- `parse_data_args()` - handles `KEY=FILE` syntax for data wrapping

### Utilities (`utils.py`)
- `deep_merge()` - recursive dictionary merge
- `load_and_wrap()` - load YAML with optional key wrapping (lists wrapped under "data" by default)
- `mangle_keyval()` - parse KEY=VAL strings

### Data Flow
1. CLI parses arguments → `compile_template()`
2. Template located via `find_template()`
3. YAML files loaded, wrapped, and deep-merged
4. Key-value params override merged data
5. Jinja2 renders template with final context

## Version Management

Version is defined in `pyproject.toml`. Access it via:
```python
from weav import __version__
```

Or:
```python
from importlib.metadata import version
version("weav")
```

## Release Workflow

Releases are triggered by pushing a git tag matching `v*`:

```bash
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

**Artifacts produced:**
- Python wheel and sdist → GitHub Releases (not published to PyPI)
- Standalone executables for 6 platforms → GitHub Releases:
  - `weav-linux-amd64`, `weav-linux-arm64`
  - `weav-macos-amd64`, `weav-macos-arm64`
  - `weav-windows-amd64.exe`, `weav-windows-arm64.exe`
- Sigstore signatures (`.sigstore.json`) for all executables except Windows ARM64
