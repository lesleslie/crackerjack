# tests/test_phase2_scenarios.py

def test_simple_assertion():
    """Test simple assertion failure."""
    assert 1 == 2


def test_assertion_with_message():
    """Test assertion with custom message."""
    assert False, "This should always fail with a message"


def test_comparison_assertion():
    """Test comparison that shows diff."""
    expected = {"a": 1, "b": 2, "c": 3}
    actual = {"a": 1, "b": 99, "c": 3}
    assert expected == actual


def test_exception():
    """Test uncaught exception."""
    raise ValueError("Intentional error")


def test_with_stdout():
    """Test with captured stdout."""
    print("Debug output 1")
    print("Debug output 2")
    assert False


def test_import_error():
    """Test import error."""
    import nonexistent_module


def test_nested_exception():
    """Test nested exception."""
    def inner():
        raise RuntimeError("Inner error")

    def outer():
        inner()

    outer()
