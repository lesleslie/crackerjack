# tests/test_phase2_scenarios.py

from typing import Never

import pytest

pytest.skip(
    "Phase 2 scenario fixtures intentionally fail; disable during refactor cleanup.",
    allow_module_level=True,
)

def test_simple_assertion() -> None:
    """Test simple assertion failure."""
    assert 1 == 2


def test_assertion_with_message() -> None:
    """Test assertion with custom message."""
    msg = "This should always fail with a message"
    raise AssertionError(msg)


def test_comparison_assertion() -> None:
    """Test comparison that shows diff."""
    expected = {"a": 1, "b": 2, "c": 3}
    actual = {"a": 1, "b": 99, "c": 3}
    assert expected == actual


def test_exception() -> Never:
    """Test uncaught exception."""
    msg = "Intentional error"
    raise ValueError(msg)


def test_with_stdout() -> None:
    """Test with captured stdout."""
    raise AssertionError


def test_import_error() -> None:
    """Test import error."""
    import nonexistent_module


def test_nested_exception() -> None:
    """Test nested exception."""
    def inner() -> Never:
        msg = "Inner error"
        raise RuntimeError(msg)

    def outer() -> None:
        inner()

    outer()
