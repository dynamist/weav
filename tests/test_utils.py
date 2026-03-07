"""Tests for utility functions."""

import io

from weav.utils import deep_merge, load_and_wrap, mangle_commas, mangle_keyval


def test_deep_merge_simple():
    """Test simple dictionary merge."""
    base = {"a": 1, "b": 2}
    updates = {"b": 3, "c": 4}
    result = deep_merge(base, updates)
    assert result == {"a": 1, "b": 3, "c": 4}


def test_deep_merge_nested():
    """Test nested dictionary merge."""
    base = {"a": {"b": 1, "c": 2}}
    updates = {"a": {"c": 3, "d": 4}}
    result = deep_merge(base, updates)
    assert result == {"a": {"b": 1, "c": 3, "d": 4}}


def test_deep_merge_does_not_modify_original():
    """Test that deep_merge doesn't modify the original dictionaries."""
    base = {"a": 1}
    updates = {"b": 2}
    result = deep_merge(base, updates)
    assert base == {"a": 1}
    assert updates == {"b": 2}
    assert result == {"a": 1, "b": 2}


def test_load_and_wrap_dict():
    """Test loading a dictionary (no wrapping needed)."""
    data = io.StringIO('{"key": "value"}')

    def parser(f):
        import json

        return json.load(f)

    result = load_and_wrap(parser, data)
    assert result == {"key": "value"}


def test_load_and_wrap_list_default():
    """Test loading a list wraps under 'data' key by default."""
    data = io.StringIO('["a", "b", "c"]')

    def parser(f):
        import json

        return json.load(f)

    result = load_and_wrap(parser, data)
    assert result == {"data": ["a", "b", "c"]}


def test_load_and_wrap_list_custom_key():
    """Test loading a list with custom wrapper key."""
    data = io.StringIO('["a", "b", "c"]')

    def parser(f):
        import json

        return json.load(f)

    result = load_and_wrap(parser, data, wrapper_key="items")
    assert result == {"items": ["a", "b", "c"]}


def test_mangle_keyval_simple():
    """Test simple key=value parsing."""
    result = mangle_keyval(["key=val", "foo=bar"])
    assert result == {"key": "val", "foo": "bar"}


def test_mangle_keyval_comma_separated():
    """Test comma-separated key=value pairs."""
    result = mangle_keyval(["key=val,foo=bar"])
    assert result == {"key": "val", "foo": "bar"}


def test_mangle_keyval_no_split():
    """Test key=value without splitting on comma."""
    result = mangle_keyval(["key=a,b,c"], sep=None)
    assert result == {"key": "a,b,c"}


def test_mangle_commas_simple():
    """Test simple comma splitting."""
    result = mangle_commas(["a,b,c"])
    assert result == ["a", "b", "c"]


def test_mangle_commas_multiple_args():
    """Test comma splitting with multiple arguments."""
    result = mangle_commas(["a,b", "c,d"])
    assert result == ["a", "b", "c", "d"]
