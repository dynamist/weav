"""Weav CLI - Jinja2 template compiler."""

from __future__ import annotations

import os
from typing import Annotated

os.environ["TYPER_USE_RICH"] = "0"

import typer
from rich.console import Console

from weav import __version__
from weav.template import TemplateError, compile_template

console = Console()
err_console = Console(stderr=True)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"weav {__version__}")
        raise typer.Exit()


def complete_template(incomplete: str) -> list[str]:
    """Return template names for shell completion."""
    from weav.template import get_template_paths

    templates = []
    for path in get_template_paths():
        if path.exists() and path.is_dir():
            for file in path.iterdir():
                if file.is_file() and file.name.startswith(incomplete):
                    templates.append(file.name)
    return templates


def main(
    template: Annotated[
        str,
        typer.Argument(
            help="Template file name or path.",
            autocompletion=complete_template,
        ),
    ],
    data: Annotated[
        list[str],
        typer.Option(
            "--data",
            "-d",
            help="YAML data file(s). Use KEY=FILE to wrap under key. Use '-' for stdin.",
        ),
    ] = [],  # noqa: B006
    keyval: Annotated[
        list[str],
        typer.Option(
            "--keyval",
            "-k",
            help="Key-value pairs (KEY=VAL). Can specify multiple times.",
        ),
    ] = [],  # noqa: B006
    env: Annotated[
        list[str],
        typer.Option(
            "--env",
            "-e",
            help="Environment variable prefix (e.g., MYAPP_). Can specify multiple times.",
        ),
    ] = [],  # noqa: B006
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show verbose output (loaded files, etc.)",
        ),
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Render a Jinja2 template with YAML data.

    Examples:

        weav template.j2 --keyval name=World

        weav template.j2 --data config.yaml

        weav report.j2 --data items=tasks.yaml --data config.yaml

        cat data.yaml | weav template.j2 --data -

        weav template.j2 --env MYAPP_
    """
    try:
        result = compile_template(template, data, keyval, env_prefixes=env or None, verbose=verbose)
        console.print(result, highlight=False, soft_wrap=True, markup=False)
    except TemplateError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    except FileNotFoundError as e:
        err_console.print(f"[red]Error:[/red] File not found: {e.filename}")
        raise typer.Exit(1) from e


app = typer.Typer()
app.command()(main)


if __name__ == "__main__":
    app()
