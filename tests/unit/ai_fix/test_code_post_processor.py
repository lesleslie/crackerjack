"""Test the wrap_long_lines post-processor."""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

from crackerjack.ai_fix.code_post_processor import wrap_long_lines

SHORT_CODE = "x = 1\ny = 2\nz = 3\n"
LONG_LINE_CODE = "very_long_variable_name = " + ("'a' + ") * 20 + "'end'\n"


def test_wrap_short_code_unchanged() -> None:
    assert wrap_long_lines(SHORT_CODE) == SHORT_CODE


def test_wrap_simple_long_line() -> None:
    result = wrap_long_lines(LONG_LINE_CODE)
    assert all(len(line) <= 88 for line in result.splitlines())
    ast.parse(result)


def test_wrap_multiple_long_lines() -> None:
    code = LONG_LINE_CODE + LONG_LINE_CODE + LONG_LINE_CODE
    result = wrap_long_lines(code)
    assert all(len(line) <= 88 for line in result.splitlines())
    ast.parse(result)


def test_wrap_mixed_long_and_short() -> None:
    code = SHORT_CODE + LONG_LINE_CODE + SHORT_CODE
    result = wrap_long_lines(code)
    # Short lines preserved as-is
    assert "x = 1" in result
    assert "y = 2" in result
    # Long line wrapped
    assert all(len(line) <= 88 for line in result.splitlines())


def test_wrap_ruff_unavailable_returns_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "crackerjack.ai_fix.code_post_processor.shutil.which",
        lambda _: None,
    )
    assert wrap_long_lines(LONG_LINE_CODE) == LONG_LINE_CODE


def test_wrap_non_python_file_path_unchanged() -> None:
    result = wrap_long_lines(LONG_LINE_CODE, file_path=Path("foo.md"))
    assert result == LONG_LINE_CODE


def test_wrap_preserves_semantics() -> None:
    code = (
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
        + LONG_LINE_CODE
    )
    result = wrap_long_lines(code)
    ast.parse(result)


def test_wrap_respects_max_length_parameter() -> None:
    result = wrap_long_lines(LONG_LINE_CODE, max_length=50)
    assert all(len(line) <= 50 for line in result.splitlines())


def test_write_file_content_wraps_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Integration: AgentContext.write_file_content wraps Python files."""
    from crackerjack.agents.base import AgentContext

    # Ensure ruff is on PATH; if not, skip
    if shutil.which("ruff") is None:
        pytest.skip("ruff not on PATH")

    ctx = AgentContext(project_path=tmp_path)
    py_file = tmp_path / "module.py"
    ctx.write_file_content(py_file, LONG_LINE_CODE)

    written = py_file.read_text()
    assert all(len(line) <= 88 for line in written.splitlines())
