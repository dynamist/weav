"""Every help page ends with the agent resources block.

The block is what tells an AI agent that `weav --skill` exists, so it has to
survive on the help paths an agent actually hits. weav has no intermediate
command groups, so unlike phabfive the leaves carry it too: `weav render --help`
is where an agent looking for a command lands.

The indentation is the fragile part: click's default format_epilog runs the
epilog through write_text, which rewraps it and flattens the two-level indent.
AgentFooterMixin writes the lines itself.

Run out of process because weav/cli.py sets TYPER_USE_RICH=0 as it imports, and
that only takes effect if nothing imported typer first. Under CliRunner
typer.testing has already imported typer with rich enabled, and typer then
renders help through rich, which never calls format_epilog. Only the real
entrypoint has the import order the installed console script has.
"""

import subprocess
import sys

import pytest
from weav.agents import AGENT_HELP_FOOTER

_ENTRYPOINT = "import sys; sys.argv = ['weav', *sys.argv[1:]]; from weav.cli import app; app()"

# The line whose leading spaces click's rewrapping would eat
_INDENTED_LINE = "    SKIP if a weav skill is already in your context."

HELP_PAGES = [
    [],
    ["render"],
    ["frontmatter"],
]


def _run(*args):
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _ENTRYPOINT, *args],
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


@pytest.mark.parametrize("args", HELP_PAGES, ids=lambda a: " ".join(a) or "(root)")
class TestHelp:
    def test_has_the_footer(self, args):
        assert "Are you an AI?" in _run(*args, "--help")

    def test_mentions_the_skill_flag(self, args):
        assert "weav --skill" in _run(*args, "--help")

    def test_indentation_survives(self, args):
        """click's write_text would rewrap this into the preceding line."""
        assert _INDENTED_LINE in _run(*args, "--help")


def test_bare_invocation_carries_the_footer():
    """A bare `weav` prints help to stderr; the pointer has to be there too."""
    assert "Are you an AI?" in _run()


def test_footer_names_the_template_search_paths():
    for path in ("./templates", "~/.local/share/weav/templates", "~/Documents/weav/templates"):
        assert path in AGENT_HELP_FOOTER


def test_footer_names_the_merge_order():
    assert "--data, --exec, --env, --keyval" in AGENT_HELP_FOOTER
