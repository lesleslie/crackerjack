from crackerjack.__main__ import main


def test_main_basic() -> None:
    import inspect

    assert callable(main), "Function should be callable"

    sig = inspect.signature(main)
    assert sig is not None, "Function should have valid signature"

    for param in sig.parameters.values():
        assert param.default is not inspect.Parameter.empty, (
            f"Parameter {param.name} should have a default value for CLI usage"
        )
