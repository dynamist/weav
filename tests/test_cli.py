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


def test_render_with_two_exec_commands(py, tmp_path):
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


def test_exec_failure_exits_nonzero(py, tmp_path):
    """A failing --exec command aborts rendering with exit code 1."""
    template = tmp_path / "test.j2"
    template.write_text("{{ tasks }}")
    result = runner.invoke(app, [str(template), "--exec", "tasks=" + py("raise SystemExit(2)")])
    assert result.exit_code == 1
    assert "exit code 2" in result.output


def test_exec_unknown_format_exits_nonzero(py, tmp_path):
    """An unknown format in a spec is reported as an error."""
    template = tmp_path / "test.j2"
    template.write_text("{{ tasks }}")
    result = runner.invoke(app, [str(template), "--exec", "tasks:xml=" + py("pass")])
    assert result.exit_code == 1
    assert "Unknown format" in result.output


def test_verbose_reports_exec_source(py, tmp_path):
    """--verbose names each loaded source, including exec commands."""
    template = tmp_path / "test.j2"
    template.write_text("{{ tasks.0.id }}")
    command = py("print('- id: T1')")
    result = runner.invoke(app, [str(template), "--verbose", "--exec", f"tasks={command}"])
    assert result.exit_code == 0
    assert f"Loaded exec:{command} with keys: ['tasks']" in result.output


WITH_MARKER = b"---\nstatus: Rolling\ndocid: DYN-1\n---\n# Manifesto\n"
HR_IN_BODY = b"# Release notes\n\nIntro.\n\n---\n\nAppendix.\n"


def test_frontmatter_edits_in_place_by_default(doc):
    """Without --stdout the file is rewritten and nothing is printed."""
    path = doc(WITH_MARKER)
    result = runner.invoke(app, ["frontmatter", str(path), "--upsert", "origin=abc"])
    assert result.exit_code == 0
    assert result.stdout == ""
    assert b"origin: abc" in path.read_bytes()


def test_frontmatter_stdout_leaves_the_file_alone(doc):
    """--stdout prints the document and must not touch the file."""
    path = doc(WITH_MARKER)
    result = runner.invoke(app, ["frontmatter", str(path), "--upsert", "origin=abc", "--stdout"])
    assert result.exit_code == 0
    assert "origin: abc" in result.stdout
    assert path.read_bytes() == WITH_MARKER


def test_frontmatter_no_op_leaves_bytes_identical(doc):
    """Neither --upsert nor --delete must still round trip exactly."""
    path = doc(WITH_MARKER)
    result = runner.invoke(app, ["frontmatter", str(path)])
    assert result.exit_code == 0
    assert path.read_bytes() == WITH_MARKER


def test_frontmatter_delete(doc):
    """--delete removes keys, accepting a comma-separated list."""
    path = doc(WITH_MARKER)
    result = runner.invoke(app, ["frontmatter", str(path), "--delete", "docid,status"])
    assert result.exit_code == 0
    text = path.read_text()
    assert "docid:" not in text
    assert "status:" not in text


def test_frontmatter_verbose_reports_on_stderr(doc):
    """The change summary belongs on stderr, not stdout."""
    path = doc(WITH_MARKER)
    result = runner.invoke(
        app,
        ["frontmatter", str(path), "--upsert", "origin=abc", "--delete", "docid", "-v"],
    )
    assert result.exit_code == 0
    assert "inserted: origin" in result.stderr
    assert "deleted: docid" in result.stderr
    assert "inserted:" not in result.stdout


def test_frontmatter_preserves_body_thematic_break(doc):
    """The regression case: an upsert must not eat the document."""
    path = doc(HR_IN_BODY)
    result = runner.invoke(app, ["frontmatter", str(path), "--upsert", "origin=abc"])
    assert result.exit_code == 0

    text = path.read_text()
    assert "origin: abc" in text
    assert "# Release notes" in text
    assert "Appendix." in text


def test_frontmatter_missing_file_exits_two(tmp_path):
    """A non-existent file is a usage error."""
    result = runner.invoke(app, ["frontmatter", str(tmp_path / "nope.md")])
    assert result.exit_code == 2


def test_frontmatter_malformed_exits_one(doc):
    """A declared but invalid block exits 1 and leaves the file alone."""
    raw = b"---\ndocid: DYN-1\nmalformed\n---\n# Manifesto\n"
    path = doc(raw)
    result = runner.invoke(app, ["frontmatter", str(path), "--upsert", "a=b"])
    assert result.exit_code == 1
    assert path.read_bytes() == raw


def test_bare_template_form_still_works(tmp_path):
    """The deprecated `weav TEMPLATE` form renders, warning on stderr only."""
    template = tmp_path / "test.j2"
    template.write_text("Hello {{ name }}!")
    result = runner.invoke(app, [str(template), "--keyval", "name=World"])
    assert result.exit_code == 0
    assert "Hello World!" in result.stdout
    assert "will be removed in weav 1.0" in result.stderr
    assert "Warning" not in result.stdout


def test_shim_passes_the_template_argument_through(tmp_path):
    """The fallback must not swallow args[0]."""
    template = tmp_path / "test.j2"
    template.write_text("{{ a }}-{{ b }}")
    result = runner.invoke(app, [str(template), "-k", "a=1", "-k", "b=2"])
    assert result.exit_code == 0
    assert "1-2" in result.stdout


def test_shim_does_not_swallow_subcommands():
    """`weav frontmatter` with no file is a usage error, not a template miss."""
    result = runner.invoke(app, ["frontmatter"])
    assert result.exit_code == 2
    assert "Missing argument" in result.stderr


def test_unknown_option_still_reports_no_such_option():
    """An unknown flag must not be treated as a template name."""
    result = runner.invoke(app, ["--bogus"])
    assert result.exit_code == 2
    assert "No such option" in result.stderr


def test_template_named_like_a_subcommand_needs_the_explicit_form(tmp_path):
    """A template named `render` is reachable via `weav render <path>`."""
    template = tmp_path / "render"
    template.write_text("Hi {{ n }}!")
    result = runner.invoke(app, ["render", str(template), "-k", "n=X"])
    assert result.exit_code == 0
    assert "Hi X!" in result.stdout


def test_explicit_render_subcommand(tmp_path):
    """The new explicit form renders without any warning."""
    template = tmp_path / "test.j2"
    template.write_text("Hello {{ name }}!")
    result = runner.invoke(app, ["render", str(template), "--keyval", "name=World"])
    assert result.exit_code == 0
    assert "Hello World!" in result.stdout
    assert result.stderr == ""


def test_help_lists_both_commands():
    """Group help must advertise render and frontmatter."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "render" in result.stdout
    assert "frontmatter" in result.stdout
