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
uv run weav render template.j2 --data config.yaml
uv run weav render template.j2 --keyval name=World
uv run weav frontmatter doc.md --upsert origin=$(git rev-parse HEAD)

# Run tests
uv run pytest                        # quick test with coverage
uv run pytest tests/test_cli.py      # run single test file
uv run pytest -k test_name           # run specific test
uv run tox                           # test Python 3.11-3.14 + lint + type
uv run tox -e smoke                  # build a wheel, install it, run the CLI

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
- Two commands: `weav render TEMPLATE [OPTIONS]` and `weav frontmatter FILE [OPTIONS]`
- Shell completion for template names via `complete_template()` callback
- Entry point: `app = typer.Typer(cls=WeavGroup)` with an `@app.callback()` that
  owns the global `--version` and `--skill`
- `--skill` prints `weav/SKILL.md` verbatim to stdout and exits 0 with an empty
  stderr, so `weav --skill > ~/.claude/skills/weav/SKILL.md` just works. It is
  eager like `--version`: a bare `weav` answers with help on stderr and exit 2,
  which would otherwise win. It uses `typer.echo`, **not** the module `console` --
  rich would rewrap the Markdown and eat its brackets.
- `WeavGroup` overrides `resolve_command()` to dispatch an unrecognised,
  non-option first argument to `render`, keeping the pre-subcommand
  `weav TEMPLATE ...` form working with a stderr warning. It returns the **full**
  `args` rather than Click's usual `args[1:]`, because `args[0]` is the template
  rather than a command name. Guarded on a leading `-` specifically, since Click
  also treats `/` as an option prefix and would misread absolute template paths.
  **Remove this class at 1.0.**
- `WeavGroup.resolve_command()` deliberately leaves its Click-typed parameters
  dynamic. typer stopped building `TyperGroup` on `click.Group` in 0.26 and now
  uses a vendored `typer._click`, and typer 0.27 dropped `click` as a dependency
  altogether -- so the concrete classes differ by typer version and `click` may
  not even be installed. Do not `import click` here to tighten the annotations;
  it would add a dependency and still be wrong on one version or the other. See
  dynamist/phabfive#330. Verified working on typer 0.24.1 and 0.27.2.

### Agent Help Footer (`agents.py`)
- `AGENT_HELP_FOOTER` - the resources block that closes every help page, and
  `AgentFooterMixin` / `AgentFooterCommand`, which write it
- Mixed into `WeavGroup` for the root and passed as `cls=` to both leaf commands.
  phabfive carries its equivalent block on groups only, but weav has no
  intermediate groups, so `weav render --help` is where an agent lands
- The block is written line by line by `format_epilog` rather than passed as
  Typer's `epilog=`, because click's default runs the epilog through
  `write_text`, which rewraps the paragraphs and flattens the indentation the
  block is made of. `tests/test_agent_help_footer.py` asserts on an indented line
  to catch a regression back to that
- Those tests run **out of process**. `weav/cli.py` sets `TYPER_USE_RICH=0` as it
  imports, which only takes effect if nothing imported typer first; under
  `CliRunner`, `typer.testing` has already imported typer with rich enabled, and
  typer then renders help through rich, which never calls `format_epilog`
- `tests/test_skill.py` also extracts every `weav ...` invocation from the
  skill's fenced bash blocks and asserts both the command path and each long
  option resolve in the click tree -- a skill that documents an option that no
  longer exists is worse than no skill

### Agent Skill (`SKILL.md`)
- Package data, read via `importlib.resources.files("weav")`, the same mechanism
  `get_template_paths()` uses
- Shipped in the wheel with no `pyproject.toml` change: hatchling has no
  `[tool.hatch.build]` section and takes the whole `weav/` tree, as it already
  does for `py.typed`. The one-file executables need `--collect-data weav` in
  `.github/workflows/release.yml`
- Every claim in it is verified against the built CLI rather than read off the
  source. Re-verify when the behaviour it documents changes

### Frontmatter Layer (`frontmatter.py`)
- `FrontmatterDocument` - a document split into a YAML mapping and a body;
  `from_file()`, `parse()`, `patch()`, `dumps()`, `write()`
- `FrontmatterError` - raised only when a declared block fails to parse
- Uses `ruamel.yaml` in round-trip mode (`YAML(typ="rt")`, `preserve_quotes`) so
  comments, quoting and block scalars survive an edit. Dumps via `io.StringIO`;
  the `ruamel.yaml.string` package is deliberately **not** a dependency.
- Parse rules, all three of which exist because writes are in place by default
  and a mis-split would destroy the document:
  1. Anchor on a **leading** `---` and close on the **first** `---`/`...` line
     after it. Never scan for the last one -- a `---` thematic break in the body
     is not a delimiter. The opening delimiter is **required**: without it a
     Markdown setext heading (`Title: subtitle` underlined by `---`) parses as a
     mapping and would be silently promoted into metadata. Comparison is exact
     on the rstripped line at both ends, so `----` and an indented `  ---` do
     not match; the raw lines are retained so whitespace round trips.
  2. The parsed value must be a mapping. Body prose loaded as a scalar or
     sequence is not frontmatter.
  3. A parse error is fatal only when a leading `---` was present. Without one
     we are guessing, and guessing must never abort or destroy.
- Reads and writes UTF-8 explicitly, and restores the source BOM and line ending.
- `write()` resolves the path first, writes a `NamedTemporaryFile` in the
  resolved parent, copies the original's mode and calls `temp.replace(target)`.
  Three properties depend on that shape and are easy to "simplify" away:
  resolving means a **symlink is followed rather than replaced**, so the
  canonical file is updated instead of being left stale behind a link that
  became a regular file; the temp file must live in the *resolved* parent or
  the rename can cross a filesystem and raise; and replacing rather than
  truncating is what makes a crash mid-write unable to destroy the original.
  Ownership, ACLs and xattrs are not carried over, and a hardlink's count is
  broken -- both inherent to replacing.
- `write()` returns `False` and leaves the file (and its mtime) alone when the
  bytes are unchanged, so a no-op invocation never produces a diff.

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
- `mangle_commas()` - flatten comma-separated strings into a list (used by
  `weav frontmatter --delete`)

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
Nothing therefore raises a fix PR for a vulnerability that only exists in `uv.lock` - the alert
shows up under Security and the weekly lock refresh (or `uv lock --upgrade-package NAME`) is what
resolves it.

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
- Leave `osvVulnerabilityAlerts` off. The hosted app cannot download the OSV database, so it only
  logs "Unable to read vulnerability information" as a repository problem
  (renovatebot/renovate#22502).

## Release Version Guard (`scripts/check_version.py`)

Every artifact is named after `pyproject.toml` while the release is named after
the tag, so the two disagreeing publishes a release full of artifacts for a
different version. The two are set by hand and only convention puts them in the
same commit.

- Its own `check-version` job, which `build` and `build-executables` both
  `needs:`, so a mismatch is answered in seconds rather than after six
  PyInstaller runs, and nothing is built or signed in the meantime
- Compares with `canonical_version()` imported from `smoke.py`, so the two ends
  of the pipeline cannot drift apart on what counts as the same version: tag
  `v0.3.0-rc.1` and the `0.3.0rc1` hatchling builds are equal, `0.3.0.dev0` is
  not
- Also refuses a version containing `dev` outright. Equality alone would pass a
  `v0.3.0-dev.0` tag over a `0.3.0.dev0` `pyproject.toml`, which is
  self-consistent and still means the tag was pushed before the release bump
- The smoke tests check it again from the other end, with
  `--expect-version "${GITHUB_REF_NAME#v}"`, against the version the built
  artifact reports at runtime -- that one catches a binary built from the wrong
  revision, which a source-level comparison cannot see
- `tests/test_check_version.py` covers both directions, including the phabfive
  case and the final-tag-over-an-rc-version case

## Release Smoke Test (`scripts/smoke.py`)

Ported from phabfive, where it exists because v0.10.0-rc.1 shipped six standalone
executables that could not start at all and every release job still reported
success: nothing in the pipeline ran what it had just built.

- One script for every artifact, so the checks cannot drift apart:
  `--executable` for each one-file build, `--venv` for a wheel or sdist
  installed into a clean venv. `uv run tox -e smoke` is the local form
- Imports nothing outside the standard library. It runs on a bare CI runner
  before anything has been installed for it, so it cannot use pytest
- Runs in `build-executables` **before** the cosign step, so a broken build is
  never signed, and in `verify-wheel` across three operating systems and Python
  3.11 and 3.14, with the sdist covered on one cell. `github-release` names
  both as gates
- `verify-wheel` installs with plain `pip`, never `uv`: uv would apply `uv.lock`
  and the `exclude-newer` window, and resolve nothing the way a user does. An
  undeclared or wrongly floored dependency is invisible under the lock file
- Each check gets a fresh `HOME` and runs with the cwd inside it, so a template
  installed on the machine cannot satisfy a check the artifact should have
  failed
- `--skill` is the check that earns its place: SKILL.md is data, not a module,
  so it depends on `--collect-data weav` in the PyInstaller line and on
  hatchling taking the whole `weav/` tree into the wheel. Building without
  `--collect-data weav` was tried, and the binary passes every other check here
- `check_completion()` derives the completion variable from the `Usage:` line
  rather than hardcoding `_WEAV_COMPLETE`, because the release renames every
  executable to `weav-<os>-<arch>` first, and follows typer's rule rather than
  click 8.2's -- they disagree on exactly one asset, the Windows `.exe`
- `scripts/**/*.py` is exempt from `ANN` and `S603` in `pyproject.toml`; the
  script's job is running subprocesses, and it is release tooling, not library
  code

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

**Release candidates.** A tag whose name contains `-rc` builds, signs and uploads
exactly what a final tag does; the only difference is that the GitHub Release is
marked as a prerelease, so it stays off the repository's "Latest" badge and out
of the `/releases/latest` redirect that install instructions follow. phabfive's
RC tags additionally skip PyPI and the floating `X.Y`/`latest` image tags; weav
publishes to neither, so the prerelease flag is the entire difference here. What
an RC buys is the same thing it buys there: a full rehearsal of the pipeline on
real runners -- six PyInstaller builds, six cosign signings, the release
assembly -- without moving what `weav` means to anyone tracking the latest
release.

The tag spelling is load-bearing. The workflow matches the literal string `-rc`,
so `v0.3.0rc1` -- the canonical PEP 440 form -- would go out as a **final**
release. Tag `v0.3.0-rc.1`.

`pyproject.toml` keeps the canonical spelling instead, `0.3.0rc1`, which is what
hatchling normalises to and therefore what the wheel is named. Set it in the same
commit as the tag. phabfive tagged `v0.10.0-rc.1` while its `pyproject.toml`
still read `0.10.0-dev.0` and the release carried artifacts named after the dev
version; nothing in phabfive's pipeline notices that. weav's does, twice over --
see below.

```bash
# pyproject.toml: version = "0.3.0rc1"
# CHANGELOG.md:   retitle "# Unreleased" to the release being rehearsed
git commit -am "Release v0.3.0-rc.1"
git push origin main
git tag -a v0.3.0-rc.1 -m "Release v0.3.0-rc.1"
git push origin v0.3.0-rc.1
```

The final tag is the same sequence with `version = "0.3.0"` and `v0.3.0`.
Afterwards bump `pyproject.toml` to `0.4.0.dev0`, so a working tree never claims
to be a released version.
