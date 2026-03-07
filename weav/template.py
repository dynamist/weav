"""Jinja2 template compilation module."""

from __future__ import annotations

import importlib.resources
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import platformdirs
from jinja2 import Environment, TemplateNotFound
from jinja2.loaders import FileSystemLoader
from ruamel.yaml import YAML

from weav.utils import deep_merge, load_and_wrap, mangle_keyval

if TYPE_CHECKING:
    from typing import TextIO


class TemplateError(Exception):
    """Error raised when template operations fail."""


def get_template_paths() -> list[Path]:
    """Return list of paths to search for templates.

    Search order:
    1. Package bundled templates
    2. Current working directory ./templates
    3. User data directory (~/.local/share/weav/templates)
    4. User documents directory (~/Documents/weav/templates)
    """
    return [
        Path(str(importlib.resources.files("weav") / "templates")),
        Path.cwd() / "templates",
        platformdirs.user_data_path() / "weav" / "templates",
        platformdirs.user_documents_path() / "weav" / "templates",
    ]


def find_template(name: str) -> tuple[FileSystemLoader, str]:
    """Find template file in search paths.

    Args:
        name: Template name or path. Can be:
            - A simple name (searched in template paths)
            - A relative or absolute file path

    Returns:
        Tuple of (FileSystemLoader, template_name)

    Raises:
        TemplateError: If template is not found
    """
    # If it's an absolute path or relative path with path separators, treat as file path
    if "/" in name or "\\" in name or Path(name).is_absolute():
        template_path = Path(name)
        if not template_path.exists():
            raise TemplateError(f"Template file '{name}' not found")
        if not template_path.is_file():
            raise TemplateError(f"Template path '{name}' is not a file")

        # For direct file paths, create a loader for the parent directory
        loader = FileSystemLoader([template_path.parent])
        return (loader, template_path.name)

    # Otherwise, search in the standard template paths
    searching = get_template_paths()
    loader = FileSystemLoader(searching)
    try:
        # Test if template exists by trying to get it
        env = Environment(autoescape=True, loader=loader)
        env.get_template(name)
        return (loader, name)
    except TemplateNotFound as exc:
        available = loader.list_templates()
        msg = (
            f"Template '{name}' not found in search paths:\n"
            f"  Searched: {searching}\n"
            f"  Available templates: {available}"
        )
        raise TemplateError(msg) from exc


def parse_data_args(data_args: list[str]) -> list[tuple[TextIO, str | None]]:
    """Parse data arguments, handling key=file syntax.

    Args:
        data_args: List of data file specifications. Each can be:
            - A filename
            - "-" for stdin
            - "key=filename" to wrap the data under a key

    Returns:
        List of tuples (file_object, wrapper_key or None)
    """
    result: list[tuple[TextIO, str | None]] = []
    for arg in data_args:
        if "=" in arg:
            # Split on first '=' to get key=filename
            wrapper_key, filename = arg.split("=", 1)
            if filename == "-":
                result.append((sys.stdin, wrapper_key))
            else:
                result.append((Path(filename).open(), wrapper_key))
        elif arg == "-":
            result.append((sys.stdin, None))
        else:
            result.append((Path(arg).open(), None))

    return result


def compile_template(
    template_name: str,
    data_files: list[str],
    keyvals: list[str],
    *,
    verbose: bool = False,
) -> str:
    """Compile a Jinja2 template with data and return rendered output.

    Args:
        template_name: Template name or path
        data_files: List of YAML data file specifications
        keyvals: List of key=value strings
        verbose: If True, print debug info to stderr

    Returns:
        Rendered template string

    Raises:
        TemplateError: If template compilation fails
    """
    # Find and load the template
    loader, tpl_name = find_template(template_name)
    env = Environment(autoescape=True, trim_blocks=True, loader=loader)
    template = env.get_template(tpl_name)

    # Parse CLI key=val parameters (sep=None allows commas in values)
    parameters = mangle_keyval(keyvals, sep=None)

    # Load all YAML files and merge them
    yaml = YAML(typ="safe")
    merged_data: dict[str, Any] = {}
    data_specs = parse_data_args(data_files)

    for file_obj, wrapper_key in data_specs:
        loaded_file = load_and_wrap(yaml.load, file_obj, wrapper_key)
        merged_data = deep_merge(merged_data, loaded_file)
        if verbose:
            print(f"Loaded {file_obj.name} with keys: {list(loaded_file.keys())}", file=sys.stderr)

    # Merge keyval parameters into merged_data (keyval takes precedence)
    merged_data.update(parameters)

    return template.render(**merged_data)
