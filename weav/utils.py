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
    """Load file using provided parser and wrap under wrapper_key if given.

    Args:
        parser: Function that takes a file object and returns parsed data
        file_obj: File object to parse
        wrapper_key: Key to namespace the data under, regardless of its shape

    Returns:
        Dictionary with parsed data. With wrapper_key, always
        {wrapper_key: data}; without, mappings are returned as-is and
        lists/scalars are wrapped under a "data" key.
    """
    loaded: Any = parser(file_obj)
    if wrapper_key:
        return {wrapper_key: loaded}
    if isinstance(loaded, dict):
        return loaded
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

        A value may contain the separator. Splitting only happens when every
        resulting piece is itself a KEY=VALUE pair, so a prose value survives:

        >>> mangle_keyval(["title=Hello, World"])
        {'title': 'Hello, World'}
    """
    result: dict[str, str] = {}
    for keyvals in keys:
        for pair in _split_pairs(keyvals, sep):
            key, found, value = pair.partition("=")
            # Keys are stripped so "a=1, b=2" does not yield a " b" key; the
            # separator heuristic above cannot tell that space from part of a
            # value, and a padded key is never what the caller meant.
            key = key.strip()
            if not found or not key:
                raise ValueError(f"expected KEY=VALUE, got {pair!r}")
            result[key] = value
    return result


def _split_pairs(keyvals: str, sep: str | None) -> list[str]:
    """Split a KEY=VAL[,KEY=VAL...] string, tolerating separators in values."""
    if not sep:
        return [keyvals]
    pairs = keyvals.split(sep)
    # "title=Hello, World" splits into a piece with no "=", which means the
    # separator belonged to the value rather than joining two pairs.
    if any("=" not in pair for pair in pairs):
        return [keyvals]
    return pairs


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
