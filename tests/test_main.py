"""Unit tests for __main__.py functions."""

import pytest

from crackerjack.__main__ import _setup_debug_and_verbose_flags


class MockOptions:
    """Mock options object for testing."""

    def __init__(self):
        self.verbose = False


def test_setup_debug_flags_preserves_ai_fix_true():
    """Test that ai_fix=True is preserved when passed."""
    options = MockOptions()

    # ai_fix=True should be preserved
    ai_fix, verbose = _setup_debug_and_verbose_flags(
        ai_fix=True, ai_debug=False, debug=False, verbose=False, options=options
    )

    assert ai_fix is True, "ai_fix=True should be preserved"


def test_setup_debug_flags_preserves_ai_fix_false():
    """Test that ai_fix=False is preserved when passed."""
    options = MockOptions()

    # ai_fix=False should be preserved
    ai_fix, verbose = _setup_debug_and_verbose_flags(
        ai_fix=False, ai_debug=False, debug=False, verbose=False, options=options
    )

    assert ai_fix is False, "ai_fix=False should be preserved"


def test_setup_debug_flags_ai_debug_implies_ai_fix():
    """Test that ai_debug=True forces ai_fix=True."""
    options = MockOptions()

    # ai_debug=True should override ai_fix to True
    ai_fix, verbose = _setup_debug_and_verbose_flags(
        ai_fix=False,  # Even if False
        ai_debug=True,  # This should force it to True
        debug=False,
        verbose=False,
        options=options,
    )

    assert ai_fix is True, "ai_debug=True should force ai_fix=True"
    assert verbose is True, "ai_debug=True should set verbose=True"
    assert options.verbose is True, "ai_debug=True should set options.verbose=True"


def test_setup_debug_flags_debug_sets_verbose():
    """Test that debug=True sets verbose=True."""
    options = MockOptions()

    ai_fix, verbose = _setup_debug_and_verbose_flags(
        ai_fix=False, ai_debug=False, debug=True, verbose=False, options=options
    )

    assert verbose is True, "debug=True should set verbose=True"
    assert options.verbose is True, "debug=True should set options.verbose=True"
