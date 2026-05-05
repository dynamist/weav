"""Data source abstractions for template context building.

This module provides a pluggable data source architecture using Python's
Protocol for structural typing. Data sources can load context data from
various backends (files, CLI arguments, environment variables, etc.).
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any, Protocol

from ruamel.yaml import YAML

from weav.utils import deep_merge, load_and_wrap, mangle_keyval


class DataSource(Protocol):
    """Protocol for data sources that provide template context data.

    Any class implementing this protocol can be used as a data source
    for building template contexts.
    """

    @property
    def name(self) -> str:
        """Return identifier for debugging/logging."""
        ...

    def load(self) -> dict[str, Any]:
        """Load and return data as a dictionary."""
        ...


class YamlDataSource:
    """Load data from a YAML file.

    Supports wrapping non-dict data under a specified key.
    Note: Since YAML is a superset of JSON, this also handles JSON files.

    Args:
        path: Path to the YAML file
        wrapper_key: Optional key to wrap non-dict data under

    Example:
        >>> source = YamlDataSource(Path("config.yaml"))
        >>> data = source.load()
        >>> print(data)
        {'key': 'value', ...}

        >>> source = YamlDataSource(Path("items.yaml"), wrapper_key="items")
        >>> data = source.load()  # List wrapped under 'items' key
    """

    def __init__(self, path: Path, wrapper_key: str | None = None) -> None:
        self._path = path
        self._wrapper_key = wrapper_key
        self._yaml = YAML(typ="safe")

    @property
    def name(self) -> str:
        """Return the file path as identifier."""
        return str(self._path)

    def load(self) -> dict[str, Any]:
        """Load YAML data from file and return as dictionary.

        Returns:
            Dictionary with loaded data, optionally wrapped under wrapper_key

        Raises:
            FileNotFoundError: If the file does not exist
            ruamel.yaml.YAMLError: If YAML parsing fails
        """
        with self._path.open() as f:
            return load_and_wrap(self._yaml.load, f, self._wrapper_key)


class JsonDataSource:
    """Load data from a JSON file.

    Supports wrapping non-dict data under a specified key.

    Args:
        path: Path to the JSON file
        wrapper_key: Optional key to wrap non-dict data under

    Example:
        >>> source = JsonDataSource(Path("config.json"))
        >>> data = source.load()
        >>> print(data)
        {'key': 'value', ...}

        >>> source = JsonDataSource(Path("items.json"), wrapper_key="items")
        >>> data = source.load()  # List wrapped under 'items' key
    """

    def __init__(self, path: Path, wrapper_key: str | None = None) -> None:
        self._path = path
        self._wrapper_key = wrapper_key

    @property
    def name(self) -> str:
        """Return the file path as identifier."""
        return str(self._path)

    def load(self) -> dict[str, Any]:
        """Load JSON data from file and return as dictionary.

        Returns:
            Dictionary with loaded data, optionally wrapped under wrapper_key

        Raises:
            FileNotFoundError: If the file does not exist
            json.JSONDecodeError: If JSON parsing fails
        """
        with self._path.open() as f:
            return load_and_wrap(json.load, f, self._wrapper_key)


class TomlDataSource:
    """Load data from a TOML file.

    Supports wrapping non-dict data under a specified key.

    Args:
        path: Path to the TOML file
        wrapper_key: Optional key to wrap non-dict data under

    Example:
        >>> source = TomlDataSource(Path("config.toml"))
        >>> data = source.load()
        >>> print(data)
        {'key': 'value', ...}

        >>> source = TomlDataSource(Path("items.toml"), wrapper_key="items")
        >>> data = source.load()  # Data wrapped under 'items' key
    """

    def __init__(self, path: Path, wrapper_key: str | None = None) -> None:
        self._path = path
        self._wrapper_key = wrapper_key

    @property
    def name(self) -> str:
        """Return the file path as identifier."""
        return str(self._path)

    def load(self) -> dict[str, Any]:
        """Load TOML data from file and return as dictionary.

        Returns:
            Dictionary with loaded data, optionally wrapped under wrapper_key

        Raises:
            FileNotFoundError: If the file does not exist
            tomllib.TOMLDecodeError: If TOML parsing fails
        """
        with self._path.open("rb") as f:
            data = tomllib.load(f)
        if self._wrapper_key:
            return {self._wrapper_key: data}
        return data


class StdinDataSource:
    """Load data from standard input.

    Args:
        wrapper_key: Optional key to wrap non-dict data under

    Example:
        >>> source = StdinDataSource()
        >>> data = source.load()  # Reads YAML from stdin
    """

    def __init__(self, wrapper_key: str | None = None) -> None:
        self._wrapper_key = wrapper_key
        self._yaml = YAML(typ="safe")

    @property
    def name(self) -> str:
        """Return identifier for stdin."""
        return "<stdin>"

    def load(self) -> dict[str, Any]:
        """Load YAML data from stdin and return as dictionary.

        Returns:
            Dictionary with loaded data, optionally wrapped under wrapper_key
        """
        return load_and_wrap(self._yaml.load, sys.stdin, self._wrapper_key)


class KeyvalDataSource:
    """Load data from CLI key=value parameters.

    Args:
        keyvals: List of key=value strings

    Example:
        >>> source = KeyvalDataSource(["name=World", "count=5"])
        >>> data = source.load()
        >>> print(data)
        {'name': 'World', 'count': '5'}
    """

    def __init__(self, keyvals: list[str]) -> None:
        self._keyvals = keyvals

    @property
    def name(self) -> str:
        """Return identifier for keyval source."""
        return "keyval"

    def load(self) -> dict[str, Any]:
        """Parse key=value strings and return as dictionary.

        Returns:
            Dictionary with parsed key-value pairs
        """
        # sep=None allows commas within values
        return mangle_keyval(self._keyvals, sep=None)


class EnvDataSource:
    """Load data from environment variables.

    Reads environment variables, optionally filtered by a prefix.
    The prefix is stripped from variable names in the resulting dictionary.

    Args:
        prefix: Only include variables starting with this prefix.
                If None, includes all environment variables.
        strip_prefix: If True (default), remove the prefix from keys.
        lowercase_keys: If True (default), convert keys to lowercase.

    Example:
        >>> # With WEAV_NAME=World and WEAV_COUNT=5 in environment
        >>> source = EnvDataSource(prefix="WEAV_")
        >>> data = source.load()
        >>> print(data)
        {'name': 'World', 'count': '5'}

        >>> # Without prefix filtering
        >>> source = EnvDataSource()
        >>> data = source.load()  # All env vars
    """

    def __init__(
        self,
        prefix: str | None = None,
        *,
        strip_prefix: bool = True,
        lowercase_keys: bool = True,
    ) -> None:
        self._prefix = prefix
        self._strip_prefix = strip_prefix
        self._lowercase_keys = lowercase_keys

    @property
    def name(self) -> str:
        """Return identifier for env source."""
        if self._prefix:
            return f"env:{self._prefix}*"
        return "env"

    def load(self) -> dict[str, Any]:
        """Read environment variables and return as dictionary.

        Returns:
            Dictionary with environment variable names as keys
        """
        result: dict[str, Any] = {}

        for key, value in os.environ.items():
            if self._prefix:
                if not key.startswith(self._prefix):
                    continue
                if self._strip_prefix:
                    key = key[len(self._prefix) :]

            if self._lowercase_keys:
                key = key.lower()

            result[key] = value

        return result


class ContextBuilder:
    """Build final template context from multiple data sources.

    Sources are loaded and merged in order, with later sources taking
    precedence over earlier ones (last wins).

    Args:
        sources: List of data sources to merge

    Example:
        >>> sources = [
        ...     YamlDataSource(Path("base.yaml")),
        ...     YamlDataSource(Path("override.yaml")),
        ...     KeyvalDataSource(["key=final"]),
        ... ]
        >>> builder = ContextBuilder(sources)
        >>> context = builder.build()  # Merged data, keyval wins
    """

    def __init__(self, sources: list[DataSource] | None = None) -> None:
        self._sources: list[DataSource] = sources or []

    def add(self, source: DataSource) -> ContextBuilder:
        """Add a data source to the builder.

        Args:
            source: Data source to add

        Returns:
            Self for method chaining
        """
        self._sources.append(source)
        return self

    def build(self, *, verbose: bool = False) -> dict[str, Any]:
        """Load all sources and merge in order (last wins).

        Args:
            verbose: If True, print debug info for each loaded source

        Returns:
            Merged dictionary from all data sources
        """
        result: dict[str, Any] = {}
        for source in self._sources:
            loaded = source.load()
            result = deep_merge(result, loaded)
            if verbose:
                print(
                    f"Loaded {source.name} with keys: {list(loaded.keys())}",
                    file=sys.stderr,
                )
        return result


def parse_data_spec(spec: str) -> tuple[str, str | None]:
    """Parse a data file specification into path and optional wrapper key.

    Args:
        spec: Data file specification. Can be:
            - A filename (e.g., "config.yaml")
            - "-" for stdin
            - "key=filename" to wrap the data under a key

    Returns:
        Tuple of (path, wrapper_key or None)

    Example:
        >>> parse_data_spec("config.yaml")
        ('config.yaml', None)
        >>> parse_data_spec("items=tasks.yaml")
        ('tasks.yaml', 'items')
        >>> parse_data_spec("-")
        ('-', None)
    """
    if "=" in spec:
        wrapper_key, path = spec.split("=", 1)
        return (path, wrapper_key)
    return (spec, None)


def build_sources_from_args(
    data_files: list[str],
    keyvals: list[str],
    env_prefixes: list[str] | None = None,
) -> list[DataSource]:
    """Convert CLI arguments to DataSource objects.

    This is the bridge between CLI argument parsing and the DataSource
    abstraction layer.

    Args:
        data_files: List of data file specifications
        keyvals: List of key=value strings
        env_prefixes: List of environment variable prefixes to load

    Returns:
        List of DataSource objects in precedence order (last wins)
    """
    sources: list[DataSource] = []

    for spec in data_files:
        path, wrapper_key = parse_data_spec(spec)
        if path == "-":
            sources.append(StdinDataSource(wrapper_key))
        elif path.endswith(".json"):
            sources.append(JsonDataSource(Path(path), wrapper_key))
        elif path.endswith(".toml"):
            sources.append(TomlDataSource(Path(path), wrapper_key))
        else:
            sources.append(YamlDataSource(Path(path), wrapper_key))

    if env_prefixes:
        for prefix in env_prefixes:
            # Empty string means no prefix filter
            sources.append(EnvDataSource(prefix=prefix if prefix else None))

    if keyvals:
        sources.append(KeyvalDataSource(keyvals))

    return sources
