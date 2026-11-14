"""Unit tests for ``crackerjack.tools.ty_ignore_syntax``.

The tool rejects mypy/ruff ignore syntax. In a ty repo, ``# type: ignore``
suppresses nothing — ty does not interpret it — so a comment written that way
looks like a suppression to a reader while the diagnostic stays live.

Rule-name validity for ``# ty: ignore[<code>]`` is *not* checked here. ty
reports ``ignore-comment-unknown-rule`` and exits non-zero for a code it does
not know, which keeps this tool free of a rule registry that would need
updating on every ty rename.

These tests are deliberately self-contained: they read and write temporary
files and never reach into another repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.tools.ty_ignore_syntax import main, scan_file


def _scan(tmp_path: Path, body: str) -> list[tuple[int, str]]:
    target = tmp_path / "sample.py"
    target.write_text(body, encoding="utf-8")
    return scan_file(target)


def _messages(tmp_path: Path, body: str) -> list[str]:
    return [message for _, message in _scan(tmp_path, body)]


# ---------------------------------------------------------------------------
# Rejected: mypy/ruff ignore syntax
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("x = 1  # type: ignore\n", id="bare"),
        pytest.param("x = 1  # type: ignore[assignment]\n", id="mypy-code"),
        pytest.param(
            "x = 1  # type: ignore[attr-defined]\n",
            id="mypy-code-attr-defined",
        ),
        pytest.param(
            "x = 1  # type: ignore[misc, assignment, no-redef]\n",
            id="mypy-code-list",
        ),
        pytest.param("x = 1  # type: ignore[]\n", id="empty-code-list"),
    ],
)
def test_rejects_mypy_ignore_syntax(tmp_path: Path, body: str) -> None:
    """Every mypy-syntax directive is rejected, whatever code it names."""
    assert _messages(tmp_path, body), f"expected a finding for {body!r}"


def test_rejects_mypy_syntax_even_when_the_code_is_a_real_ty_rule(
    tmp_path: Path,
) -> None:
    """A ty code written in mypy syntax is still rejected.

    ``# type: ignore[missing-attribute]`` names a valid ty rule but uses the
    spelling ty does not read, so it suppresses nothing. It must be reported
    rather than waved through because the code happens to look familiar.
    """
    findings = _messages(
        tmp_path,
        "x = 1  # type: ignore[missing-attribute]\n",
    )
    assert findings
    assert "does not interpret it" in findings[0]


def test_bare_mypy_ignore_names_the_bare_form(tmp_path: Path) -> None:
    """The bare form gets its own message, not the generic one."""
    findings = _messages(tmp_path, "x = 1  # type: ignore\n")
    assert findings
    assert "bare" in findings[0]


# ---------------------------------------------------------------------------
# Rejected: both forms on one line
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            "x = 1  # type: ignore[attr-defined]  # ty: ignore[missing-attribute]\n",
            id="mypy-then-ty",
        ),
        pytest.param(
            "x = 1  # ty: ignore[missing-attribute]  # type: ignore[attr-defined]\n",
            id="ty-then-mypy",
        ),
        pytest.param(
            "x = 1  # type: ignore[assignment] # ty: ignore[invalid-assignment]\n",
            id="single-space",
        ),
    ],
)
def test_rejects_both_forms_on_one_line(tmp_path: Path, body: str) -> None:
    """A line carrying both spellings is reported once."""
    findings = _messages(tmp_path, body)
    assert len(findings) == 1
    assert "combines" in findings[0]


# ---------------------------------------------------------------------------
# Accepted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("x = 1  # ty: ignore[missing-attribute]\n", id="ty-with-code"),
        pytest.param("x = 1  # ty: ignore\n", id="ty-bare"),
        pytest.param(
            "x = 1  # ty: ignore[missing-attribute, invalid-argument-type]\n",
            id="ty-code-list",
        ),
        pytest.param("x = 1  # noqa: E501\n", id="ruff-noqa"),
        pytest.param("x = 1  # a comment mentioning ty: ignore in prose\n", id="prose"),
        pytest.param("x = 1\n", id="no-comment"),
    ],
)
def test_accepts_ty_syntax_and_unrelated_comments(
    tmp_path: Path,
    body: str,
) -> None:
    """``# ty: ignore[...]`` and unrelated comments produce no findings."""
    assert _messages(tmp_path, body) == []


def test_ignores_unknown_ty_rule_names(tmp_path: Path) -> None:
    """Rule-name validity belongs to ty, not to this tool.

    ty reports ``ignore-comment-unknown-rule`` for a code it does not know.
    This tool stays silent so the two never disagree about the same line.
    """
    assert _messages(tmp_path, "x = 1  # ty: ignore[not-a-real-rule]\n") == []


# ---------------------------------------------------------------------------
# Behaviour beyond a single line
# ---------------------------------------------------------------------------


def test_reports_the_line_number_of_each_finding(tmp_path: Path) -> None:
    body = "x = 1\ny = 2  # type: ignore[assignment]\nz = 3\n"
    findings = _scan(tmp_path, body)
    assert [line for line, _ in findings] == [2]


def test_reads_a_real_file(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("x = 1  # type: ignore[assignment]\n", encoding="utf-8")
    assert scan_file(target)


def test_missing_file_is_reported_not_raised(tmp_path: Path) -> None:
    findings = scan_file(tmp_path / "does-not-exist.py")
    assert findings
    assert "Could not read" in findings[0][1]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_main_exits_zero_when_clean(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("x = 1  # ty: ignore[missing-attribute]\n", encoding="utf-8")
    assert main([str(target)]) == 0


def test_main_exits_nonzero_when_dirty(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("x = 1  # type: ignore[assignment]\n", encoding="utf-8")
    assert main([str(target)]) == 1


def test_main_dry_run_always_exits_zero(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("x = 1  # type: ignore[assignment]\n", encoding="utf-8")
    assert main([str(target), "--dry-run"]) == 0


class TestDefaultScanPath:
    """The default must scan the repository root, not a fixed package name.

    The hook registers this tool with no path argument, so it uses the
    default. A default of ``crackerjack/`` — a directory that exists only in
    crackerjack itself — meant every other repo scanned zero files and
    passed. That is the same vacuous-gate shape already fixed in
    ``ty_ratchet``.
    """

    def test_default_path_scans_the_repo_root(self, tmp_path: Path) -> None:
        package = tmp_path / "pkg"
        tests = tmp_path / "tests"
        package.mkdir()
        tests.mkdir()
        (package / "mod.py").write_text(
            "x = 1  # type: ignore[assignment]\n", encoding="utf-8"
        )
        (tests / "test_mod.py").write_text(
            "y = 2  # type: ignore[assignment]\n", encoding="utf-8"
        )

        cwd = Path.cwd()
        try:
            import os

            os.chdir(tmp_path)
            assert main([]) == 1
        finally:
            import os

            os.chdir(cwd)

    def test_default_path_reports_the_files_it_scanned(self, tmp_path: Path) -> None:
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "mod.py").write_text(
            "x = 1  # ty: ignore[missing-attribute]\n", encoding="utf-8"
        )

        cwd = Path.cwd()
        try:
            import os

            os.chdir(tmp_path)
            assert main(["--json"]) == 0
        finally:
            import os

            os.chdir(cwd)

    def test_excluded_cache_directory_is_not_scanned(self, tmp_path: Path) -> None:
        """``.crackerjack/`` holds a vendored copy of the source."""
        cache = tmp_path / ".crackerjack" / "uv" / "cache"
        cache.mkdir(parents=True)
        (cache / "mod.py").write_text(
            "x = 1  # type: ignore[assignment]\n", encoding="utf-8"
        )

        cwd = Path.cwd()
        try:
            import os

            os.chdir(tmp_path)
            assert main([]) == 0
        finally:
            import os

            os.chdir(cwd)


class TestDocumentedDirectivesAreNotFindings:
    """A comment can write *about* a directive instead of using one.

    ``# ``# type: ignore[import-not-found]`` directive covers Mypy/Pyright``
    documents a directive. Reporting it would send a reader to fix a
    comment that is not broken.
    """

    def test_a_documented_directive_is_not_a_finding(self, tmp_path: Path) -> None:
        target = tmp_path / "sample.py"
        target.write_text(
            "# ``# type: ignore[import-not-found]`` directive covers Mypy/Pyright\n",
            encoding="utf-8",
        )
        assert scan_file(target) == []

    def test_a_documented_ty_directive_is_not_a_finding(self, tmp_path: Path) -> None:
        target = tmp_path / "sample.py"
        target.write_text(
            "# use ``# ty: ignore[missing-attribute]`` for that\n",
            encoding="utf-8",
        )
        assert scan_file(target) == []

    def test_a_real_directive_is_still_a_finding(self, tmp_path: Path) -> None:
        target = tmp_path / "sample.py"
        target.write_text("x = 1  # type: ignore[import-not-found]\n", encoding="utf-8")
        assert scan_file(target)
