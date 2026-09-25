"""Tests for the template module."""

import jinja2
import pytest
from weav.template import (
    TemplateError,
    _autoescape,
    compile_template,
    find_template,
)


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


def test_find_template_does_not_compile(tmp_path, monkeypatch):
    """Search-path lookup finds a broken template rather than parsing it."""
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "broken.j2").write_text("{% for %}")
    monkeypatch.chdir(tmp_path)
    _loader, name = find_template("broken.j2")
    assert name == "broken.j2"


# Every jinja2 failure while compiling or rendering must arrive as
# weav.TemplateError -- the documented contract -- with the original as cause.
@pytest.mark.parametrize(
    ("body", "cause", "message"),
    [
        ("{% for %}", jinja2.TemplateSyntaxError, "line 1"),
        ("\n\n{{ x | nosuchfilter }}", jinja2.TemplateAssertionError, "line 3"),
        ("{{ nope.missing }}", jinja2.UndefinedError, "'nope' is undefined"),
        ("{% include 'absent.j2' %}", jinja2.TemplateNotFound, "absent.j2"),
    ],
    ids=["syntax", "assertion", "undefined", "missing-include"],
)
def test_compile_template_wraps_jinja2_errors(tmp_path, body, cause, message):
    template = tmp_path / "bad.md.j2"
    template.write_text(body)
    with pytest.raises(TemplateError, match=message) as excinfo:
        compile_template(str(template), [], [])
    assert type(excinfo.value.__cause__) is cause
    assert "bad.md.j2" in str(excinfo.value)


def test_compile_template_lets_python_errors_through(tmp_path):
    """Only jinja2's own errors are wrapped; template code raising is not."""
    template = tmp_path / "div.j2"
    template.write_text("{{ 1 / 0 }}")
    with pytest.raises(ZeroDivisionError):
        compile_template(str(template), [], [])


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


@pytest.mark.parametrize(
    ("template_name", "expected"),
    [
        ("page.html.j2", True),
        ("page.html", True),
        ("page.htm.j2", True),
        ("feed.xml.j2", True),
        ("feed.xml", True),
        ("doc.md.j2", False),
        ("notes.txt.j2", False),
        ("notes.txt", False),
        ("plain.j2", False),
        (None, False),
    ],
)
def test_autoescape_by_extension(template_name, expected):
    """Autoescape is enabled only for HTML/XML templates, .j2 suffix ignored."""
    assert _autoescape(template_name) is expected


def test_compile_template_markdown_not_html_escaped(tmp_path):
    """Non-HTML templates render substituted values verbatim."""
    template = tmp_path / "report.md.j2"
    template.write_text("# {{ title }}")
    result = compile_template(str(template), [], ['title=Say "hi" & <bye>'])
    assert result == '# Say "hi" & <bye>'
    assert "&#34;" not in result


def test_compile_template_html_still_escaped(tmp_path):
    """HTML templates keep autoescaping substituted values."""
    template = tmp_path / "page.html.j2"
    template.write_text("<h1>{{ title }}</h1>")
    result = compile_template(str(template), [], ['title=Say "hi" & <bye>'])
    assert result == "<h1>Say &#34;hi&#34; &amp; &lt;bye&gt;</h1>"


def test_compile_template_dict_data_namespaced_under_key(tmp_path):
    """A mapping data file given as KEY=FILE is namespaced under KEY."""
    template = tmp_path / "test.j2"
    template.write_text("{{ server.host }}:{{ server.port }}")
    data_file = tmp_path / "server.yaml"
    data_file.write_text("host: example.com\nport: 8080\n")
    result = compile_template(str(template), [f"server={data_file}"], [])
    assert result == "example.com:8080"


def test_compile_template_with_exec_command(py, tmp_path):
    """compile_template runs --exec commands and namespaces their output."""
    template = tmp_path / "test.j2"
    template.write_text("{{ tasks.0.id }}")
    command = py("print('- id: T1')")
    result = compile_template(str(template), [], [], exec_commands=[f"tasks={command}"])
    assert result == "T1"


def test_compile_template_exec_merges_with_data(py, tmp_path):
    """--exec data merges alongside --data under separate keys."""
    template = tmp_path / "test.j2"
    template.write_text("{{ repos.name }}/{{ tasks.0.id }}")
    data_file = tmp_path / "repos.yaml"
    data_file.write_text("name: weav\n")
    command = py("print('- id: T1')")
    result = compile_template(
        str(template), [f"repos={data_file}"], [], exec_commands=[f"tasks={command}"]
    )
    assert result == "weav/T1"
