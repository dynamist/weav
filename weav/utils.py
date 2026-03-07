"""Utility functions for data manipulation and CLI argument parsing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TextIO


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with updates taking precedence.

    Args:
        base: The base dictionary
        updates: Dictionary with updates to apply

    Returns:
        New dictionary with merged values

    Example:
        >>> deep_merge({"a": {"b": 1}}, {"a": {"c": 2}})
        {'a': {'b': 1, 'c': 2}}
    """
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_and_wrap(
    parser: Callable[[TextIO], Any],
    file_obj: TextIO,
    wrapper_key: str | None = None,
) -> dict[str, Any]:
    """Load file using provided parser and optionally wrap in a key if it's a list.

    Args:
        parser: Function that takes a file object and returns parsed data
        file_obj: File object to parse
        wrapper_key: Optional key to wrap non-dict data under

    Returns:
        Dictionary with parsed data, optionally wrapped under wrapper_key
    """
    loaded: Any = parser(file_obj)
    if isinstance(loaded, list):
        if wrapper_key:
            return {wrapper_key: loaded}
        return {"data": loaded}
    if isinstance(loaded, dict):
        return loaded
    if wrapper_key:
        return {wrapper_key: loaded}
    return {"data": loaded}


def mangle_keyval(keys: list[str], sep: str | None = ",") -> dict[str, str]:
    """Parse CLI key=value arguments into a dictionary.

    Args:
        keys: List of strings containing key=value pairs
        sep: Character to split multiple pairs on (default: ",").
            Set to None to disable splitting.

    Returns:
        Dictionary with parsed key-value pairs

    Example:
        >>> mangle_keyval(["key=val", "foo=bar"])
        {'key': 'val', 'foo': 'bar'}

        >>> mangle_keyval(["key=val,foo=bar", "baz=1"])
        {'key': 'val', 'foo': 'bar', 'baz': '1'}

        >>> mangle_keyval(["key=a,b,c"], sep=None)
        {'key': 'a,b,c'}
    """
    result: dict[str, str] = {}
    for keyvals in keys:
        pairs = keyvals.split(sep) if sep else [keyvals]
        for pair in pairs:
            key, value = pair.split("=", 1)
            result[key] = value
    return result


def mangle_commas(keys: list[str]) -> list[str]:
    """Parse CLI comma-separated arguments into a flat list.

    Args:
        keys: List of strings containing comma-separated values

    Returns:
        Flattened list with all values

    Example:
        >>> mangle_commas(["key1,key2,key3"])
        ['key1', 'key2', 'key3']

        >>> mangle_commas(["key1,key2", "key3"])
        ['key1', 'key2', 'key3']
    """
    result: list[str] = []
    for key in keys:
        result.extend(key.split(","))
    return result
