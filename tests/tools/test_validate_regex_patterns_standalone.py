import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


def _load_standalone_module() -> object:
    """Load the standalone validator by file path to avoid 'tools' name clashes."""
    root = Path(__file__).resolve().parents[2]
    mod_path = root / "tools" / "validate_regex_patterns_standalone.py"
    spec = spec_from_file_location("cj_tools.validate_regex_patterns_standalone", mod_path)
    assert spec and spec.loader, "Failed to build spec for standalone validator"
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load_standalone_module()
RegexVisitor = getattr(_mod, "RegexVisitor")
main = getattr(_mod, "main")
validate_file = getattr(_mod, "validate_file")


def write(tmpdir: Path, rel: str, content: str) -> Path:
    path = tmpdir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_validate_file_reports_raw_regex_usage(tmp_path: Path) -> None:
    # Raw regex usage without exemptions should be reported
    p = write(
        tmp_path,
        "pkg/module.py",
        """
import re

def f():
    return re.sub(r"foo", "bar", "foobar")
""",
    )

    issues = validate_file(p)
    assert issues, "Expected issues for raw regex usage"
    assert any("Raw regex usage" in msg for _, msg in issues)


def test_validate_file_allows_exempt_comment_and_allowed_paths(tmp_path: Path) -> None:
    # Exemption via inline comment
    p1 = write(
        tmp_path,
        "pkg/a.py",
        """
import re

def f():
    return re.search(r"foo", "foo")  # REGEX OK: unit test
""",
    )
    assert validate_file(p1) == []

    # Exemption via allowed file path pattern
    p2 = write(
        tmp_path,
        "crackerjack/services/regex_patterns.py",
        """
import re
X = re.compile(r"foo")
""",
    )
    assert validate_file(p2) == []


def test_validate_file_detects_bad_replacement_syntax(tmp_path: Path) -> None:
    # Detect incorrect replacement syntax using \g <1>
    p = write(
        tmp_path,
        "pkg/b.py",
        """
import re

def f(s: str) -> str:
    return re.sub(r"([ab])", "\\g <1>", s)
""",
    )

    issues = validate_file(p)
    assert any("Bad replacement syntax" in msg for _, msg in issues)


def test_main_returns_nonzero_and_prints_issues(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = write(
        tmp_path,
        "pkg/bad.py",
        """
import re
re.match(r"x", "x")
""",
    )

    code = main([str(bad)])
    out = capsys.readouterr().out

    assert code == 1
    assert "REGEX VALIDATION FAILED" in out
    assert str(bad) in out


def test_main_success_when_no_issues(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ok = write(
        tmp_path,
        "pkg/ok.py",
        """
def f():
    return "ok"
""",
    )

    code = main([str(ok)])
    out = capsys.readouterr().out

    assert code == 0
    assert "All regex patterns validated successfully" in out


def test_main_ignores_non_python_and_missing_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    txt = write(tmp_path, "pkg/readme.txt", "no python here")
    missing = tmp_path / "pkg/missing.py"

    code = main([str(txt), str(missing)])
    out = capsys.readouterr().out

    # No issues and success message when only ignored inputs are provided
    assert code == 0
    assert "All regex patterns validated successfully" in out
