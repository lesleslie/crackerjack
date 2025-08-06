from crackerjack.py313 import (
    HookResult,
    HookStatus,
    analyze_hook_result,
    clean_python_code,
)


def test_analyze_hook_result_unknown_pattern() -> None:
    unknown_result = {"unexpected": "data", "format": "unknown"}
    result = analyze_hook_result(unknown_result)
    assert result == "Unknown hook result pattern"


def test_analyze_hook_result_error_case() -> None:
    error_result: HookResult = {
        "status": HookStatus.ERROR,
        "hook_id": "test - hook",
        "output": "Something went wrong",
        "files": [],
    }
    result = analyze_hook_result(error_result)
    assert result == "💥 Hook test - hook encountered an error: Something went wrong"


def test_clean_python_code_comment_preservation() -> None:
    test_code = '''# Important comment that should be kept
def function():
    x = 1
    return x
"""This docstring should be removed"""
y = 2
'''

    result = clean_python_code(test_code)

    assert "# Important comment that should be kept" not in result
    assert "x = 1" in result
    assert '"""This docstring should be removed"""' not in result


def test_clean_python_code_special_comment_detection() -> None:
    test_cases = [
        "# type: ignore",
        "# noqa",
        "# nosec",
        "# pragma: no cover",
        "# pylint: disable = unused - variable",
        "# mypy: ignore - errors",
    ]
    for comment in test_cases:
        test_code = f"""def test_function():
    x = 1 {comment}
    return x"""
        result = clean_python_code(test_code)
        assert "x = 1" in result


def test_clean_python_code_docstring_removal() -> None:
    test_code = '''def function():
    """This is a docstring."""
    return 1

class TestClass:
    pass'''

    result = clean_python_code(test_code)

    assert '"""This is a docstring."""' not in result
    assert '"""Class docstring."""' not in result
    assert "def function(): " in result
    assert "class TestClass: " in result


def test_clean_python_code_edge_cases() -> None:
    assert clean_python_code("") == ""
    result = clean_python_code(" \n \n ")
    assert result == ""
    result = clean_python_code("# Just a comment\n# Another comment")
    assert "# Just a comment" not in result


def test_clean_python_code_complex_patterns() -> None:
    test_code = '''def process_data(data: dict) -> str:
    """Process data using match statement."""
    match data:
        case {"type": "success", "value": value}:
            return f"Success: {value}"
        case {"type": "error", "message": msg}:
            return f"Error: {msg}"
        case _:
            return "Unknown"

    return "default"'''
    result = clean_python_code(test_code)
    assert "match data: " in result
    assert "case {" in result
    assert '"""Process data using match statement."""' not in result
    assert "# Important comment" not in result
