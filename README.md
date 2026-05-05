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

Reading data from stdin:

```bash
cat data.yaml | weav template.j2 --data -
```

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
| `-d, --data` | YAML/JSON/TOML data file(s). Use `KEY=FILE` to wrap under key. Use `-` for stdin. |
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
    KeyvalDataSource,
    ContextBuilder,
)
from weav.template import compile_template

# Build context from multiple sources
builder = ContextBuilder()
builder.add(YamlDataSource(Path("base.yaml")))
builder.add(JsonDataSource(Path("override.json")))
builder.add(TomlDataSource(Path("settings.toml")))
builder.add(EnvDataSource(prefix="MYAPP_"))  # Read MYAPP_* env vars
builder.add(KeyvalDataSource(["debug=true"]))

context = builder.build()

# Or use the high-level API
result = compile_template(
    "template.j2",
    data_files=["config.yaml", "data.json", "settings.toml"],
    keyvals=["name=World"],
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

## License

Apache License 2.0 - Copyright 2026 Dynamist AB
