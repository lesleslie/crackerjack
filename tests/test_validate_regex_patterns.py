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
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
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
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
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
