"""Weav CLI - Jinja2 template compiler."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, Any

os.environ["TYPER_USE_RICH"] = "0"

import typer
from rich.console import Console
from typer.core import TyperGroup

from weav import __version__
from weav.datasources import DataSourceError
from weav.frontmatter import FrontmatterDocument, FrontmatterError
from weav.template import TemplateError, compile_template
from weav.utils import mangle_commas, mangle_keyval

console = Console()
err_console = Console(stderr=True)


class WeavGroup(TyperGroup):
    """Dispatch an unrecognised first argument to `render`.

    Compatibility shim for the pre-subcommand `weav TEMPLATE ...` form.
    Remove at 1.0, together with this class and the `cls=` argument below.
    """

    # ctx and the returned command are Click objects, but typer vendors its own
    # copy of Click from 0.27 onwards, so the concrete classes differ by version
    # and cannot be named portably here.
    def resolve_command(
        self,
        ctx: Any,  # noqa: ANN401 -- see above
        args: list[str],
    ) -> tuple[str | None, Any, list[str]]:
        """Fall back to `render` when args[0] is not a command or an option."""
        name = args[0] if args else None
        # Options are left to Click so an unknown flag still reports
        # "No such option" rather than "template not found". The test is a
        # leading "-" specifically: Click also treats "/" as an option prefix,
        # which would misread an absolute template path as a flag.
        if name is not None and name not in self.commands and not name.startswith("-"):
            if not ctx.resilient_parsing:
                err_console.print(
                    f"Warning: '{name}' is not a weav command; treating it as a "
                    f"template. Use 'weav render {name}'. This fallback will be "
                    "removed in weav 1.0.",
                    style="yellow",
                    highlight=False,
                )
            # Return the full args: args[0] is the template, not a command name.
            return "render", self.get_command(ctx, "render"), args
        return super().resolve_command(ctx, args)


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


def render(
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
            help="Data file (YAML/JSON/TOML). Use KEY=FILE to wrap under key, "
            "KEY:FORMAT=FILE to force a format. '-' for stdin.",
        ),
    ] = [],  # noqa: B006
    exec_: Annotated[
        list[str],
        typer.Option(
            "--exec",
            "-x",
            help="Run COMMAND and use its stdout as data. Use KEY=COMMAND to wrap "
            "under key, KEY:FORMAT=COMMAND to force yaml/json/toml. Runs without "
            "a shell. Can specify multiple times.",
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
) -> None:
    """Render a Jinja2 template with data from YAML, JSON, or TOML files.

    Examples:

        weav render template.j2 --keyval name=World

        weav render template.j2 --data config.yaml

        weav render template.j2 --data config.toml

        weav render report.j2 --data items=tasks.yaml --data config.json

        cat data.yaml | weav render template.j2 --data -

        weav render template.j2 --env MYAPP_

        weav render report.j2 --exec tasks:yaml='phabfive --format=yaml maniphest search'
    """
    try:
        result = compile_template(
            template,
            data,
            keyval,
            env_prefixes=env or None,
            exec_commands=exec_ or None,
            verbose=verbose,
        )
        console.print(result, highlight=False, soft_wrap=True, markup=False)
    except (TemplateError, DataSourceError) as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    except FileNotFoundError as e:
        err_console.print(f"[red]Error:[/red] File not found: {e.filename}")
        raise typer.Exit(1) from e


def frontmatter(
    file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Markdown or reST file to edit.",
        ),
    ],
    upsert: Annotated[
        list[str],
        typer.Option(
            "--upsert",
            "-u",
            help="Insert or update KEY=VAL. Comma-separated pairs allowed. "
            "Can specify multiple times.",
        ),
    ] = [],  # noqa: B006
    delete: Annotated[
        list[str],
        typer.Option(
            "--delete",
            "-D",
            help="Delete KEY. Comma-separated keys allowed. Can specify multiple times.",
        ),
    ] = [],  # noqa: B006
    to_stdout: Annotated[
        bool,
        typer.Option(
            "--stdout",
            help="Write the result to stdout instead of editing FILE in place.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Report inserted, updated and deleted keys on stderr.",
        ),
    ] = False,
) -> None:
    """Edit the YAML frontmatter of a Markdown or reST document.

    The file is edited in place. Its BOM and line endings are preserved, and a
    document whose content is unchanged is not rewritten.

    Examples:

        weav frontmatter doc.md --upsert origin=$(git rev-parse HEAD)

        weav frontmatter doc.md --delete status,docid

        weav frontmatter doc.md --upsert lorem=ipsum --stdout
    """
    try:
        document = FrontmatterDocument.from_file(file)
    except FrontmatterError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    result = document.patch(
        upsert=mangle_keyval(upsert),
        delete=mangle_commas(delete),
    )

    if to_stdout:
        _echo_document(document, result, verbose=verbose)
    else:
        document.write(file)

    if verbose:
        _report(result)


def _echo_document(
    document: FrontmatterDocument,
    result: dict[str, list[str]],
    *,
    verbose: bool,
) -> None:
    """Print the document, colouring changed keys when verbose."""
    if not verbose:
        # Bypass rich so redirected output is byte-identical to an in-place write.
        sys.stdout.write(document.dumps())
        return

    for line in document.dump_frontmatter().splitlines():
        key = line.split(":", 1)[0]
        style = None
        if key in result["inserted"]:
            style = "green"
        elif key in result["updated"]:
            style = "yellow"
        console.print(line, style=style, markup=False, highlight=False, soft_wrap=True)
    sys.stdout.write(document.dump_content())


def _report(result: dict[str, list[str]]) -> None:
    """Summarise what changed on stderr."""
    for key, values in result.items():
        if not values:
            continue
        # A key that was deleted after being inserted or updated is only deleted.
        if key != "deleted" and set(values) & set(result["deleted"]):
            continue
        err_console.print(
            f"{key}: {','.join(values)}",
            style="red",
            markup=False,
            highlight=False,
        )


app = typer.Typer(cls=WeavGroup, no_args_is_help=True)


@app.callback()
def cli(
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
    """Compile Jinja2 templates and edit YAML frontmatter."""


app.command("render")(render)
app.command("frontmatter")(frontmatter)


if __name__ == "__main__":
    app()
