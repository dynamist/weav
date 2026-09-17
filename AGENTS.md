# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

weav is a Jinja2 template compiler CLI. It renders templates with data from YAML, JSON and TOML files, stdin, environment variables and command output, supporting multiple data sources with deep merge, key-value parameters, and flexible template search paths.

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
uv run tox                           # test Python 3.11-3.14 + lint + type

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

### Data Sources (`datasources.py`)
- `DataSource` - Protocol (structural typing): a `name` property and `load() -> dict`
- Implementations: `YamlDataSource`, `JsonDataSource`, `TomlDataSource`,
  `StdinDataSource`, `ExecDataSource`, `KeyvalDataSource`, `EnvDataSource`
- `ContextBuilder` - loads sources in order and deep-merges them (last wins)
- `parse_data_spec()` - parses the `[KEY][:FORMAT]=SOURCE` spec grammar
- `build_sources_from_args()` - bridges CLI arguments to `DataSource` objects
- `get_parser()` / `_PARSERS` - format name to parser callable
- `DataSourceError` - raised for bad formats and failed commands

### Utilities (`utils.py`)
- `deep_merge()` - recursive dictionary merge (lists are replaced, not concatenated)
- `load_and_wrap()` - parse a stream with optional key wrapping (lists/scalars
  wrapped under "data" when no key is given)
- `mangle_keyval()` - parse KEY=VAL strings

### Data Flow
1. CLI parses arguments → `compile_template()`
2. Template located via `find_template()`
3. `build_sources_from_args()` turns specs into `DataSource` objects
4. `ContextBuilder` loads and deep-merges them in precedence order:
   `--data` → `--exec` → `--env` → `--keyval` (last wins)
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

## Dependency Updates

Renovate (Mend app, `renovate.json`) is the only bot. Dependabot *alerts* stay enabled because
Renovate reads them for `vulnerabilityAlerts`, but its automated security PRs are turned off.

- Runtime deps under `[project.dependencies]` keep loose `>=` floors: weav ships as a wheel and
  must not over-constrain consumers. Renovate never bumps them; `lockFileMaintenance` (weekly
  `uv lock --upgrade`) is what keeps the resolved versions and transitive deps current.
- Dev/test tooling lives only in `[dependency-groups]` (installed with `uv sync --group dev`),
  never as a published extra, and uses `rangeStrategy: bump` so the floors track the revs pinned
  in `.pre-commit-config.yaml`. That is what makes the `ruff`, `uv` and `mypy` groups update both
  files in one PR.
- `minimumReleaseAge: "5 days"` exists to stay behind `[tool.uv] exclude-newer = "4 days"` in
  `pyproject.toml`. uv resolves as if four days ago, so a fresher version would be proposed but
  could not be locked. Change the two together or lock file updates start failing.

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
