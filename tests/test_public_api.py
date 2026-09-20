"""The top-level namespace is a promise, and it is resolved lazily.

`weav/__init__.py` re-exports its public surface through a PEP 562
`__getattr__` rather than importing the modules eagerly, for two reasons that
no other test in this suite can observe:

* `import weav` must not drag in jinja2, ruamel or platformdirs. A consumer of
  FrontmatterDocument alone should not pay for the template engine.
* `weav/cli.py` sets `os.environ["TYPER_USE_RICH"] = "0"` as it imports. That
  is a process-global side effect, and merely touching an attribute on `weav`
  must never cause it.

Both are properties of a *fresh* interpreter. By the time any in-process
assertion runs, the rest of this suite has already imported everything, so the
laziness checks shell out.

The other half of the file guards a failure mypy structurally cannot see: the
TYPE_CHECKING block, `__all__` and `_LAZY` are three separate lists of the same
names, and a name present in the first two but missing from the third type
checks perfectly while raising AttributeError at runtime.
"""

import ast
import importlib
import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

import pytest
import weav

# Nothing here may be in sys.modules after a bare `import weav`.
BANNED = [
    "jinja2",  # only weav.template needs it
    "ruamel.yaml",  # only weav.frontmatter and weav.datasources
    "platformdirs",  # only weav.template, for the search paths
    "typer",  # CLI only
    "rich",  # CLI only
    "click",  # CLI only, and not always installed (see AGENTS.md)
    "importlib.metadata",  # __version__ is lazy too; it is 65ms of the import
    "weav.cli",
    "weav.agents",
    "weav.datasources",
    "weav.frontmatter",
    "weav.template",
    "weav.utils",
]

_PUBLIC = sorted(set(weav.__all__) - {"__version__"})


def _run(code):
    """Run `code` in a fresh interpreter, with TYPER_USE_RICH unset.

    Stripping the variable is what makes the side-effect assertion mean
    something: if the parent environment already set it, importing weav.cli
    would be undetectable.
    """
    env = {k: v for k, v in os.environ.items() if k != "TYPER_USE_RICH"}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


class TestResolution:
    @pytest.mark.parametrize("name", _PUBLIC)
    def test_name_resolves_to_its_modules_object(self, name):
        """Identity, not equality: a future wrapper or copy must fail here."""
        module = importlib.import_module(weav._LAZY[name])
        assert getattr(weav, name) is getattr(module, name)

    @pytest.mark.parametrize("name", _PUBLIC)
    def test_name_is_public_in_its_own_module(self, name):
        """A top-level export must still be public where it is defined."""
        module = importlib.import_module(weav._LAZY[name])
        assert name in module.__all__

    @pytest.mark.parametrize("name", weav._SUBMODULES)
    def test_submodule_resolves(self, name):
        assert getattr(weav, name) is importlib.import_module(f"weav.{name}")

    def test_repeated_access_is_the_same_object(self):
        """__getattr__ caches into globals(); it must not rebuild each time."""
        assert weav.FrontmatterDocument is weav.FrontmatterDocument


class TestSurfacesAgree:
    """__all__, _LAZY and the TYPE_CHECKING block are three copies of one list."""

    def test_all_matches_lazy(self):
        assert set(weav.__all__) == set(weav._LAZY) | {"__version__"}

    def test_type_checking_block_matches_lazy(self):
        """Parse the source: a name missing from _LAZY still type checks."""
        tree = ast.parse(Path(weav.__file__).read_text(encoding="utf-8"))
        imported = {}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.If) and getattr(node.test, "id", "") == "TYPE_CHECKING"):
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom):
                    for alias in child.names:
                        imported[alias.name] = child.module
        assert imported == weav._LAZY

    def test_all_is_sorted_and_unique(self):
        assert weav.__all__ == sorted(weav.__all__)
        assert len(weav.__all__) == len(set(weav.__all__))

    def test_cli_is_not_exported(self):
        """Touching an attribute must never import the typer stack."""
        assert "cli" not in weav._SUBMODULES
        assert "agents" not in weav._SUBMODULES
        assert not any(m.startswith("weav.cli") for m in weav._LAZY.values())


class TestAttributeProtocol:
    def test_unknown_attribute_raises_attribute_error(self):
        match = r"module 'weav' has no attribute 'no_such_name'"
        with pytest.raises(AttributeError, match=match):
            _ = weav.no_such_name

    def test_hasattr_is_false_for_unknown(self):
        """Proves __getattr__ raises AttributeError and not KeyError."""
        assert not hasattr(weav, "no_such_name")

    def test_dir_offers_the_surface(self):
        assert set(weav.__all__) <= set(dir(weav))
        assert set(weav._SUBMODULES) <= set(dir(weav))

    def test_dir_is_sorted(self):
        assert dir(weav) == sorted(dir(weav))


class TestVersion:
    def test_matches_the_distribution_metadata(self):
        assert weav.__version__ == importlib.metadata.version("weav")

    def test_is_a_string(self):
        assert isinstance(weav.__version__, str)

    def test_falls_back_when_metadata_is_missing(self, monkeypatch):
        """A vendored or never-installed tree must still import.

        scripts/smoke.py rejects this exact string, so a release artifact that
        lost its metadata is still caught.
        """

        def raise_not_found(_name):
            raise importlib.metadata.PackageNotFoundError(_name)

        monkeypatch.setattr(importlib.metadata, "version", raise_not_found)
        assert weav._read_version() == "0.0.0+unknown"


class TestLaziness:
    def test_bare_import_pulls_in_nothing(self):
        banned = ", ".join(repr(name) for name in BANNED)
        out = _run(
            "import sys, os, json; import weav; "
            f"print(json.dumps([n for n in [{banned}] if n in sys.modules]))"
        )
        assert out == "[]"

    def test_bare_import_has_no_cli_side_effect(self):
        out = _run("import os; import weav; print(os.environ.get('TYPER_USE_RICH'))")
        assert out == "None"

    def test_every_public_name_resolves_in_a_fresh_interpreter(self):
        """Catches a _LAZY entry naming a module or attribute that is gone."""
        out = _run("import weav; [getattr(weav, n) for n in weav.__all__]; print('ok')")
        assert out == "ok"

    def test_touching_a_template_name_imports_jinja2_but_not_typer(self):
        out = _run(
            "import sys, weav; weav.compile_template; "
            "print('jinja2' in sys.modules, 'typer' in sys.modules)"
        )
        assert out == "True False"

    def test_frontmatter_does_not_import_jinja2(self):
        """The consumer this matters most for wants frontmatter alone."""
        out = _run(
            "import sys, weav; weav.FrontmatterDocument; "
            "print('ruamel.yaml' in sys.modules, 'jinja2' in sys.modules)"
        )
        assert out == "True False"
