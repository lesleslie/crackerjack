import pytest


def test_assertion_failure():
    with pytest.raises(AssertionError):
        assert 1 == 2, "Expected equality failure"


def test_exception_failure():
    with pytest.raises(ValueError):
        raise ValueError("Intentional error for testing")


def test_import_error():
    with pytest.raises(ModuleNotFoundError):
        import nonexistent_module
