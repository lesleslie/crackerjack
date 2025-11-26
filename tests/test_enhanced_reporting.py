def test_assertion_failure():
    assert 1 == 2, "Expected equality failure"

def test_exception_failure():
    raise ValueError("Intentional error for testing")

def test_import_error():
    import nonexistent_module
