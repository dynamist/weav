"""Shared fixtures for the test suite."""

import shlex
import sys
from pathlib import Path

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


@pytest.fixture
def doc(tmp_path):
    """Return a helper that writes document bytes to a temp file."""

    def _write(data: bytes, name: str = "doc.md") -> Path:
        path = tmp_path / name
        path.write_bytes(data)
        return path

    return _write
