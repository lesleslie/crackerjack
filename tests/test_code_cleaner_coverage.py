"""Coverage tests for code_cleaner.py to target uncovered lines."""

from pathlib import Path

from rich.console import Console
from crackerjack.code_cleaner import CodeCleaner


def test_analyze_workload_characteristics_empty_files() -> None:
    code_cleaner = CodeCleaner(console=Console())
    result = code_cleaner._analyze_workload_characteristics([])
    expected = {
        "total_files": 0,
        "total_size": 0,
        "avg_file_size": 0,
        "complexity": "low",
    }
    assert result == expected


def test_analyze_workload_characteristics_with_files(tmp_path: Path) -> None:
    code_cleaner = CodeCleaner(console=Console())
    file1 = tmp_path / "small.py"
    file1.write_text("def small(): pass")
    file2 = tmp_path / "medium.py"
    file2.write_text("def medium():\n    " + "x = 1\n    " * 100)
    file3 = tmp_path / "large.py"
    large_content = "def large():\n    " + "y = 1\n    " * 1000
    file3.write_text(large_content)
    files = [file1, file2, file3]
    result = code_cleaner._analyze_workload_characteristics(files)
    assert result["total_files"] == 3
    assert result["total_size"] > 0
    assert result["avg_file_size"] > 0
    assert result["complexity"] in ("low", "medium", "high")


def test_remove_line_comments_edge_cases() -> None:
    code_cleaner = CodeCleaner(console=Console())
    test_code = """
def function():
    x = 1  # type: ignore
    y = 2  # noqa
    z = 3  # pragma: no cover
    return x + y + z
"""

    result = code_cleaner.remove_line_comments(test_code)

    assert "# type: ignore" in result
    assert "# noqa" in result
    assert "# pragma: no cover" in result
    assert "# Regular comment to remove" not in result


def test_remove_docstrings_edge_cases() -> None:
    code_cleaner = CodeCleaner(console=Console())
    test_code = """
def function():
    x = "not a docstring"
    return x

class TestClass:

    def method(self):
        return "also not a docstring"
"""

    result = code_cleaner.remove_docstrings(test_code)

    assert '"""Function docstring' not in result
    assert '"""Class docstring."""' not in result
    assert '"""Method docstring."""' not in result

    assert '"not a docstring"' in result
    assert '"also not a docstring"' in result


def test_clean_file_with_nonexistent_file() -> None:
    code_cleaner = CodeCleaner(console=Console())
    nonexistent_file = Path("/nonexistent/file.py")
    code_cleaner.clean_file(nonexistent_file)


def test_remove_extra_whitespace_edge_cases() -> None:
    code_cleaner = CodeCleaner(console=Console())
    test_code = """

def function():
    x = 1

    return x
"""

    result = code_cleaner.remove_extra_whitespace(test_code)

    assert result.count("\n\n\n") == 0
    assert "def function():" in result
    assert "x = 1" in result
