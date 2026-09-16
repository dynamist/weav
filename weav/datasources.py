"""Data source abstractions for template context building.

This module provides a pluggable data source architecture using Python's
Protocol for structural typing. Data sources can load context data from
various backends (files, CLI arguments, environment variables, etc.).
"""

from __future__ import annotations

import io
import json
import os
import re
import shlex
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TextIO

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from weav.utils import deep_merge, load_and_wrap, mangle_keyval


class DataSourceError(Exception):
    """Error raised when a data source fails to produce data."""


def _parse_yaml(file_obj: TextIO) -> Any:  # noqa: ANN401
    """Parse YAML from a text stream; the document shape is arbitrary."""
    return YAML(typ="safe").load(file_obj)


def _parse_toml(file_obj: TextIO) -> Any:  # noqa: ANN401
    """Parse TOML from a text stream; the document shape is arbitrary.

    tomllib.load() requires a binary handle, so read the text and use loads().
    """
    return tomllib.loads(file_obj.read())


_PARSERS: dict[str, Callable[[TextIO], Any]] = {
    "yaml": _parse_yaml,
    "json": json.load,
    "toml": _parse_toml,
}

#: Format names accepted by the KEY:FORMAT=SOURCE spec syntax.
FORMATS: tuple[str, ...] = tuple(_PARSERS)


def get_parser(fmt: str) -> Callable[[TextIO], Any]:
    """Return the parser callable for a format name.

    Args:
        fmt: One of the names in FORMATS ("yaml", "json", "toml")

    Returns:
        A callable taking a text stream and returning the parsed data

    Raises:
        DataSourceError: If the format name is not recognised
    """
    try:
        return _PARSERS[fmt]
    except KeyError:
        valid = ", ".join(FORMATS)
        msg = f"Unknown format '{fmt}'. Valid formats: {valid}"
        raise DataSourceError(msg) from None


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

    Supports namespacing the loaded data under a specified key.
    Note: Since YAML is a superset of JSON, this also handles JSON files.

    Args:
        path: Path to the YAML file
        wrapper_key: Optional key to namespace the loaded data under

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

    Supports namespacing the loaded data under a specified key.

    Args:
        path: Path to the JSON file
        wrapper_key: Optional key to namespace the loaded data under

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

    Supports namespacing the loaded data under a specified key.

    Args:
        path: Path to the TOML file
        wrapper_key: Optional key to namespace the loaded data under

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
        wrapper_key: Optional key to namespace the loaded data under
        fmt: Format to parse stdin as (one of FORMATS); defaults to YAML

    Example:
        >>> source = StdinDataSource()
        >>> data = source.load()  # Reads YAML from stdin

        >>> source = StdinDataSource(fmt="json")
        >>> data = source.load()  # Reads JSON from stdin
    """

    def __init__(self, wrapper_key: str | None = None, fmt: str = "yaml") -> None:
        self._wrapper_key = wrapper_key
        self._fmt = fmt
        self._parser = get_parser(fmt)

    @property
    def name(self) -> str:
        """Return identifier for stdin."""
        return "<stdin>"

    def load(self) -> dict[str, Any]:
        """Load data from stdin and return as dictionary.

        Returns:
            Dictionary with loaded data, optionally wrapped under wrapper_key
        """
        return load_and_wrap(self._parser, sys.stdin, self._wrapper_key)


class ExecDataSource:
    """Run a command and use its standard output as data.

    The command is split with shlex and executed directly, without a shell,
    so shell metacharacters (pipes, redirects, globs) are not interpreted.
    The command's stderr is inherited rather than captured, so its own
    diagnostics reach the user as they would in a shell pipeline.

    Args:
        command: Command line to run, e.g. "phabfive --format=yaml paste search"
        wrapper_key: Optional key to namespace the loaded data under
        fmt: Format to parse the command's stdout as; defaults to YAML

    Example:
        >>> source = ExecDataSource("date +%Y", wrapper_key="year")
        >>> data = source.load()
    """

    def __init__(
        self,
        command: str,
        wrapper_key: str | None = None,
        fmt: str = "yaml",
    ) -> None:
        self._command = command
        self._wrapper_key = wrapper_key
        self._fmt = fmt
        self._parser = get_parser(fmt)

    @property
    def name(self) -> str:
        """Return the command as identifier."""
        return f"exec:{self._command}"

    def load(self) -> dict[str, Any]:
        """Run the command and parse its stdout.

        Returns:
            Dictionary with parsed data, optionally wrapped under wrapper_key

        Raises:
            DataSourceError: If the command is empty, exits non-zero, or its
                output cannot be parsed as the expected format
            FileNotFoundError: If the executable does not exist
        """
        argv = shlex.split(self._command)
        if not argv:
            msg = f"Empty command: {self._command!r}"
            raise DataSourceError(msg)

        # S603: shell=False and argv comes from shlex.split, so no shell
        # metacharacters are evaluated. The command is user-supplied by design.
        proc = subprocess.run(  # noqa: S603
            argv,
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            msg = f"Command failed with exit code {proc.returncode}: {self._command}"
            raise DataSourceError(msg)

        try:
            return load_and_wrap(self._parser, io.StringIO(proc.stdout), self._wrapper_key)
        except (YAMLError, ValueError) as exc:
            msg = f"Could not parse {self._fmt} output of command: {self._command}\n{exc}"
            raise DataSourceError(msg) from exc


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


#: Matches an optional "KEY", optional ":FORMAT" and the "=" that ends the
#: prefix of a data spec. The key deliberately excludes whitespace and path
#: characters so that bare paths ("./my=dir/x.yaml") and commands containing
#: "=" ("phabfive --format=yaml ...") are not mistaken for a KEY= prefix.
_SPEC_RE = re.compile(r"^(?P<key>[^\s/\\:=.]+)?(?::(?P<fmt>[A-Za-z0-9_]+))?=")

#: File suffixes that imply a format when none is given explicitly.
_SUFFIX_FORMATS = {".json": "json", ".toml": "toml"}


def parse_data_spec(spec: str) -> tuple[str, str | None, str | None]:
    r"""Parse a data specification into source, wrapper key and format.

    The grammar is ``[KEY][:FORMAT]=SOURCE``, where SOURCE is a file path,
    ``-`` for stdin, or (for --exec) a command line.

    A prefix is only recognised when KEY looks like a name: it may not contain
    whitespace, ``/``, ``\``, ``:``, ``=`` or ``.``. This keeps bare paths and
    commands that contain ``=`` intact.

    Args:
        spec: Data specification

    Returns:
        Tuple of (source, wrapper_key or None, format or None)

    Example:
        >>> parse_data_spec("config.yaml")
        ('config.yaml', None, None)
        >>> parse_data_spec("items=tasks.yaml")
        ('tasks.yaml', 'items', None)
        >>> parse_data_spec("items:json=out")
        ('out', 'items', 'json')
        >>> parse_data_spec(":json=-")
        ('-', None, 'json')
        >>> parse_data_spec("phabfive --format=yaml paste search")
        ('phabfive --format=yaml paste search', None, None)
    """
    match = _SPEC_RE.match(spec)
    if match is None:
        return (spec, None, None)
    return (spec[match.end() :], match.group("key"), match.group("fmt"))


def _file_source(path: Path, wrapper_key: str | None, fmt: str | None) -> DataSource:
    """Return the data source for a file, choosing a parser by format or suffix.

    Args:
        path: Path to the data file
        wrapper_key: Optional key to namespace the loaded data under
        fmt: Explicit format, or None to infer from the file suffix

    Returns:
        A data source for the file

    Raises:
        DataSourceError: If an explicit format is not recognised
    """
    if fmt is None:
        fmt = _SUFFIX_FORMATS.get(path.suffix, "yaml")
    get_parser(fmt)  # validates the format name
    if fmt == "json":
        return JsonDataSource(path, wrapper_key)
    if fmt == "toml":
        return TomlDataSource(path, wrapper_key)
    return YamlDataSource(path, wrapper_key)


def build_sources_from_args(
    data_files: list[str],
    keyvals: list[str],
    env_prefixes: list[str] | None = None,
    exec_commands: list[str] | None = None,
) -> list[DataSource]:
    """Convert CLI arguments to DataSource objects.

    This is the bridge between CLI argument parsing and the DataSource
    abstraction layer.

    Precedence is fixed and documented (last wins):
    --data files, then --exec commands, then --env prefixes, then --keyval.

    Args:
        data_files: List of data file specifications
        keyvals: List of key=value strings
        env_prefixes: List of environment variable prefixes to load
        exec_commands: List of command specifications to run for data

    Returns:
        List of DataSource objects in precedence order (last wins)

    Raises:
        DataSourceError: If a spec names an unrecognised format
    """
    sources: list[DataSource] = []

    for spec in data_files:
        path, wrapper_key, fmt = parse_data_spec(spec)
        if path == "-":
            sources.append(StdinDataSource(wrapper_key, fmt or "yaml"))
        else:
            sources.append(_file_source(Path(path), wrapper_key, fmt))

    for spec in exec_commands or []:
        command, wrapper_key, fmt = parse_data_spec(spec)
        sources.append(ExecDataSource(command, wrapper_key, fmt or "yaml"))

    if env_prefixes:
        for prefix in env_prefixes:
            # Empty string means no prefix filter
            sources.append(EnvDataSource(prefix=prefix if prefix else None))

    if keyvals:
        sources.append(KeyvalDataSource(keyvals))

    return sources
