"""Jinja2 template compilation module."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import platformdirs
from jinja2 import Environment, TemplateNotFound, TemplateSyntaxError
from jinja2 import TemplateError as Jinja2TemplateError
from jinja2.loaders import FileSystemLoader

from weav.datasources import ContextBuilder, build_sources_from_args

# This module's full public surface. The package's own __all__ in
# weav/__init__.py is the narrower, curated promise; anything listed here
# but not there is public but reached one import deeper.
__all__ = [
    "TemplateError",
    "compile_template",
    "find_template",
    "get_template_paths",
]


class TemplateError(Exception):
    """Error raised when template operations fail."""


def _autoescape(template_name: str | None) -> bool:
    """Autoescape only HTML/XML templates; a trailing .j2 is ignored.

    Text formats (Markdown, plain text, config files) must render
    substitutions verbatim -- HTML entities like &#34; would corrupt them.
    """
    if template_name is None:
        return False
    name = template_name.removesuffix(".j2")
    return name.endswith((".html", ".htm", ".xml"))


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
        # Only look the template up; compiling it here would raise jinja2's
        # own exceptions from a lookup, and compile_template() compiles anyway.
        # get_source() requires an environment but FileSystemLoader ignores it
        loader.get_source(Environment(autoescape=True), name)
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
    exec_commands: list[str] | None = None,
    verbose: bool = False,
) -> str:
    """Compile a Jinja2 template with data and return rendered output.

    Args:
        template_name: Template name or path
        data_files: List of YAML data file specifications
        keyvals: List of key=value strings
        env_prefixes: List of environment variable prefixes to load
        exec_commands: List of command specifications to run for data
        verbose: If True, print debug info to stderr

    Returns:
        Rendered template string

    Raises:
        TemplateError: If the template is not found, or jinja2 fails to
            compile or render it (a syntax error, an unknown filter, an
            undefined variable, a missing include). The jinja2 exception is
            chained as ``__cause__``. Exceptions raised by the template's own
            expressions, such as ``ZeroDivisionError``, are not wrapped.
        DataSourceError: If a data source fails to produce data
    """
    # Find and load the template
    loader, tpl_name = find_template(template_name)
    # S701: _autoescape enables escaping for HTML/XML templates; unlike
    # select_autoescape it also recognizes them behind a .j2 suffix
    env = Environment(autoescape=_autoescape, trim_blocks=True, loader=loader)  # noqa: S701
    try:
        template = env.get_template(tpl_name)
    except Jinja2TemplateError as exc:
        raise _wrap(tpl_name, exc) from exc

    # Build data sources from CLI arguments and merge them; kept outside the
    # render guard so a data source's own error is not relabelled
    sources = build_sources_from_args(data_files, keyvals, env_prefixes, exec_commands)
    context = ContextBuilder(sources).build(verbose=verbose)

    try:
        return template.render(**context)
    except Jinja2TemplateError as exc:
        raise _wrap(tpl_name, exc) from exc


def _wrap(tpl_name: str, exc: Jinja2TemplateError) -> TemplateError:
    """Describe a jinja2 failure as a weav TemplateError.

    Only a syntax error carries its location as attributes; a render-time
    error's line lives in jinja2's rewritten traceback, which is not API.
    """
    if isinstance(exc, TemplateSyntaxError):
        where = exc.name or tpl_name
        return TemplateError(f"Template '{where}', line {exc.lineno}: {exc.message}")
    if isinstance(exc, TemplateNotFound):
        return TemplateError(f"Template '{tpl_name}' references '{exc.name}', which was not found")
    return TemplateError(f"Template '{tpl_name}': {exc.message or exc}")
