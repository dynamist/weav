"""Shared fixtures for the test suite."""

import shlex
import sys

import pytest


def _py_command(code, *args):
    """Build a command string that runs Python code, for exec tests.

    Quoting with shlex.quote is the exact inverse of the shlex.split that
    ExecDataSource applies, so code containing spaces, quotes or shell
    metacharacters survives the round trip as a single argv element. No
    shell is involved at either end.
    """
    parts = [sys.executable, "-c", code, *args]
    return " ".join(shlex.quote(part) for part in parts)


@pytest.fixture
def py():
    """Return a helper that builds a `python -c ...` command string."""
    return _py_command
