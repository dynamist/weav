"""Tests for the template module."""

import pytest
from weav.template import TemplateError, compile_template, find_template


def test_find_template_direct_path(tmp_path):
    """Test finding template by direct file path."""
    template = tmp_path / "test.j2"
    template.write_text("Hello {{ name }}")
    _loader, name = find_template(str(template))
    assert name == template.name


def test_find_template_not_found():
    """Test that TemplateError is raised for non-existent template."""
    with pytest.raises(TemplateError, match="not found"):
        find_template("nonexistent_template.j2")


def test_compile_template_basic(tmp_path):
    """Test basic template compilation."""
    template = tmp_path / "test.j2"
    template.write_text("Hello {{ name }}!")
    result = compile_template(str(template), [], ["name=World"])
    assert result == "Hello World!"


def test_compile_template_with_yaml(tmp_path):
    """Test template compilation with YAML data."""
    template = tmp_path / "test.j2"
    template.write_text("{{ greeting }}, {{ name }}!")
    data_file = tmp_path / "data.yaml"
    data_file.write_text("greeting: Hello\nname: World\n")
    result = compile_template(str(template), [str(data_file)], [])
    assert result == "Hello, World!"


def test_compile_template_keyval_overrides_yaml(tmp_path):
    """Test that keyval overrides YAML data."""
    template = tmp_path / "test.j2"
    template.write_text("{{ name }}")
    data_file = tmp_path / "data.yaml"
    data_file.write_text("name: FromYAML\n")
    result = compile_template(str(template), [str(data_file)], ["name=FromKeyval"])
    assert result == "FromKeyval"


def test_compile_template_wrapped_list(tmp_path):
    """Test template compilation with wrapped list data."""
    template = tmp_path / "test.j2"
    template.write_text("{% for item in items %}{{ item }} {% endfor %}")
    data_file = tmp_path / "data.yaml"
    data_file.write_text("- apple\n- banana\n- cherry\n")
    result = compile_template(str(template), [f"items={data_file}"], [])
    assert "apple" in result
    assert "banana" in result
    assert "cherry" in result
