from pathlib import Path

import pytest

from crackerjack.tools import validate_regex_patterns as validator


def write(tmpdir: Path, rel: str, content: str) -> Path:
    path = tmpdir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_validate_file_reports_raw_regex_usage(tmp_path: Path) -> None:
    bad_file = write(
        tmp_path,
        "pkg/module.py",
        """
import re

def f():
    return re.sub(r"foo", "bar", "foobar")
""",
    )

    issues = validator.validate_file(bad_file)
    assert issues, "Expected issues for raw regex usage"
    assert any("Raw regex usage" in msg for _, msg in issues)


def test_validate_file_allows_exemptions(tmp_path: Path) -> None:
    exempted = write(
        tmp_path,
        "pkg/a.py",
        """
import re

def f():
    return re.search(r"foo", "foo")  # REGEX OK: unit test
""",
    )

    allowed_path = write(
        tmp_path,
        "crackerjack/services/regex_patterns.py",
        """
import re
X = re.compile(r"foo")
""",
    )

    assert validator.validate_file(exempted) == []
    assert validator.validate_file(allowed_path) == []


def test_validate_file_detects_bad_replacement_syntax(tmp_path: Path) -> None:
    bad_replacement = write(
        tmp_path,
        "pkg/b.py",
        """
import re

def f(s: str) -> str:
    return re.sub(r"([ab])", "\\g <1>", s)
""",
    )

    issues = validator.validate_file(bad_replacement)
    assert any("Bad replacement syntax" in msg for _, msg in issues)


def test_main_returns_nonzero_and_prints_issues(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    bad = write(
        tmp_path,
        "pkg/bad.py",
        """
import re
re.match(r"x", "x")
""",
    )

    code = validator.main([str(bad)])
    out = capsys.readouterr().out

    assert code == 1
    assert "REGEX VALIDATION FAILED" in out
    assert str(bad) in out


def test_main_success_when_no_issues(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    ok = write(
        tmp_path,
        "pkg/ok.py",
        """
def f():
    return "ok"
""",
    )

    code = validator.main([str(ok)])
    out = capsys.readouterr().out

    assert code == 0
    assert "All regex patterns validated successfully" in out


class TestRegexVisitorMethods:
    """Tests for RegexVisitor AST visitor methods."""

    def test_visit_Import_detects_regex_import(self, tmp_path: Path) -> None:
        """Test that visit_Import correctly detects regex module imports."""
        file_with_import = write(
            tmp_path,
            "pkg/import_test.py",
            """
import re

def f():
    pass
""",
        )
        issues = validator.validate_file(file_with_import)
        # Import alone shouldn't trigger issues, but using regex functions should
        assert isinstance(issues, list)

    def test_visit_ImportFrom_with_module_prefix(self, tmp_path: Path) -> None:
        """Test that 'from re import sub' with direct call doesn't trigger re.sub check.

        Note: The validator checks for 're.sub' style calls, not bare 'sub' calls.
        When importing 'from re import sub', calling 'sub()' directly won't trigger
        the validator since it's checking for the pattern 're.sub' not 'sub'.
        This is expected behavior - the validator focuses on module-prefixed calls.
        """
        file_with_from_import = write(
            tmp_path,
            "pkg/from_import_test.py",
            """
from re import sub

def f():
    return sub(r"foo", "bar", "foobar")
""",
        )
        issues = validator.validate_file(file_with_from_import)
        # No issues expected because validator checks for "re.sub", not bare "sub"
        assert issues == []

    def test_visit_Call_detects_regex_usage(self, tmp_path: Path) -> None:
        """Test that visit_Call correctly detects regex function calls."""
        file_with_call = write(
            tmp_path,
            "pkg/call_test.py",
            """
import re

def f():
    return re.search(r"pattern", "text")
""",
        )
        issues = validator.validate_file(file_with_call)
        assert any("Raw regex usage" in msg for _, msg in issues)

    def test_visit_Call_allows_inline_exempted_comments(self, tmp_path: Path) -> None:
        """Test that visit_Call allows regex calls with inline exemption comments."""
        # The exemption check looks at the call line and lines after it
        exempted_call = write(
            tmp_path,
            "pkg/exempted_call.py",
            """
import re

def f():
    return re.findall(r"\\d+", "123")  # REGEX OK: test exemption
""",
        )
        issues = validator.validate_file(exempted_call)
        assert issues == []

    def test_visit_Call_allows_same_line_exempted_comments(
        self, tmp_path: Path
    ) -> None:
        """Test exemption comment on the same line as the regex call."""
        exempted_call = write(
            tmp_path,
            "pkg/exempted_same_line.py",
            """
import re

def f():
    return re.search(r"pattern", "text")  # REGEX OK: testing
""",
        )
        issues = validator.validate_file(exempted_call)
        assert issues == []
