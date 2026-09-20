"""weav - a markup template compiler with data support.

weav is a CLI first, but everything under it is usable as a library:

    from weav import FrontmatterDocument, compile_template

Every public name is resolved lazily (PEP 562), so `import weav` pulls in no
third-party module and costs about a millisecond. The module that defines a
name is imported the first time the name is touched. See AGENTS.md for why
this must stay lazy -- it is not an optimisation that can be simplified away.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Declared for type checkers only; resolved at runtime by __getattr__.
    # Every name here must also appear in _LAZY and in __all__: mypy's
    # no_implicit_reexport (implied by strict) refuses to re-export a name
    # that is missing from __all__, and a name missing from _LAZY type checks
    # perfectly while raising AttributeError at runtime.
    # tests/test_public_api.py asserts all three agree.
    __version__: str

    from weav.datasources import (
        ContextBuilder,
        DataSource,
        DataSourceError,
        EnvDataSource,
        ExecDataSource,
        JsonDataSource,
        KeyvalDataSource,
        StdinDataSource,
        TomlDataSource,
        YamlDataSource,
    )
    from weav.frontmatter import FrontmatterDocument, FrontmatterError
    from weav.template import (
        TemplateError,
        compile_template,
        find_template,
        get_template_paths,
    )
    from weav.utils import deep_merge

# The promise. Spelled out as literals rather than derived from _LAZY: ruff
# cannot see a computed __all__, and would flag every import above as unused.
__all__ = [
    "ContextBuilder",
    "DataSource",
    "DataSourceError",
    "EnvDataSource",
    "ExecDataSource",
    "FrontmatterDocument",
    "FrontmatterError",
    "JsonDataSource",
    "KeyvalDataSource",
    "StdinDataSource",
    "TemplateError",
    "TomlDataSource",
    "YamlDataSource",
    "__version__",
    "compile_template",
    "deep_merge",
    "find_template",
    "get_template_paths",
]

# Public name -> the module that defines it, and the single source of truth
# for what __getattr__ will resolve.
_LAZY = {
    "ContextBuilder": "weav.datasources",
    "DataSource": "weav.datasources",
    "DataSourceError": "weav.datasources",
    "EnvDataSource": "weav.datasources",
    "ExecDataSource": "weav.datasources",
    "FrontmatterDocument": "weav.frontmatter",
    "FrontmatterError": "weav.frontmatter",
    "JsonDataSource": "weav.datasources",
    "KeyvalDataSource": "weav.datasources",
    "StdinDataSource": "weav.datasources",
    "TemplateError": "weav.template",
    "TomlDataSource": "weav.datasources",
    "YamlDataSource": "weav.datasources",
    "compile_template": "weav.template",
    "deep_merge": "weav.utils",
    "find_template": "weav.template",
    "get_template_paths": "weav.template",
}

# Resolved as attributes so `import weav; weav.frontmatter.FrontmatterDocument`
# works. Without this it depends on whether something else already imported the
# submodule, which is worse than either answer consistently.
#
# cli and agents are deliberately absent: weav/cli.py sets
# os.environ["TYPER_USE_RICH"] = "0" as it imports, and a library must never
# cause a process-global side effect just because an attribute was touched.
_SUBMODULES = ("datasources", "frontmatter", "template", "utils")


def _read_version() -> str:
    """Return the installed distribution's version, read on first access.

    Deferred rather than read at import: importlib.metadata parses the
    installed distributions' metadata, which is most of what importing weav
    used to cost and all of it for a consumer who only wants
    FrontmatterDocument.

    A source tree that was never installed has no metadata at all, so this
    falls back instead of raising -- a library that cannot be imported from a
    checkout is a library nobody can vendor. scripts/smoke.py rejects the
    fallback string, so a release artifact that lost its metadata still fails.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("weav")
    except PackageNotFoundError:
        return "0.0.0+unknown"


def __getattr__(name: str) -> object:
    """Resolve a public name on first access, then cache it (PEP 562).

    Annotated `-> object` rather than `Any` on purpose: `Any` would make a
    consumer's typo silently well-typed, while `object` fails at the point of
    use. The names in the TYPE_CHECKING block keep their real types either way.
    """
    if name in _SUBMODULES:
        return import_module(f"weav.{name}")
    if name == "__version__":
        value: object = _read_version()
    else:
        module = _LAZY.get(name)
        if module is None:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        value = getattr(import_module(module), name)
    # Bound in the module namespace, so __getattr__ runs once per name.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Offer the curated surface to dir() and REPL completion."""
    return sorted({*__all__, *_SUBMODULES})
