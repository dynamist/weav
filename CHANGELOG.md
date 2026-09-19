# Unreleased

## New Features

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
