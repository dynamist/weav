# Unreleased

## New Features

* **weav is usable as a library** - the programmatic surface is exported from
  the top level, so `from weav import FrontmatterDocument, compile_template`
  works without knowing the module layout. `__all__` is the supported promise:
  `FrontmatterDocument`, `compile_template`, `find_template`,
  `get_template_paths`, `ContextBuilder`, `DataSource`, the seven data source
  classes, `FrontmatterError`, `TemplateError`, `DataSourceError`, `deep_merge`
  and `__version__`. Each module also gained its own `__all__` covering its full
  public surface; a name listed there but not at the top level - the
  `[KEY][:FORMAT]=SOURCE` spec parser, the argv mangling, the YAML indentation
  machinery - is still public and still importable from its module, just not
  part of the narrower promise. Existing submodule imports are unchanged and are
  not deprecated.

  The names are resolved lazily (PEP 562), so `import weav` pulls in no
  third-party module at all and costs about a millisecond rather than ninety.
  The module holding a name is imported the first time the name is touched,
  which means a consumer of `FrontmatterDocument` alone never imports Jinja2,
  and nothing that merely touches an attribute on `weav` can trip the
  `TYPER_USE_RICH` environment variable that `weav/cli.py` sets as it imports.
  Closes #90.

## Bug Fixes

* **`import weav` no longer fails on a source tree** - `weav/__init__.py` read
  its version from the installed distribution's metadata as it imported, so a
  vendored copy, a checkout that was never installed, or any `sys.path` use
  raised `PackageNotFoundError` before the package existed. The version is now
  read on first access and falls back to `0.0.0+unknown` when there is no
  metadata to read.

  The fallback is not allowed to hide a broken build: `scripts/smoke.py`
  rejects that exact string, because it matches the version pattern and a
  release artifact that lost its `dist-info` would otherwise pass a smoke run
  that was not given `--expect-version`. That script also gained a library
  import check, run against the wheel installed into a clean venv, asserting
  that every name in `__all__` resolves and that a bare `import weav` pulls in
  neither Jinja2 nor typer. Closes #88.

* **`weav frontmatter` keeps the document's own indentation** - An edit no
  longer flattens an indented block sequence or renormalises a mapping indented
  by anything but two. `ruamel.yaml` carries a single global indentation setting
  rather than recording one per node, so re-dumping a block emitted it in the
  library's style whatever the author had written; `weav frontmatter doc.md
  --upsert title=$(current value)` would rewrite the file, and stamping a docs
  tree mixed the reindentation into the same commit as the intended change.

  The block's own style is now measured before it is re-emitted, from the one
  case that is unambiguously structure: a line whose preceding line is a key
  that opened a block. Block scalar bodies are skipped, so a `- ` inside a
  literal scalar is not mistaken for a sequence entry. A block that mixes two
  styles is left to the emitter, since matching one would reflow the other.

* **`weav frontmatter` no longer re-wraps long values** - `ruamel.yaml` folds a
  plain or quoted scalar at its default width of 80 columns, so a value the
  author wrote on one line came back wrapped, with a **trailing space** on the
  line the fold broke. An editor that strips trailing whitespace on save, or a
  `trailing-whitespace` pre-commit hook, takes that space straight back out, so
  the two then take turns rewriting the same line.

  The emitter is given a line width no real line reaches, so a long value is
  emitted as it was written however long it is. A document has no width the way
  it has an indentation style, so there is nothing to measure and the setting is
  unconditional. Nothing is lost by it: a plain scalar's own line breaks are not
  round tripped at either width, so a hand-wrapped value is joined now where it
  used to be re-broken at the library's points rather than the author's. A
  folded block scalar (`>`) is the construct that does keep its breaks, and one
  whose lines run past 80 now round trips too.


# 0.3.0 (2026-09-19)

## New Features

* **`weav --skill` agent skill** - Print a skill file describing the CLI for AI
  coding agents: `weav --skill > ~/.claude/skills/weav/SKILL.md`. The file is
  shipped as package data and written to stdout verbatim with nothing on stderr,
  so the redirect is all there is to it. It documents the parts an agent
  otherwise gets wrong: that only `.json` and `.toml` suffixes pick a parser
  while everything else is read as YAML, that `--keyval` values are strings and
  so `count=0` is truthy, that a later source replaces a list rather than
  extending it, that `--env ''` puts the whole environment into the context, and
  that `weav frontmatter` rewrites the file unless `--stdout` is passed.

  Every help page - the root and both subcommands - now ends with a short
  resources block naming the template search paths, the merge order and the
  flag, because an agent that only reads `--help` would otherwise never learn
  the flag exists.

* **`weav frontmatter` command** - Add, change and remove keys in a Markdown or
  reST document's YAML frontmatter:
  `weav frontmatter contract.md --upsert origin=$(git rev-parse HEAD)`. Comments,
  quoting and block scalars survive the edit, as do a byte order mark, CRLF line
  endings and the exact delimiter lines; a document whose content did not change
  is not rewritten at all. Ported from Dynamist's proprietary frontmatter
  tooling and relicensed to Apache-2.0 by the copyright holder: the document
  model from `dynatron-lib-frontmatter`, the command surface from
  `dynatron-cli-frontmatter`, and the `--upsert` and `--delete` argument
  parsing from `dynatron-lib-utils`.

  The port fixes a defect in the original that could destroy documents: it split
  on the *last* `---` anywhere in the file, so a thematic break in the body was
  mistaken for the closing delimiter and everything above it was parsed as YAML.
  weav anchors on a leading `---` and closes on the first `---` or `...` line
  after it, treats anything that does not parse as a mapping as body content,
  and never fails on a document that did not declare a frontmatter block. The
  opening delimiter is required, so a Markdown setext heading such as
  `Overview: the big picture` underlined by `---` stays a heading instead of
  being consumed as metadata. A document whose frontmatter is closed but never
  opened by `---` is therefore body content, and needs a leading `---` added.

  Note weav edits **in place** by default, where the original only ever wrote to
  stdout. Pass `--stdout` for the old behaviour.
* **`weav frontmatter` preserves comments, permissions and separators in values** - a comment-only frontmatter block, a block comment alongside keys, and the file mode all survive an edit; `--upsert "title=Hello, World"` no longer crashes; and an indented `  ---` is treated as a thematic break rather than an opening delimiter. Writes go through a temporary file and an atomic rename, so a crash mid-write cannot destroy the original; a symlink is followed rather than replaced, so the canonical file is the one updated.
* **`weav render` command** - The template renderer is now an explicit
  subcommand, alongside `weav frontmatter`. The renderer itself is not new: it
  is what weav has done since 0.1.0, and it began as Dynamist's proprietary
  `dynatron-cli-template`, open sourced and relicensed to Apache-2.0 by the
  copyright holder. `weav/utils.py` carries ports of the `deep_merge`,
  `load_and_wrap` and `mangle_keyval` helpers it used, which came from
  `dynatron-lib-utils` rather than from the tool itself.
* **`--exec` / `-x` command data sources** - Run a command and use its stdout
  as template data: `weav render report.j2 --exec tasks:yaml='phabfive --format=yaml
  maniphest search'`. Repeatable, so several query results can feed one
  template. Commands run without a shell (argv is split with `shlex`), their
  stderr is passed through, and a non-zero exit or unparseable output aborts
  rendering with exit code 1 instead of producing a silently incomplete
  document.
* **Explicit format override** - Any `--data` or `--exec` spec may name its
  parser as `KEY:FORMAT=SOURCE`, where FORMAT is `yaml`, `json` or `toml`.
  This makes stdin and extensionless paths usable with non-YAML formats, e.g.
  `--data :json=-` or `--data cfg:yaml=/dev/fd/63`.

## Bug Fixes

* Autoescape no longer HTML-escapes substituted values in non-HTML templates
  (`.md.j2`, `.txt.j2`, plain `.j2`, ...), which previously rendered `"` as
  `&#34;`. Templates named `*.html`, `*.htm`, or `*.xml` (with or without a
  trailing `.j2`) still autoescape.
* `--data KEY=FILE` / `--data KEY=-` now always namespaces the data under
  `KEY`. Previously the key was silently ignored when the data was a mapping,
  so `{{ KEY.field }}` rendered as an empty string. YAML/JSON/stdin sources
  now match the (already correct) TOML behavior.
* A data path containing `=` but no key prefix (such as
  `--data ./my=dir/config.yaml`) is no longer misparsed as `KEY=FILE`. A
  `KEY=` prefix is now only recognised when KEY looks like a name.

## Upgrade Notes

* The bare `weav TEMPLATE ...` form is **deprecated**. It still renders, and is
  dispatched to `weav render TEMPLATE ...`, but it now prints a warning to
  stderr and will be removed in weav 1.0. Scripts should move to
  `weav render ...`.
* A template whose filename collides with a command name is no longer reachable
  by the bare form, because the command wins. Use `weav render render` or
  `weav render ./render`.
* `weav TEMPLATE --version` no longer works; `--version` is now a global option,
  so use `weav --version`.
* `weav.datasources.parse_data_spec()` now returns a 3-tuple
  `(source, wrapper_key, format)` instead of a 2-tuple. Only affects code
  using the programmatic API directly.
* `weav.template.compile_template()` gained a keyword-only `exec_commands`
  argument; existing calls are unaffected.
* Templates that passed a mapping with `--data KEY=FILE` and relied on the
  mapping's keys landing at the top level of the context must either drop the
  `KEY=` prefix or access values as `{{ KEY.field }}`.

## Other Notes

* **Release candidate tags** - A tag containing `-rc`, such as `v0.3.0-rc.1`,
  now builds, signs and uploads everything a final tag does, but its GitHub
  Release is marked as a prerelease and so stays out of `/releases/latest`.
  Ported from phabfive, where the same flag lets a release be rehearsed end to
  end on real runners before it becomes the one people install.

* **Every release artifact is now run before it ships** - `scripts/smoke.py`
  executes each of the six standalone executables before it is signed, and the
  wheel and sdist after installing them into a clean venv with plain `pip` on
  three operating systems and two Python versions. The GitHub Release depends
  on all of it passing, so a build that cannot start stops the release instead
  of being published. Run the same checks locally with `uv run tox -e smoke`.

  Also ported from phabfive, where it was written after v0.10.0-rc.1 shipped
  six executables that could not start at all while every job reported success,
  because nothing in the pipeline ever ran what it built. The checks that matter
  most for weav are the ones no unit test can reach: `weav --skill` reads
  SKILL.md out of the bundle, which depends on `--collect-data weav` surviving
  in the PyInstaller line, and `--version` reads the distribution metadata
  before typer parses an argument.

* **The macOS Intel build is now actually Intel** - `weav-macos-amd64` was
  built on `macos-14`, which is an arm64 label; every macOS asset of v0.2.0 is
  an arm64 Mach-O, so the file an Intel Mac downloads fails to start with "Bad
  CPU type in executable". It is now built on `macos-15-intel`, the x86_64 label
  GitHub introduced when `macos-13` was retired. The arm64 row moved from the
  floating `macos-latest` to a pinned `macos-15`, so the minimum macOS version a
  release binary requires does not rise on its own when GitHub migrates the
  alias.

  `macos-14` is separately deprecated: jobs using it fail during brownouts from
  October 5th 2026 and the image is unsupported from November 2nd
  (actions/runner-images#13518).

* **An executable that does not match its name no longer releases** -
  `scripts/check_arch.py` reads each built executable's ELF, Mach-O or PE
  header and refuses one whose architecture is not the one its asset name
  promises. It runs before signing. The smoke test cannot cover this, because it
  runs each binary on the machine that built it, where the architecture is
  native by definition; only the finished artifact shows it. Ported from
  phabfive, and verified against weav's own releases: it passes all six
  v0.3.0-rc.1 assets and refuses v0.2.0's `weav-macos-amd64`.

* **A tag that disagrees with `pyproject.toml` no longer releases** -
  `scripts/check_version.py` runs before anything is built and refuses a tag
  that names a different version than the one that would be built, or a version
  that is still a `.dev` one. The smoke tests check it again from the other end,
  against the version the built artifact reports at runtime.

  phabfive tagged `v0.10.0-rc.1` over a `pyproject.toml` that still read
  `0.10.0-dev.0`, and published a release candidate whose wheel, sdist and six
  executables were all named for the dev version. Nothing in its pipeline
  noticed, because every artifact is named after `pyproject.toml` while the
  release is named after the tag.


# 0.2.0 (2026-05-05)

## New Features

* **JSON data source** - Load data from JSON files with `--data config.json`
* **TOML data source** - Load data from TOML files with `--data config.toml`
* **Environment variable support** - Load environment variables with `--env PREFIX_` CLI option
* **Pluggable data source architecture** - New programmatic API with `YamlDataSource`, `JsonDataSource`, `TomlDataSource`, `EnvDataSource`, `KeyvalDataSource`, `StdinDataSource`, and `ContextBuilder`

## Other Notes

* Refactored internal data loading to use DataSource protocol pattern
* All data sources support deep merge when combined


# 0.1.1 (2026-03-30)

## Bug Fixes

* Fix Rich stripping bracket content from template output
* Fix Windows CI failures from unclosed file handles

## Other Notes

* Added `exclude-newer` to `[tool.uv]` for supply chain protection


# 0.1.0 (2026-03-09)

## Prelude

Initial release of weav - a Jinja2 template compiler CLI. Renders templates with data from YAML files, supporting multiple data sources with deep merge, key-value parameters, and flexible template search paths.

## New Features

* **Template rendering** - Render Jinja2 templates with data from YAML files
* **Multiple data sources** - Load and deep-merge data from multiple YAML files
* **Key wrapping** - Wrap data under a key with `KEY=FILE` syntax (e.g., `--data tasks=data.yaml`)
* **Stdin support** - Read data from stdin with `-` or `KEY=-` syntax
* **Key-value parameters** - Override template variables with `--keyval KEY=VALUE`
* **Template search paths** - Automatic template discovery in package, local, user data, and user documents directories
* **Shell completion** - Tab completion for template names
* **Standalone executables** - Pre-built binaries for Linux, macOS, and Windows (AMD64 and ARM64)
* **Sigstore signing** - Cryptographically signed release executables
