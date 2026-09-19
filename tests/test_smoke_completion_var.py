"""scripts/smoke.py names the completion variable the way typer does.

The release renames each PyInstaller artifact to weav-<os>-<arch> before smoke
testing it, and typer derives the completion environment variable from whatever
the binary is called. Getting that name wrong does not look like a broken test:
the binary never sees a completion instruction and falls through to an ordinary
run, which for weav means WeavGroup dispatching the empty argument list to
render and failing on the missing template -- indistinguishable from completion
itself being broken.

That failure mode is only reachable from a release. phabfive, where this is
ported from, spent two release candidates finding it. These tests move it into
the normal suite.

The rule lives in typer.core:

    complete_var = f"_{prog_name}_COMPLETE".replace("-", "_").upper()

which is click's pre-8.2 rule: "-" becomes "_" and a "." is left alone. click
8.2 started mapping dots too, and following click instead of typer is what broke
phabfive's Windows executables -- the .exe suffix is the only dot among the
release assets.
"""

import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from smoke import completion_var


# Every asset name release.yml builds, plus the plain console script.
@pytest.mark.parametrize(
    ("program", "expected"),
    [
        ("weav", "_WEAV_COMPLETE"),
        ("weav-linux-amd64", "_WEAV_LINUX_AMD64_COMPLETE"),
        ("weav-linux-arm64", "_WEAV_LINUX_ARM64_COMPLETE"),
        ("weav-macos-amd64", "_WEAV_MACOS_AMD64_COMPLETE"),
        ("weav-macos-arm64", "_WEAV_MACOS_ARM64_COMPLETE"),
        # The dot survives. Mapping it to "_" is click's rule, not typer's.
        ("weav-windows-amd64.exe", "_WEAV_WINDOWS_AMD64.EXE_COMPLETE"),
        ("weav-windows-arm64.exe", "_WEAV_WINDOWS_ARM64.EXE_COMPLETE"),
    ],
)
def test_completion_var_matches_typer(program, expected):
    assert completion_var(program) == expected


# What completion_var() is a transcription of, read back out of typer itself.
TYPER_RULE = 'f"_{prog_name}_COMPLETE".replace("-", "_").upper()'


def test_completion_var_agrees_with_typer_source():
    """Check the rule against the installed typer rather than only restating it.

    A typer release that changes how the variable is spelled should fail here,
    where the message says so, rather than in a release job where it shows up as
    completion looking broken on one platform. Compared as source text rather
    than executed -- running typer's expression would mean evaluating a string
    at test time, which the python-no-eval pre-commit hook forbids, and the
    parametrised cases above already cover what it produces.
    """
    import typer.core

    source = pathlib.Path(typer.core.__file__).read_text()
    match = re.search(r"complete_var = (.+)", source)
    assert match, "could not find typer's complete_var derivation"

    assert match.group(1).strip() == TYPER_RULE, (
        f"typer now spells it {match.group(1).strip()}; "
        f"scripts/smoke.py still implements {TYPER_RULE}"
    )
