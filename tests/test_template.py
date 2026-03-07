"""Tests for the template module."""

import tempfile
from pathlib import Path

import pytest
from weav.template import TemplateError, compile_template, find_template


def test_find_template_direct_path():
    """Test finding template by direct file path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as f:
        f.write("Hello {{ name }}")
        f.flush()
        _loader, name = find_template(f.name)
        Path(f.name).unlink()

    assert name == Path(f.name).name


def test_find_template_not_found():
    """Test that TemplateError is raised for non-existent template."""
    with pytest.raises(TemplateError, match="not found"):
        find_template("nonexistent_template.j2")


def test_compile_template_basic():
    """Test basic template compilation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as f:
        f.write("Hello {{ name }}!")
        f.flush()
        result = compile_template(f.name, [], ["name=World"])
        Path(f.name).unlink()

    assert result == "Hello World!"


def test_compile_template_with_yaml():
    """Test template compilation with YAML data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as template_file:
        template_file.write("{{ greeting }}, {{ name }}!")
        template_file.flush()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as data_file:
            data_file.write("greeting: Hello\nname: World\n")
            data_file.flush()

            result = compile_template(template_file.name, [data_file.name], [])
            Path(data_file.name).unlink()
        Path(template_file.name).unlink()

    assert result == "Hello, World!"


def test_compile_template_keyval_overrides_yaml():
    """Test that keyval overrides YAML data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as template_file:
        template_file.write("{{ name }}")
        template_file.flush()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as data_file:
            data_file.write("name: FromYAML\n")
            data_file.flush()

            result = compile_template(template_file.name, [data_file.name], ["name=FromKeyval"])
            Path(data_file.name).unlink()
        Path(template_file.name).unlink()

    assert result == "FromKeyval"


def test_compile_template_wrapped_list():
    """Test template compilation with wrapped list data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as template_file:
        template_file.write("{% for item in items %}{{ item }} {% endfor %}")
        template_file.flush()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as data_file:
            data_file.write("- apple\n- banana\n- cherry\n")
            data_file.flush()

            result = compile_template(template_file.name, [f"items={data_file.name}"], [])
            Path(data_file.name).unlink()
        Path(template_file.name).unlink()

    assert "apple" in result
    assert "banana" in result
    assert "cherry" in result
