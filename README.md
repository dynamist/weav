# weav

A markup template compiler with data support.

**Note:** The `weav` package on PyPI is unrelated to this project.

## Features

- Render Jinja2 templates with data from YAML, JSON, or TOML files
- Support for multiple data files with deep merge
- Key-value parameters via command line
- Environment variable support (programmatic API)
- Flexible template search paths
- Read data from stdin
- Run commands and use their output as data (`--exec`)
- Explicit per-source format override (`KEY:FORMAT=SOURCE`)
- Edit YAML frontmatter in Markdown and reST documents (`weav frontmatter`)
- Agent skill for AI coding agents (`weav --skill`)

## Installation

### Using uv

```bash
uv tool install git+https://github.com/dynamist/weav.git
```

### From source

```bash
git clone https://github.com/dynamist/weav.git
cd weav
uv sync
```

## Commands

weav has two commands:

| Command | Description |
|---------|-------------|
| `weav render TEMPLATE` | Render a Jinja2 template with data from files, commands or the environment. |
| `weav frontmatter FILE` | Edit the YAML frontmatter of a Markdown or reST document. |

> **Deprecated:** the bare `weav TEMPLATE ...` form still works and is treated as
> `weav render TEMPLATE ...`, but it prints a warning to stderr and will be
> removed in weav 1.0. A template whose name collides with a command needs the
> explicit form -- use `weav render render` or `weav render ./render`.

## Usage

Basic usage with key-value parameters:

```bash
weav render template.j2 --keyval name=World
```

Using a YAML data file:

```bash
weav render template.j2 --data config.yaml
```

Using a JSON data file:

```bash
weav render template.j2 --data config.json
```

Using a TOML data file:

```bash
weav render template.j2 --data config.toml
```

Mixing YAML, JSON, and TOML data files:

```bash
weav render template.j2 --data base.yaml --data override.json --data final.toml
```

Multiple data files with key wrapping:

```bash
weav render report.j2 --data items=tasks.yaml --data config.yaml
```

`KEY=FILE` always namespaces the file's data under `KEY` — whether it is a
mapping, list, or scalar — so the template accesses it as `{{ items }}`.
Without a key, mappings merge at the top level of the context and
lists/scalars are wrapped under `data`.

Reading data from stdin:

```bash
cat data.yaml | weav render template.j2 --data -
```

### Running commands as data sources

`--exec` runs a command and uses its standard output as data. This is the way
to combine several query results in one template:

```bash
weav render report.j2 \
  --exec tasks:yaml='phabfive --format=yaml maniphest search --limit 10' \
  --exec pastes:json='phabfive --format=json paste search --limit 10'
```

Each command's stdout is parsed and namespaced under its key, so the template
sees `{{ tasks }}` and `{{ pastes }}`. If a command exits non-zero, weav
reports the failure and exits 1 rather than rendering an incomplete document.
The command's own stderr is passed through untouched.

Commands run **without a shell**, so pipes, redirects and globs are not
interpreted — the command string is split into arguments the way a shell would
split it, then executed directly. When you need a pipeline, use process
substitution with `--data` instead:

```bash
weav render report.j2 --data tasks=<(phabfive --format=yaml maniphest search | head -50)
```

Note that quoting is consumed twice: once by your shell, once by weav. A
command containing quotes needs them escaped or nested.

### Choosing a format explicitly

Data files pick a parser from their suffix, which does not work for stdin,
extensionless files, or `--exec` commands. Prefix any spec with `:FORMAT` to be
explicit:

```bash
weav render template.j2 --data config:yaml=/dev/fd/63   # extensionless path
weav render template.j2 --data :json=-                  # stdin as JSON
weav render template.j2 --exec items:json='some-query'  # command output as JSON
```

The full spec grammar for `--data` and `--exec` is `[KEY][:FORMAT]=SOURCE`,
where FORMAT is `yaml`, `json` or `toml`. A `KEY=` prefix is only recognised
when KEY looks like a name, so paths and commands containing `=` (such as
`phabfive --format=yaml ...`) are left intact.

Using environment variables:

```bash
# Load all MYAPP_* environment variables
export MYAPP_NAME=World
export MYAPP_DEBUG=true
weav render template.j2 --env MYAPP_
# Variables are available as lowercase keys: {{ name }}, {{ debug }}

# Combine with data files (env vars override file values)
weav render template.j2 --data config.yaml --env MYAPP_
```

### Precedence

Sources are merged in a fixed order, with later sources overriding earlier ones:

1. `--data` files, in command-line order
2. `--exec` commands, in command-line order
3. `--env` prefixes
4. `--keyval` pairs

## Template Search Paths

Templates are searched in the following order:

1. Package bundled templates
2. `./templates` in current directory
3. `~/.local/share/weav/templates` (user data directory)
4. `~/Documents/weav/templates` (user documents)

You can also specify a direct file path to a template.

## Options

### render

| Option | Description |
|--------|-------------|
| `-d, --data` | YAML/JSON/TOML data file(s). Use `KEY=FILE` to wrap under key, `KEY:FORMAT=FILE` to force a format. Use `-` for stdin. |
| `-x, --exec` | Run a command and use its stdout as data. Same `KEY[:FORMAT]=` syntax. Runs without a shell. Can specify multiple times. |
| `-e, --env` | Environment variable prefix (e.g., `MYAPP_`). Can specify multiple times. |
| `-k, --keyval` | Key-value pairs (`KEY=VAL`). Can specify multiple times. |
| `-v, --verbose` | Show verbose output (loaded files, etc.) |

`-V, --version` is a global option: use `weav --version`.

### frontmatter

| Option | Description |
|--------|-------------|
| `-u, --upsert` | Insert or update `KEY=VAL`. Comma-separated pairs allowed. Can specify multiple times. |
| `-D, --delete` | Delete `KEY`. Comma-separated keys allowed. Can specify multiple times. |
| `--stdout` | Write the result to stdout instead of editing the file in place. |
| `-v, --verbose` | Report inserted, updated and deleted keys on stderr. |

## Agent skill

`weav --skill` prints a skill file describing the CLI for AI coding agents. It
goes to stdout verbatim, with nothing on stderr, so it can be redirected
straight into place:

```bash
mkdir -p ~/.claude/skills/weav
weav --skill > ~/.claude/skills/weav/SKILL.md
```

Every help page ends with a short resources block pointing at the flag, so an
agent that only reads `--help` still finds it.

## Editing frontmatter

`weav frontmatter` adds, changes and removes keys in a document's YAML
frontmatter block, preserving comments, quoting, block scalars, the document's
own indentation and its long values, which are never re-wrapped.

```bash
# Stamp a document with the commit it was derived from
weav frontmatter contract.md --upsert origin=$(git rev-parse HEAD)

# Remove several keys at once
weav frontmatter doc.md --delete status,docid

# Preview without touching the file
weav frontmatter doc.md --upsert lorem=ipsum --stdout
```

**The file is edited in place by default.** Pass `--stdout` to print the
result and leave the file untouched.

A frontmatter block is recognised only when the document opens with a `---`
line, and the next `---` or `...` line closes it. A `---` used as a thematic
break in the body is left alone, as is an indented `  ---` or a longer `----`,
and a document with no frontmatter simply gains a block.

The opening delimiter is required, which means a Markdown setext heading is
never mistaken for metadata -- `Overview: the big picture` underlined by `---`
stays a heading. It also means a document whose frontmatter is closed by `---`
but never opened by one is treated as body content; add a leading `---` to such
documents. Documents are read and written as UTF-8, and a byte order mark, CRLF
line endings and the exact delimiter lines all survive a round trip. A document
whose content did not change is not rewritten at all.

## Programmatic API

weav is a library as well as a command. The supported names are exported from
the top level:

```python
from weav import FrontmatterDocument, compile_template
```

Every public name is resolved lazily, so `import weav` pulls in no third-party
module and costs about a millisecond -- a consumer who only wants
`FrontmatterDocument` never imports Jinja2. The module holding a name is
imported the first time the name is touched.

### What weav exports

| | |
|---|---|
| Documents | `FrontmatterDocument` |
| Templates | `compile_template`, `find_template`, `get_template_paths` |
| Data sources | `ContextBuilder`, `DataSource`, `YamlDataSource`, `JsonDataSource`, `TomlDataSource`, `StdinDataSource`, `ExecDataSource`, `KeyvalDataSource`, `EnvDataSource` |
| Errors | `FrontmatterError`, `TemplateError`, `DataSourceError` |
| Utilities | `deep_merge` |

Everything else stays in its own module -- `weav.datasources.parse_data_spec`,
`weav.utils.mangle_keyval`, `weav.frontmatter.detect_indent` -- because their
contracts are the CLI's argument grammar or the YAML emitter's internals rather
than a library API. Submodule imports keep working and are not deprecated;
`from weav.frontmatter import FrontmatterDocument` is as supported as the short
form.

### Editing frontmatter programmatically

```python
from pathlib import Path
from weav import FrontmatterDocument

doc = FrontmatterDocument.from_file(Path("contract.md"))
doc.patch(upsert={"origin": "deadbeef"}, delete=["draft"])
doc.write(Path("contract.md"))
```

`patch()` reports what it did, as `{"inserted": [...], "updated": [...],
"deleted": [...]}`, and `write()` returns `False` without touching the file
when the bytes would not change. A document already in memory goes through the
constructor instead of `from_file()`:

```python
doc = FrontmatterDocument(text)
doc.patch(upsert={"origin": "deadbeef"})
print(doc.frontmatter["origin"], doc.content, doc.dumps())
```

The constructor decodes exactly as `from_file()` does: a leading byte order
mark is recorded and stripped, and CRLF or lone-CR endings are folded, so the
same bytes give the same document whichever way they arrive. `dumps()` returns
the document with `\n` endings and no BOM; `write()` is what restores the
original endings and the mark.

`doc.frontmatter` is a `ruamel.yaml` `CommentedMap`, which is a `dict` that
also remembers comments and quoting. Values are mostly what you would expect --
unquoted scalars come back as plain `str` and `int`, and quoted ones as
`str` subclasses that compare and serialise normally. The exception worth
knowing is that an unquoted ISO date becomes a `datetime.date`, so
`json.dumps(dict(doc.frontmatter))` raises `TypeError` on a document with one;
quote the value or convert it before serialising.

### Building a context

```python
from pathlib import Path
from weav import (
    ContextBuilder,
    EnvDataSource,
    ExecDataSource,
    JsonDataSource,
    KeyvalDataSource,
    TomlDataSource,
    YamlDataSource,
    compile_template,
)

builder = ContextBuilder()
builder.add(YamlDataSource(Path("base.yaml")))
builder.add(JsonDataSource(Path("override.json")))
builder.add(TomlDataSource(Path("settings.toml")))
builder.add(ExecDataSource("phabfive --format=yaml paste search", "pastes"))
builder.add(EnvDataSource(prefix="MYAPP_"))  # Read MYAPP_* env vars
builder.add(KeyvalDataSource(["debug=true"]))

context = builder.build()

# Or use the high-level API
result = compile_template(
    "template.j2",
    data_files=["config.yaml", "data.json", "settings.toml"],
    keyvals=["name=World"],
    exec_commands=["pastes:yaml=phabfive --format=yaml paste search"],
)
```

`compile_template()` takes the same specification strings the CLI accepts,
rather than structured arguments.

### Available Data Sources

| Class | Description |
|-------|-------------|
| `YamlDataSource` | Load data from YAML files |
| `JsonDataSource` | Load data from JSON files |
| `TomlDataSource` | Load data from TOML files |
| `EnvDataSource` | Load data from environment variables |
| `KeyvalDataSource` | Load data from key=value strings |
| `StdinDataSource` | Load data from standard input |
| `ExecDataSource` | Run a command and load data from its stdout |
| `DataSource` | The protocol the others satisfy |

`DataSource` is a typing `Protocol` and is not `runtime_checkable`: implement
it structurally -- a `name` property and a `load()` returning a dict -- rather
than inheriting from it, and do not use it with `isinstance()`.

### Errors

```python
from weav import DataSourceError, FrontmatterError, TemplateError
```

`FrontmatterError` is raised only when a document that opens with `---` has a
block that will not parse. A document with no frontmatter is not an error.

### Installing weav as a dependency

weav is published to GitHub Releases, not to PyPI, and **the `weav` package on
PyPI is an unrelated project**. Depend on it by direct reference:

```
weav @ git+https://github.com/dynamist/weav.git@v0.3.0
```

`uv pip compile` ignores `[tool.uv.sources]`, so a project that pins weav
there also needs the direct reference in its requirements input, plus a
`weav>=0.3.0` floor. Without both, the resolve can silently pick up the
unrelated PyPI package instead.


## License

Apache License 2.0 - Copyright 2026 Dynamist AB
