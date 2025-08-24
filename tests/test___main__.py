"""Tests for main function."""

from crackerjack.__main__ import main


def test_main_basic() -> None:
    """Test basic functionality of main."""
    import inspect

    # Test that main function exists and is callable
    assert callable(main), "Function should be callable"

    # Test that main function has proper signature
    sig = inspect.signature(main)
    assert sig is not None, "Function should have valid signature"

    # Test that all parameters have defaults (since it's a Typer CLI function)
    for param in sig.parameters.values():
        assert param.default is not inspect.Parameter.empty, (
            f"Parameter {param.name} should have a default value for CLI usage"
        )
