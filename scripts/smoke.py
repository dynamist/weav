#!/usr/bin/env python3
"""Run a built weav and prove it works, before it is signed or released.

Ported from phabfive's scripts/smoke.py, and it is here for the reason that one
is there: phabfive v0.10.0-rc.1 shipped six standalone executables that could
not start at all, and every release job reported success, because nothing in
the pipeline ever ran what it had just built.

weav's builds guess at the same kind of thing, and none of it is visible in a
test run against the source tree. The one-file executables need
`--collect-data weav` to carry SKILL.md, and `weav/__init__.py` reads its own
version out of the distribution metadata at import time. The wheel needs
hatchling to have picked SKILL.md up as package data. A check that only imports
weav proves none of that -- dropping `--collect-data weav` from the PyInstaller
line was tried, and the resulting binary passes every check here but `--skill`.

    python scripts/smoke.py --executable dist/weav-linux-amd64
    python scripts/smoke.py --venv /tmp/fresh-venv
    python scripts/smoke.py --venv .venv --expect-version 0.3.0rc1

Deliberately imports nothing outside the standard library: it has to run on a
bare CI runner, before anything has been installed for it.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# The two leaf commands. Reaching each one's help proves the command was
# registered and its module really made it into the bundle.
COMMANDS = ["render", "frontmatter"]

# --version prints "weav <version>". How much PEP 440 normalization reaches it
# depends on how weav was installed, so only require that it looks like a
# version and compare with canonical_version() rather than as strings.
VERSION_PATTERN = re.compile(r"^weav (\d+\.\d+[0-9A-Za-z.\-+]*)$")

# A frozen build that lost a module says so in a traceback and still exits
# non-zero, which a "did it fail?" check alone would accept.
IMPORT_FAILURES = [
    "ModuleNotFoundError",
    "ImportError",
    "PackageNotFoundError",
    "Traceback (most recent call last)",
]


class CheckError(Exception):
    """A check that did not hold."""


def resolve_executable(args) -> Path:
    """The weav to run: given directly, or found inside a venv."""
    if args.executable:
        given = Path(args.executable)
        if not given.is_file():
            sys.exit(f"no such executable: {args.executable}")
        return given.resolve()

    for relative in ("bin/weav", "Scripts/weav.exe", "Scripts/weav"):
        candidate = Path(args.venv).joinpath(*relative.split("/"))
        if candidate.is_file():
            return candidate.resolve()

    sys.exit(f"no weav console script in venv: {args.venv}")


def smoke_env(home: Path) -> dict:
    """An environment the machine's own files cannot leak into.

    weav has no config file, but it does search `~/.local/share/weav/templates`
    and `~/Documents/weav/templates` through platformdirs, and `--env` reads
    the whole environment. Pointing HOME at an empty directory and running from
    there means a template the developer happens to have installed cannot
    satisfy a check that the built artifact should have failed.
    """
    env = dict(os.environ)
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "NO_COLOR": "1",
            # Fixed width: rich wraps to the terminal, and a narrow CI terminal
            # would break the help strings these checks look for.
            "COLUMNS": "200",
        }
    )
    return env


def run(executable: Path, arguments: list, home: Path, timeout: int, env_extra=None):
    """Run weav once and return (returncode, stdout, stderr)."""
    env = smoke_env(home)
    if env_extra:
        env.update(env_extra)

    try:
        completed = subprocess.run(
            [str(executable), *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
            # cwd is the empty HOME, so the "./templates" search path resolves
            # inside the sandbox rather than against the checkout.
            cwd=home,
            env=env,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as expired:
        raise CheckError(
            f"timed out after {timeout}s -- it is probably waiting for input"
        ) from expired

    return completed.returncode, completed.stdout, completed.stderr


def expect_success(executable, arguments, home, timeout):
    """Run weav and require a clean exit. Returns stdout."""
    code, out, err = run(executable, arguments, home, timeout)
    if code != 0:
        raise CheckError(f"exited {code}\n{indent(out + err)}")
    for marker in IMPORT_FAILURES:
        if marker in err:
            raise CheckError(f"exited 0 but broke on an import\n{indent(err)}")
    return out


def indent(text: str) -> str:
    lines = text.strip().splitlines() or ["(no output)"]
    return "\n".join(f"    | {line}" for line in lines[:20])


def write(home: Path, name: str, text: str) -> Path:
    """Drop a fixture file into the sandbox and return its path."""
    path = home.joinpath(*name.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def canonical_version(version: str) -> str:
    """Compare versions without caring which separators survived.

    "0.3.0-dev.0", "0.3.0.dev0" and "0.3.0dev0" are the same release; so are
    tag v0.3.0-rc.1 and the "0.3.0rc1" importlib.metadata reports for it.
    Dropping the separators makes all of them compare equal, which is enough to
    catch a binary built from the wrong revision.
    """
    return re.sub(r"[-._]", "", version).lower()


def check_version(executable, home, timeout, expected):
    """--version is the check a broken build fails first.

    weav/__init__.py runs importlib.metadata.version("weav") at import time, so
    a build that did not carry the distribution metadata raises
    PackageNotFoundError before typer ever parses an argument, and the binary
    cannot start at all. Reaching this output also means typer, rich and the
    whole eager import graph under weav/cli.py were bundled.
    """
    output = expect_success(executable, ["--version"], home, timeout).strip()

    match = VERSION_PATTERN.match(output)
    if not match:
        raise CheckError(f"not a version: {output!r}")
    if expected and canonical_version(match.group(1)) != canonical_version(expected):
        raise CheckError(f"reported {output!r}, expected {expected!r}")

    return output


def check_help(executable, home, timeout):
    """Root help lists both commands and ends with the agent footer."""
    output = expect_success(executable, ["--help"], home, timeout)

    for command in COMMANDS:
        if command not in output:
            raise CheckError(f"--help does not mention {command!r}")

    # Written by AgentFooterMixin.format_epilog, a click rendering path that
    # only runs when typer is not rendering help through rich.
    if "Are you an AI?" not in output:
        raise CheckError("--help is missing the agent resources footer")

    return "lists " + ", ".join(COMMANDS)


def check_command_help(executable, command, home, timeout):
    """Each leaf command's help, footer included.

    weav has no intermediate groups, so this is the page an agent lands on, and
    AgentFooterCommand is what puts the footer there.
    """
    output = expect_success(executable, [command, "--help"], home, timeout)
    if "Are you an AI?" not in output:
        raise CheckError(f"{command} --help is missing the agent resources footer")
    return "ok"


def check_skill(executable, home, timeout):
    """--skill reads weav/SKILL.md through importlib.resources.

    A data file, not a module: a one-file build without --collect-data weav, or
    a wheel that dropped the non-Python file, fails here and nowhere else --
    verified by building one and running this script against it. The empty
    stderr
    is part of the contract -- `weav --skill > SKILL.md` is the documented way
    to install it, so a warning on the way out would land in someone's skill.
    """
    code, out, err = run(executable, ["--skill"], home, timeout)
    if code != 0:
        raise CheckError(f"exited {code}\n{indent(out + err)}")
    if err:
        raise CheckError(f"wrote to stderr\n{indent(err)}")

    if not out.startswith("---"):
        raise CheckError(f"does not start with YAML frontmatter: {out[:60]!r}")
    if "name: weav" not in out:
        raise CheckError("frontmatter does not name the skill")

    lines = len(out.splitlines())
    if lines < 300:
        raise CheckError(f"only {lines} lines -- SKILL.md looks truncated")

    return f"{lines} lines"


def completion_var(program):
    """Name the completion variable the way typer derives it.

    typer.core builds it as

        f"_{prog_name}_COMPLETE".replace("-", "_").upper()

    which is click's pre-8.2 rule: "-" becomes "_" and a "." is left alone.
    click 8.2 started mapping dots too, so the two rules agree on every name
    without a dot and disagree on exactly one asset -- the Windows .exe. weav
    is a typer app, so typer's TyperGroup is what runs; follow typer.
    """
    return f"_{program}_COMPLETE".replace("-", "_").upper()


def program_name(executable, home, timeout):
    """Ask the binary what it calls itself, rather than guessing.

    click derives the completion variable from sys.argv[0], and the release
    renames every executable to weav-<os>-<arch> before smoke testing it. A
    hardcoded _WEAV_COMPLETE reaches none of them: the renamed binary never
    sees an instruction and falls through to an ordinary run, which for weav
    means WeavGroup dispatching to render and failing on a missing argument --
    indistinguishable from broken completion.

    Deriving the name from the file name instead would be a second guess:
    console scripts trim a ".exe" off sys.argv[0] and frozen binaries do not.
    The "Usage:" line is what click itself resolved, so it is right on every
    platform.
    """
    code, out, err = run(executable, ["--help"], home, timeout)
    match = re.search(r"^Usage:\s+(\S+)", out + err, re.MULTILINE)
    if code != 0 or not match:
        # Not fatal on its own -- check_help reports a broken --help.
        return executable.name
    return match.group(1)


def check_completion(executable, home, timeout):
    """Drive click's completion protocol the way a shell does."""
    program = program_name(executable, home, timeout)
    code, out, err = run(
        executable,
        [],
        home,
        timeout,
        env_extra={
            completion_var(program): "complete_bash",
            "COMP_WORDS": f"{program} ",
            "COMP_CWORD": "1",
        },
    )

    if code != 0:
        raise CheckError(f"completion exited {code}\n{indent(out + err)}")

    offered = out.split()
    for command in COMMANDS:
        if command not in offered:
            raise CheckError(f"completion did not offer {command!r}: {offered[:12]}")

    return f"offers {len(offered)} candidates"


def check_render_search_path(executable, home, timeout):
    """Render by bare name, which is what walks the template search path.

    find_template() only consults get_template_paths() for a name with no path
    separator in it, and that function builds its first entry from
    importlib.resources.files("weav") and the rest from platformdirs. A frozen
    build that cannot resolve either raises before Jinja2 is reached, so this
    is the check that covers both.

    The data source is YAML, which is ruamel.yaml, and the template does a
    for-loop and a filter, which is Jinja2 doing real work rather than echoing.
    """
    write(
        home,
        "templates/greeting.j2",
        "{{ greeting | upper }}, {{ name }}!\n{% for item in items %}- {{ item }}\n{% endfor %}",
    )
    write(
        home,
        "data.yaml",
        "greeting: hello\nname: placeholder\nitems:\n  - one\n  - two\n",
    )

    output = expect_success(
        executable,
        ["render", "greeting.j2", "--data", "data.yaml", "--keyval", "name=world"],
        home,
        timeout,
    )

    # Compared without the trailing newlines: the template ends in one and the
    # CLI adds another, and neither is what this check is about.
    expected = "HELLO, world!\n- one\n- two"
    if output.rstrip("\n") != expected:
        raise CheckError(f"rendered {output!r}, expected {expected!r}")

    return "search path, YAML and --keyval"


def check_render_json(executable, home, timeout):
    """Render a template given as a path, with a JSON source.

    The suffix is what picks the parser, so this is the only check that reaches
    JsonDataSource. Autoescaping is on for an .html.j2 template, and the value
    is chosen to prove it: a build that lost the _autoescape wiring would emit
    the raw ampersand.
    """
    write(home, "pages/page.html.j2", "<p>{{ title }}</p>")
    write(home, "page.json", '{"title": "Ben & Jerry"}')

    output = expect_success(
        executable,
        ["render", "./pages/page.html.j2", "--data", "page.json"],
        home,
        timeout,
    )

    if "Ben &amp; Jerry" not in output:
        raise CheckError(f"not autoescaped: {output!r}")

    return "JSON source, autoescaped"


def check_frontmatter(executable, home, timeout):
    """Edit a document in place and read the result back.

    The only check that reaches frontmatter.py, and so the only one that runs
    ruamel.yaml in round-trip mode and the temp-file-and-replace write. The
    comment and the single quotes are there because preserving them is the
    whole point of round-trip mode.
    """
    path = write(
        home,
        "doc.md",
        "---\n# keep me\ntitle: 'Kept'\ndraft: true\n---\n\nBody stays put.\n",
    )

    expect_success(
        executable,
        ["frontmatter", "doc.md", "--upsert", "origin=abc123", "--delete", "draft"],
        home,
        timeout,
    )

    result = path.read_text(encoding="utf-8")

    for expected in ["# keep me", "title: 'Kept'", "origin: abc123", "Body stays put."]:
        if expected not in result:
            raise CheckError(f"lost {expected!r} from the document\n{indent(result)}")
    if "draft" in result:
        raise CheckError(f"--delete left the key behind\n{indent(result)}")

    return "round trip preserved"


def check_missing_template(executable, home, timeout):
    """A template that is not there must fail cleanly, not on an import.

    The error path formats the search paths it looked in, so it reaches
    get_template_paths() and the rich error console. Failing is the expected
    outcome; what is being checked is that it fails as weav rather than as a
    traceback.
    """
    code, out, err = run(executable, ["render", "nope.j2"], home, timeout)

    for marker in IMPORT_FAILURES:
        if marker in out + err:
            raise CheckError(f"broke on an import, not on the lookup\n{indent(out + err)}")
    if code == 0:
        raise CheckError("rendered a template that does not exist")
    if "not found" not in err:
        raise CheckError(f"no clean error on stderr\n{indent(out + err)}")

    return "clean error"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--executable", help="path to a weav executable")
    target.add_argument("--venv", help="path to a venv holding a weav console script")
    parser.add_argument("--expect-version", help="exact PEP 440 version --version must report")
    parser.add_argument("--timeout", type=int, default=120, help="seconds per check (default: 120)")
    args = parser.parse_args()

    executable = resolve_executable(args)
    print(f"smoke testing {executable}\n")

    def bind(function, *extra):
        return lambda home: function(executable, *extra, home, args.timeout)

    checks = [
        (
            "--version",
            lambda home: check_version(executable, home, args.timeout, args.expect_version),
        ),
        ("--help", bind(check_help)),
    ]
    checks += [(f"{command} --help", bind(check_command_help, command)) for command in COMMANDS]
    checks += [
        ("--skill", bind(check_skill)),
        ("shell completion", bind(check_completion)),
        ("render by name", bind(check_render_search_path)),
        ("render by path", bind(check_render_json)),
        ("frontmatter edit", bind(check_frontmatter)),
        ("missing template", bind(check_missing_template)),
    ]

    failures = []

    # A fresh HOME per check, so nothing one command writes can change what the
    # next one sees.
    for name, check in checks:
        with tempfile.TemporaryDirectory(prefix="weav-smoke-") as home:
            try:
                print(f"  ok   {name}: {check(Path(home))}")
            except CheckError as failure:
                print(f"  FAIL {name}: {failure}")
                failures.append(name)

    print()
    if failures:
        print(f"{len(failures)} of {len(checks)} checks failed: {', '.join(failures)}")
        return 1

    print(f"all {len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
