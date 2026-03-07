"""Tests for the CLI application."""

import tempfile
from pathlib import Path

from typer.testing import CliRunner
from weav import __version__
from weav.cli import app

runner = CliRunner()


def test_version_command():
    """Test the --version flag."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_render_with_keyval():
    """Test the render command with keyval."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as f:
        f.write("Hello {{ name }}!")
        f.flush()
        result = runner.invoke(app, [f.name, "--keyval", "name=World"])
        Path(f.name).unlink()

    assert result.exit_code == 0
    assert "Hello World!" in result.stdout


def test_render_with_yaml_data():
    """Test the render command with YAML data file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as template_file:
        template_file.write("Items: {% for item in items %}{{ item }} {% endfor %}")
        template_file.flush()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as data_file:
            data_file.write("items:\n  - apple\n  - banana\n")
            data_file.flush()

            result = runner.invoke(app, [template_file.name, "--data", data_file.name])
            Path(data_file.name).unlink()
        Path(template_file.name).unlink()

    assert result.exit_code == 0
    assert "apple" in result.stdout
    assert "banana" in result.stdout


def test_render_template_not_found():
    """Test the render command with non-existent template."""
    result = runner.invoke(app, ["nonexistent.j2"])
    assert result.exit_code == 1
    assert "Error" in result.stdout or "Error" in result.stderr


def test_render_data_file_not_found():
    """Test the render command with non-existent data file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as f:
        f.write("Hello {{ name }}!")
        f.flush()
        result = runner.invoke(app, [f.name, "--data", "nonexistent.yaml"])
        Path(f.name).unlink()

    assert result.exit_code == 1
