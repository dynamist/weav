"""Tests for the CLI application."""

import shlex
import sys

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


def test_render_with_toml_data(tmp_path):
    """Test the render command with TOML data file."""
    template = tmp_path / "test.j2"
    template.write_text("Hello {{ name }}! Count: {{ count }}")
    data_file = tmp_path / "data.toml"
    data_file.write_text('name = "World"\ncount = 42\n')
    result = runner.invoke(app, [str(template), "--data", str(data_file)])
    assert result.exit_code == 0
    assert "Hello World!" in result.stdout
    assert "Count: 42" in result.stdout


def test_render_with_nested_toml(tmp_path):
    """Test the render command with nested TOML data."""
    template = tmp_path / "test.j2"
    template.write_text("Host: {{ config.host }}, Port: {{ config.port }}")
    data_file = tmp_path / "data.toml"
    data_file.write_text('[config]\nhost = "localhost"\nport = 8080\n')
    result = runner.invoke(app, [str(template), "--data", str(data_file)])
    assert result.exit_code == 0
    assert "Host: localhost" in result.stdout
    assert "Port: 8080" in result.stdout


def py(code):
    """Build a command string that runs Python code, for --exec tests."""
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"


def test_render_with_two_data_files(tmp_path):
    """Two --data flags are both namespaced and available to the template."""
    template = tmp_path / "test.j2"
    template.write_text("{{ tasks.0.id }} {{ repos.name }}")
    tasks = tmp_path / "tasks.yaml"
    tasks.write_text("- id: T1\n")
    repos = tmp_path / "repos.yaml"
    repos.write_text("name: weav\n")
    result = runner.invoke(
        app,
        [str(template), "--data", f"tasks={tasks}", "--data", f"repos={repos}"],
    )
    assert result.exit_code == 0
    assert "T1 weav" in result.stdout


def test_render_with_two_exec_commands(tmp_path):
    """Two --exec flags feed two query results into one template."""
    template = tmp_path / "test.j2"
    template.write_text("{{ tasks.0.id }} {{ pastes.0.Name }}")
    result = runner.invoke(
        app,
        [
            str(template),
            "--exec",
            "tasks:yaml=" + py("print('- id: T1')"),
            "--exec",
            "pastes:json=" + py('print(\'[{"Name": "notes"}]\')'),
        ],
    )
    assert result.exit_code == 0
    assert "T1 notes" in result.stdout


def test_exec_failure_exits_nonzero(tmp_path):
    """A failing --exec command aborts rendering with exit code 1."""
    template = tmp_path / "test.j2"
    template.write_text("{{ tasks }}")
    result = runner.invoke(app, [str(template), "--exec", "tasks=" + py("raise SystemExit(2)")])
    assert result.exit_code == 1
    assert "exit code 2" in result.output


def test_exec_unknown_format_exits_nonzero(tmp_path):
    """An unknown format in a spec is reported as an error."""
    template = tmp_path / "test.j2"
    template.write_text("{{ tasks }}")
    result = runner.invoke(app, [str(template), "--exec", "tasks:xml=" + py("pass")])
    assert result.exit_code == 1
    assert "Unknown format" in result.output


def test_verbose_reports_exec_source(tmp_path):
    """--verbose names each loaded source, including exec commands."""
    template = tmp_path / "test.j2"
    template.write_text("{{ tasks.0.id }}")
    command = py("print('- id: T1')")
    result = runner.invoke(app, [str(template), "--verbose", "--exec", f"tasks={command}"])
    assert result.exit_code == 0
    assert f"Loaded exec:{command} with keys: ['tasks']" in result.output
