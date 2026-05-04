"""Jinja2 template compilation module."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import platformdirs
from jinja2 import Environment, TemplateNotFound
from jinja2.loaders import FileSystemLoader

from weav.datasources import ContextBuilder, build_sources_from_args


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


def compile_template(
    template_name: str,
    data_files: list[str],
    keyvals: list[str],
    *,
    env_prefixes: list[str] | None = None,
    verbose: bool = False,
) -> str:
    """Compile a Jinja2 template with data and return rendered output.

    Args:
        template_name: Template name or path
        data_files: List of YAML data file specifications
        keyvals: List of key=value strings
        env_prefixes: List of environment variable prefixes to load
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

    # Build data sources from CLI arguments and merge them
    sources = build_sources_from_args(data_files, keyvals, env_prefixes)
    context = ContextBuilder(sources).build(verbose=verbose)

    return template.render(**context)
