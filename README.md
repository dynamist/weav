# weav

A markup template compiler with data support.

**Note:** The `weav` package on PyPI is unrelated to this project.

## Features

- Render Jinja2 templates with data from YAML files
- Support for multiple data files with deep merge
- Key-value parameters via command line
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

Multiple data files with key wrapping:

```bash
weav report.j2 --data items=tasks.yaml --data config.yaml
```

Reading data from stdin:

```bash
cat data.yaml | weav template.j2 --data -
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
| `-d, --data` | YAML data file(s). Use `KEY=FILE` to wrap under key. Use `-` for stdin. |
| `-k, --keyval` | Key-value pairs (`KEY=VAL`). Can specify multiple times. |
| `-v, --verbose` | Show verbose output (loaded files, etc.) |
| `-V, --version` | Show version and exit |

## License

Apache License 2.0 - Copyright 2026 Dynamist AB
