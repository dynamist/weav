"""Tests for the datasources module."""

from pathlib import Path

import pytest
from weav.datasources import (
    ContextBuilder,
    EnvDataSource,
    JsonDataSource,
    KeyvalDataSource,
    StdinDataSource,
    TomlDataSource,
    YamlDataSource,
    build_sources_from_args,
    parse_data_spec,
)


class TestYamlDataSource:
    """Tests for YamlDataSource."""

    def test_load_dict_yaml(self, tmp_path: Path):
        """Test loading a YAML dictionary."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("name: World\ncount: 5\n")

        source = YamlDataSource(yaml_file)
        result = source.load()

        assert result == {"name": "World", "count": 5}

    def test_load_list_yaml_default_wrapper(self, tmp_path: Path):
        """Test loading a YAML list wraps under 'data' by default."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("- apple\n- banana\n- cherry\n")

        source = YamlDataSource(yaml_file)
        result = source.load()

        assert result == {"data": ["apple", "banana", "cherry"]}

    def test_load_list_yaml_custom_wrapper(self, tmp_path: Path):
        """Test loading a YAML list with custom wrapper key."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("- apple\n- banana\n")

        source = YamlDataSource(yaml_file, wrapper_key="items")
        result = source.load()

        assert result == {"items": ["apple", "banana"]}

    def test_name_property(self, tmp_path: Path):
        """Test the name property returns the path."""
        yaml_file = tmp_path / "file.yaml"
        source = YamlDataSource(yaml_file)
        assert source.name == str(yaml_file)

    def test_file_not_found(self, tmp_path: Path):
        """Test FileNotFoundError for missing file."""
        source = YamlDataSource(tmp_path / "nonexistent.yaml")
        with pytest.raises(FileNotFoundError):
            source.load()

    def test_nested_yaml(self, tmp_path: Path):
        """Test loading nested YAML structures."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("config:\n  host: localhost\n  port: 8080\n")

        source = YamlDataSource(yaml_file)
        result = source.load()

        assert result == {"config": {"host": "localhost", "port": 8080}}


class TestJsonDataSource:
    """Tests for JsonDataSource."""

    def test_load_dict_json(self, tmp_path: Path):
        """Test loading a JSON dictionary."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "World", "count": 5}')

        source = JsonDataSource(json_file)
        result = source.load()

        assert result == {"name": "World", "count": 5}

    def test_load_list_json_default_wrapper(self, tmp_path: Path):
        """Test loading a JSON list wraps under 'data' by default."""
        json_file = tmp_path / "test.json"
        json_file.write_text('["apple", "banana", "cherry"]')

        source = JsonDataSource(json_file)
        result = source.load()

        assert result == {"data": ["apple", "banana", "cherry"]}

    def test_load_list_json_custom_wrapper(self, tmp_path: Path):
        """Test loading a JSON list with custom wrapper key."""
        json_file = tmp_path / "test.json"
        json_file.write_text('["apple", "banana"]')

        source = JsonDataSource(json_file, wrapper_key="items")
        result = source.load()

        assert result == {"items": ["apple", "banana"]}

    def test_name_property(self, tmp_path: Path):
        """Test the name property returns the path."""
        json_file = tmp_path / "file.json"
        source = JsonDataSource(json_file)
        assert source.name == str(json_file)

    def test_file_not_found(self, tmp_path: Path):
        """Test FileNotFoundError for missing file."""
        source = JsonDataSource(tmp_path / "nonexistent.json")
        with pytest.raises(FileNotFoundError):
            source.load()

    def test_nested_json(self, tmp_path: Path):
        """Test loading nested JSON structures."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"config": {"host": "localhost", "port": 8080}}')

        source = JsonDataSource(json_file)
        result = source.load()

        assert result == {"config": {"host": "localhost", "port": 8080}}


class TestTomlDataSource:
    """Tests for TomlDataSource."""

    def test_load_dict_toml(self, tmp_path: Path):
        """Test loading a TOML dictionary."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('name = "World"\ncount = 5\n')

        source = TomlDataSource(toml_file)
        result = source.load()

        assert result == {"name": "World", "count": 5}

    def test_load_toml_with_wrapper(self, tmp_path: Path):
        """Test loading TOML with custom wrapper key."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('name = "World"\n')

        source = TomlDataSource(toml_file, wrapper_key="config")
        result = source.load()

        assert result == {"config": {"name": "World"}}

    def test_name_property(self, tmp_path: Path):
        """Test the name property returns the path."""
        toml_file = tmp_path / "file.toml"
        source = TomlDataSource(toml_file)
        assert source.name == str(toml_file)

    def test_file_not_found(self, tmp_path: Path):
        """Test FileNotFoundError for missing file."""
        source = TomlDataSource(tmp_path / "nonexistent.toml")
        with pytest.raises(FileNotFoundError):
            source.load()

    def test_nested_toml(self, tmp_path: Path):
        """Test loading nested TOML structures."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('[config]\nhost = "localhost"\nport = 8080\n')

        source = TomlDataSource(toml_file)
        result = source.load()

        assert result == {"config": {"host": "localhost", "port": 8080}}

    def test_toml_array_of_tables(self, tmp_path: Path):
        """Test loading TOML array of tables."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('[[items]]\nname = "apple"\n\n[[items]]\nname = "banana"\n')

        source = TomlDataSource(toml_file)
        result = source.load()

        assert result == {"items": [{"name": "apple"}, {"name": "banana"}]}


class TestKeyvalDataSource:
    """Tests for KeyvalDataSource."""

    def test_load_simple_keyvals(self):
        """Test loading simple key=value pairs."""
        source = KeyvalDataSource(["name=World", "count=5"])
        result = source.load()
        assert result == {"name": "World", "count": "5"}

    def test_load_keyval_with_equals_in_value(self):
        """Test key=value where value contains equals sign."""
        source = KeyvalDataSource(["equation=a=b+c"])
        result = source.load()
        assert result == {"equation": "a=b+c"}

    def test_load_keyval_with_comma_in_value(self):
        """Test key=value where value contains comma (no split)."""
        source = KeyvalDataSource(["items=a,b,c"])
        result = source.load()
        assert result == {"items": "a,b,c"}

    def test_load_empty_keyvals(self):
        """Test loading empty keyvals list."""
        source = KeyvalDataSource([])
        result = source.load()
        assert result == {}

    def test_name_property(self):
        """Test the name property."""
        source = KeyvalDataSource(["key=val"])
        assert source.name == "keyval"


class TestEnvDataSource:
    """Tests for EnvDataSource."""

    def test_load_with_prefix(self, monkeypatch):
        """Test loading env vars with prefix filtering."""
        monkeypatch.setenv("WEAV_NAME", "World")
        monkeypatch.setenv("WEAV_COUNT", "5")
        monkeypatch.setenv("OTHER_VAR", "ignored")

        source = EnvDataSource(prefix="WEAV_")
        result = source.load()

        assert result == {"name": "World", "count": "5"}
        assert "other_var" not in result

    def test_load_without_prefix(self, monkeypatch):
        """Test loading all env vars without prefix."""
        monkeypatch.setenv("TEST_VAR", "value")

        source = EnvDataSource()
        result = source.load()

        assert "test_var" in result
        assert result["test_var"] == "value"

    def test_strip_prefix_disabled(self, monkeypatch):
        """Test keeping prefix in keys."""
        monkeypatch.setenv("WEAV_NAME", "World")

        source = EnvDataSource(prefix="WEAV_", strip_prefix=False)
        result = source.load()

        assert result == {"weav_name": "World"}

    def test_lowercase_keys_disabled(self, monkeypatch):
        """Test keeping original case in keys."""
        monkeypatch.setenv("WEAV_NAME", "World")

        source = EnvDataSource(prefix="WEAV_", lowercase_keys=False)
        result = source.load()

        # Windows env vars are always uppercase, so we check for uppercase
        assert result == {"NAME": "World"}

    def test_name_property_with_prefix(self):
        """Test the name property with prefix."""
        source = EnvDataSource(prefix="WEAV_")
        assert source.name == "env:WEAV_*"

    def test_name_property_without_prefix(self):
        """Test the name property without prefix."""
        source = EnvDataSource()
        assert source.name == "env"

    def test_empty_result_with_unmatched_prefix(self, monkeypatch):
        """Test that unmatched prefix returns empty dict."""
        monkeypatch.setenv("OTHER_VAR", "value")

        source = EnvDataSource(prefix="WEAV_")
        result = source.load()

        assert result == {}


class TestStdinDataSource:
    """Tests for StdinDataSource."""

    def test_name_property(self):
        """Test the name property."""
        source = StdinDataSource()
        assert source.name == "<stdin>"

    def test_name_property_with_wrapper(self):
        """Test the name property with wrapper key."""
        source = StdinDataSource(wrapper_key="items")
        assert source.name == "<stdin>"


class TestContextBuilder:
    """Tests for ContextBuilder."""

    def test_build_empty_sources(self):
        """Test building with no sources."""
        builder = ContextBuilder([])
        result = builder.build()
        assert result == {}

    def test_build_single_source(self):
        """Test building with a single source."""
        source = KeyvalDataSource(["name=World"])
        builder = ContextBuilder([source])
        result = builder.build()
        assert result == {"name": "World"}

    def test_build_multiple_sources_merge(self, tmp_path: Path):
        """Test that multiple sources are deep-merged."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("name: FromFile\ngreeting: Hello\n")

        file_source = YamlDataSource(yaml_file)
        keyval_source = KeyvalDataSource(["name=FromKeyval"])

        builder = ContextBuilder([file_source, keyval_source])
        result = builder.build()

        assert result == {"name": "FromKeyval", "greeting": "Hello"}

    def test_build_later_source_wins(self, tmp_path: Path):
        """Test that later sources override earlier ones."""
        file1 = tmp_path / "first.yaml"
        file1.write_text("priority: low\nvalue: first\n")
        file2 = tmp_path / "second.yaml"
        file2.write_text("priority: high\n")

        source1 = YamlDataSource(file1)
        source2 = YamlDataSource(file2)
        builder = ContextBuilder([source1, source2])
        result = builder.build()

        assert result == {"priority": "high", "value": "first"}

    def test_build_deep_merge(self, tmp_path: Path):
        """Test that nested dictionaries are deep-merged."""
        file1 = tmp_path / "first.yaml"
        file1.write_text("config:\n  host: localhost\n  port: 8080\n")
        file2 = tmp_path / "second.yaml"
        file2.write_text("config:\n  port: 9000\n  debug: true\n")

        source1 = YamlDataSource(file1)
        source2 = YamlDataSource(file2)
        builder = ContextBuilder([source1, source2])
        result = builder.build()

        assert result == {
            "config": {
                "host": "localhost",
                "port": 9000,
                "debug": True,
            }
        }

    def test_add_method(self):
        """Test the add() method for chaining."""
        source1 = KeyvalDataSource(["a=1"])
        source2 = KeyvalDataSource(["b=2"])

        builder = ContextBuilder()
        builder.add(source1).add(source2)
        result = builder.build()

        assert result == {"a": "1", "b": "2"}

    def test_add_returns_self(self):
        """Test that add() returns self for chaining."""
        builder = ContextBuilder()
        result = builder.add(KeyvalDataSource(["key=val"]))
        assert result is builder


class TestParseDataSpec:
    """Tests for parse_data_spec."""

    def test_simple_filename(self):
        """Test parsing a simple filename."""
        path, wrapper = parse_data_spec("config.yaml")
        assert path == "config.yaml"
        assert wrapper is None

    def test_stdin_marker(self):
        """Test parsing stdin marker."""
        path, wrapper = parse_data_spec("-")
        assert path == "-"
        assert wrapper is None

    def test_wrapped_filename(self):
        """Test parsing key=filename format."""
        path, wrapper = parse_data_spec("items=tasks.yaml")
        assert path == "tasks.yaml"
        assert wrapper == "items"

    def test_wrapped_stdin(self):
        """Test parsing key=- format."""
        path, wrapper = parse_data_spec("data=-")
        assert path == "-"
        assert wrapper == "data"


class TestBuildSourcesFromArgs:
    """Tests for build_sources_from_args."""

    def test_empty_args(self):
        """Test building sources from empty arguments."""
        sources = build_sources_from_args([], [])
        assert sources == []

    def test_single_file(self):
        """Test building sources with a single file."""
        sources = build_sources_from_args(["config.yaml"], [])
        assert len(sources) == 1
        assert isinstance(sources[0], YamlDataSource)
        assert sources[0].name == "config.yaml"

    def test_multiple_files(self):
        """Test building sources with multiple files."""
        sources = build_sources_from_args(["base.yaml", "override.yaml"], [])
        assert len(sources) == 2
        assert all(isinstance(s, YamlDataSource) for s in sources)

    def test_file_with_wrapper(self):
        """Test building sources with wrapped file."""
        sources = build_sources_from_args(["items=tasks.yaml"], [])
        assert len(sources) == 1
        assert isinstance(sources[0], YamlDataSource)

    def test_stdin_source(self):
        """Test building sources with stdin marker."""
        sources = build_sources_from_args(["-"], [])
        assert len(sources) == 1
        assert isinstance(sources[0], StdinDataSource)

    def test_keyvals_only(self):
        """Test building sources with only keyvals."""
        sources = build_sources_from_args([], ["name=World"])
        assert len(sources) == 1
        assert isinstance(sources[0], KeyvalDataSource)

    def test_files_and_keyvals(self):
        """Test building sources with both files and keyvals."""
        sources = build_sources_from_args(["config.yaml"], ["name=World"])
        assert len(sources) == 2
        assert isinstance(sources[0], YamlDataSource)
        assert isinstance(sources[1], KeyvalDataSource)

    def test_keyvals_last(self):
        """Test that keyvals source is always last (for precedence)."""
        sources = build_sources_from_args(["a.yaml", "b.yaml"], ["key=val"])
        assert len(sources) == 3
        assert isinstance(sources[-1], KeyvalDataSource)

    def test_json_file(self):
        """Test building sources with a JSON file."""
        sources = build_sources_from_args(["config.json"], [])
        assert len(sources) == 1
        assert isinstance(sources[0], JsonDataSource)
        assert sources[0].name == "config.json"

    def test_mixed_yaml_and_json(self):
        """Test building sources with both YAML and JSON files."""
        sources = build_sources_from_args(["base.yaml", "override.json"], [])
        assert len(sources) == 2
        assert isinstance(sources[0], YamlDataSource)
        assert isinstance(sources[1], JsonDataSource)

    def test_json_file_with_wrapper(self):
        """Test building sources with wrapped JSON file."""
        sources = build_sources_from_args(["items=tasks.json"], [])
        assert len(sources) == 1
        assert isinstance(sources[0], JsonDataSource)

    def test_toml_file(self):
        """Test building sources with a TOML file."""
        sources = build_sources_from_args(["config.toml"], [])
        assert len(sources) == 1
        assert isinstance(sources[0], TomlDataSource)
        assert sources[0].name == "config.toml"

    def test_mixed_yaml_json_toml(self):
        """Test building sources with YAML, JSON, and TOML files."""
        sources = build_sources_from_args(["base.yaml", "override.json", "final.toml"], [])
        assert len(sources) == 3
        assert isinstance(sources[0], YamlDataSource)
        assert isinstance(sources[1], JsonDataSource)
        assert isinstance(sources[2], TomlDataSource)

    def test_toml_file_with_wrapper(self):
        """Test building sources with wrapped TOML file."""
        sources = build_sources_from_args(["config=settings.toml"], [])
        assert len(sources) == 1
        assert isinstance(sources[0], TomlDataSource)
