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

## Usage

Basic usage with key-value parameters:

```bash
weav template.j2 --keyval name=World
```

Using a YAML data file:

```bash
weav template.j2 --data config.yaml
```

Using a JSON data file:

```bash
weav template.j2 --data config.json
```

Using a TOML data file:

```bash
weav template.j2 --data config.toml
```

Mixing YAML, JSON, and TOML data files:

```bash
weav template.j2 --data base.yaml --data override.json --data final.toml
```

Multiple data files with key wrapping:

```bash
weav report.j2 --data items=tasks.yaml --data config.yaml
```

`KEY=FILE` always namespaces the file's data under `KEY` — whether it is a
mapping, list, or scalar — so the template accesses it as `{{ items }}`.
Without a key, mappings merge at the top level of the context and
lists/scalars are wrapped under `data`.

Reading data from stdin:

```bash
cat data.yaml | weav template.j2 --data -
```

### Running commands as data sources

`--exec` runs a command and uses its standard output as data. This is the way
to combine several query results in one template:

```bash
weav report.j2 \
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
weav report.j2 --data tasks=<(phabfive --format=yaml maniphest search | head -50)
```

Note that quoting is consumed twice: once by your shell, once by weav. A
command containing quotes needs them escaped or nested.

### Choosing a format explicitly

Data files pick a parser from their suffix, which does not work for stdin,
extensionless files, or `--exec` commands. Prefix any spec with `:FORMAT` to be
explicit:

```bash
weav template.j2 --data config:yaml=/dev/fd/63   # extensionless path
weav template.j2 --data :json=-                  # stdin as JSON
weav template.j2 --exec items:json='some-query'  # command output as JSON
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
weav template.j2 --env MYAPP_
# Variables are available as lowercase keys: {{ name }}, {{ debug }}

# Combine with data files (env vars override file values)
weav template.j2 --data config.yaml --env MYAPP_
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

| Option | Description |
|--------|-------------|
| `-d, --data` | YAML/JSON/TOML data file(s). Use `KEY=FILE` to wrap under key, `KEY:FORMAT=FILE` to force a format. Use `-` for stdin. |
| `-x, --exec` | Run a command and use its stdout as data. Same `KEY[:FORMAT]=` syntax. Runs without a shell. Can specify multiple times. |
| `-e, --env` | Environment variable prefix (e.g., `MYAPP_`). Can specify multiple times. |
| `-k, --keyval` | Key-value pairs (`KEY=VAL`). Can specify multiple times. |
| `-v, --verbose` | Show verbose output (loaded files, etc.) |
| `-V, --version` | Show version and exit |

## Programmatic API

weav provides a pluggable data source architecture for programmatic use:

```python
from pathlib import Path
from weav.datasources import (
    YamlDataSource,
    JsonDataSource,
    TomlDataSource,
    EnvDataSource,
    ExecDataSource,
    KeyvalDataSource,
    ContextBuilder,
)
from weav.template import compile_template

# Build context from multiple sources
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

## License

Apache License 2.0 - Copyright 2026 Dynamist AB
