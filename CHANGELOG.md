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
