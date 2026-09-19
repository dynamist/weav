"""`weav --skill` prints the agent skill file and exits.

An AI agent that meets weav for the first time reads --help, so --help points it
here. The flag has to be eager: a bare `weav` answers with help on stderr and
exit 2, which would otherwise win.

The skill is shipped as package data, and the wheel is not the only artifact --
the release also builds one-file PyInstaller executables, which collect data
files only when asked. test_skill_is_package_data guards that path from the
resource side, independently of the CLI.
"""

import re
import shlex
import subprocess
import sys
from importlib import resources

import pytest
from typer.main import get_command
from typer.testing import CliRunner
from weav.cli import app

runner = CliRunner()

_ENTRYPOINT = "import sys; sys.argv = ['weav', *sys.argv[1:]]; from weav.cli import app; app()"

# A fenced block introduced by ```bash
_BASH_BLOCK = re.compile(r"^```bash$(.*?)^```$", re.MULTILINE | re.DOTALL)


def _skill_text():
    return resources.files("weav").joinpath("SKILL.md").read_text(encoding="utf-8")


def test_skill_is_package_data():
    """Readable as a resource, so a frozen build can find it too."""
    assert _skill_text().startswith("---\n")


def test_prints_the_skill():
    result = runner.invoke(app, ["--skill"])

    assert result.exit_code == 0
    assert result.stdout.startswith("---\n")
    assert "name: weav" in result.stdout


def test_output_is_the_file_verbatim():
    """The output is meant to be redirected straight into a SKILL.md."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _ENTRYPOINT, "--skill"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == _skill_text()
    assert result.stderr == ""


def test_beats_the_bare_invocation_help():
    """Without is_eager the root callback would answer with help and exit 2."""
    result = runner.invoke(app, ["--skill"])

    assert result.exit_code == 0
    assert "Commands" not in result.stdout


def test_help_offers_the_flag():
    result = runner.invoke(app, ["--help"])

    assert "--skill" in result.stdout


def _documented_invocations():
    """Every `weav ...` invocation the skill tells an agent to run.

    Deliberately conservative: a line with a command substitution is skipped,
    only the segment after the last pipe is read, and the command path stops at
    the first word that is an option or a value rather than a subcommand.
    """
    for block in _BASH_BLOCK.findall(_skill_text()):
        for raw in block.splitlines():
            line = raw.split("|")[-1].strip()
            if not line.startswith("weav ") or "$(" in line:
                continue
            try:
                words = shlex.split(line)
            except ValueError:  # pragma: no cover - an unbalanced quote
                continue
            path = []
            for word in words[1:]:
                if word.startswith("-") or "." in word or "=" in word:
                    break
                path.append(word)
            options = [w.split("=", 1)[0] for w in words[1:] if w.startswith("-") and w != "-"]
            yield line, tuple(path), tuple(options)


_INVOCATIONS = sorted(set(_documented_invocations()))


def test_the_skill_documents_commands():
    """Guard the guard: a broken extractor would make the next tests vacuous."""
    assert len(_INVOCATIONS) > 10
    assert any(path == ("render",) for _, path, _ in _INVOCATIONS)
    assert any(path == ("frontmatter",) for _, path, _ in _INVOCATIONS)


@pytest.mark.parametrize(
    "line,path,options",
    _INVOCATIONS,
    ids=[line for line, _, _ in _INVOCATIONS],
)
def test_documented_invocation_resolves(line, path, options):
    """The skill goes stale silently; this is what notices."""
    command = get_command(app)
    ctx = command.make_context("weav", [], resilient_parsing=True)

    for name in path:
        child = command.get_command(ctx, name)
        assert child is not None, f"{line!r}: no such command {name}"
        command = child
        ctx = command.make_context(name, [], parent=ctx, resilient_parsing=True)

    # click adds --help at invocation time rather than in params
    known = set(ctx.help_option_names)
    known |= {opt for param in command.params for opt in (*param.opts, *param.secondary_opts)}
    for option in options:
        assert option in known, f"{line!r}: {option} is not an option of {path or ('weav',)}"
