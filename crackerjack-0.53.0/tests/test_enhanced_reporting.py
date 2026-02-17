from typing import Never

import pytest


def test_assertion_failure() -> None:
    with pytest.raises(AssertionError):
        assert 1 == 2, "Expected equality failure"


def test_exception_failure() -> Never:
    with pytest.raises(ValueError):
        msg = "Intentional error for testing"
        raise ValueError(msg)


def test_import_error() -> None:
    with pytest.raises(ModuleNotFoundError):
        import nonexistent_module
