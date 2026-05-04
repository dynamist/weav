"""Tests for the CLI application."""

from typer.testing import CliRunner
from weav import __version__
from weav.cli import app

runner = CliRunner()


def test_version_command():
    """Test the --version flag."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_render_with_keyval(tmp_path):
    """Test the render command with keyval."""
    template = tmp_path / "test.j2"
    template.write_text("Hello {{ name }}!")
    result = runner.invoke(app, [str(template), "--keyval", "name=World"])
    assert result.exit_code == 0
    assert "Hello World!" in result.stdout


def test_render_with_yaml_data(tmp_path):
    """Test the render command with YAML data file."""
    template = tmp_path / "test.j2"
    template.write_text("Items: {% for item in items %}{{ item }} {% endfor %}")
    data_file = tmp_path / "data.yaml"
    data_file.write_text("items:\n  - apple\n  - banana\n")
    result = runner.invoke(app, [str(template), "--data", str(data_file)])
    assert result.exit_code == 0
    assert "apple" in result.stdout
    assert "banana" in result.stdout


def test_render_template_not_found():
    """Test the render command with non-existent template."""
    result = runner.invoke(app, ["nonexistent.j2"])
    assert result.exit_code == 1
    assert "Error" in result.stdout or "Error" in result.stderr


def test_render_data_file_not_found(tmp_path):
    """Test the render command with non-existent data file."""
    template = tmp_path / "test.j2"
    template.write_text("Hello {{ name }}!")
    result = runner.invoke(app, [str(template), "--data", "nonexistent.yaml"])
    assert result.exit_code == 1


def test_render_with_env_prefix(tmp_path, monkeypatch):
    """Test the render command with environment variable prefix."""
    monkeypatch.setenv("MYAPP_NAME", "EnvWorld")
    monkeypatch.setenv("MYAPP_COUNT", "42")
    template = tmp_path / "test.j2"
    template.write_text("Hello {{ name }}! Count: {{ count }}")
    result = runner.invoke(app, [str(template), "--env", "MYAPP_"])
    assert result.exit_code == 0
    assert "Hello EnvWorld!" in result.stdout
    assert "Count: 42" in result.stdout


def test_render_env_overrides_data(tmp_path, monkeypatch):
    """Test that env vars override data file values."""
    monkeypatch.setenv("MYAPP_NAME", "FromEnv")
    template = tmp_path / "test.j2"
    template.write_text("Hello {{ name }}!")
    data_file = tmp_path / "data.yaml"
    data_file.write_text("name: FromYaml\n")
    result = runner.invoke(app, [str(template), "--data", str(data_file), "--env", "MYAPP_"])
    assert result.exit_code == 0
    assert "Hello FromEnv!" in result.stdout
