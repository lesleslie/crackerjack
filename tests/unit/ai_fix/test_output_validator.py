"""Tests for the post-fix output validator.

The validator is the gatekeeper between an AI fix and the working
tree. It runs three checks in order:

1. **Syntax check** — ``compile()`` rejects broken Python before the
   fix can land. Already implemented in the coordinator's syntax
   gate; we re-test the gate here for end-to-end coverage.
2. **Import check** — ``python -c "import <module>"`` in a subprocess
   catches ``ImportError`` / ``NameError`` / ``SyntaxError`` that
   ``compile()`` missed (e.g. forward references resolved at import
   time, missing third-party modules).
3. **Ruff sanity** — ``ruff check --select=E9,F63,F7,F82`` catches
   runtime errors (``E9``), undefined names (``F821``), and similar
   issues that import cannot.

A failed check returns a ``ValidationResult(passed=False, reason=...)``
so the caller can roll back the working tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.ai_fix.output_validator import (
    OutputValidator,
    import_check,
    ruff_sanity_check,
    syntax_check,
)


class TestSyntaxCheck:
    """The ``compile()`` gate — already proven in the coordinator tests,
    but tested here for the public module-level helper."""

    def test_syntax_check_passes_valid_python(self, tmp_path: Path) -> None:
        py = tmp_path / "good.py"
        py.write_text("value = 1\n", encoding="utf-8")
        result = syntax_check(py)
        assert result.passed is True
        assert result.reason == ""

    def test_syntax_check_fails_broken_python(self, tmp_path: Path) -> None:
        py = tmp_path / "bad.py"
        py.write_text("def broken(:\n", encoding="utf-8")
        result = syntax_check(py)
        assert result.passed is False
        assert "syntax" in result.reason.lower()

    def test_syntax_check_skips_non_python(self, tmp_path: Path) -> None:
        md = tmp_path / "README.md"
        md.write_text("# Hello\n", encoding="utf-8")
        result = syntax_check(md)
        assert result.passed is True
        assert result.skipped is True


class TestImportCheck:
    """The import-safety gate — runs ``python -c "import <module>"``.

    This catches errors that ``compile()`` doesn't, e.g. a fix that
    deletes a needed import or mistypes a module name. The check
    runs the import in a subprocess with a 30s timeout so a broken
    fix can't hang the coordinator.
    """

    def test_import_check_passes_valid_module(self, tmp_path: Path) -> None:
        """A syntactically-valid, importable module passes."""
        py = tmp_path / "good.py"
        py.write_text("value = 1\n", encoding="utf-8")
        result = import_check(py)
        assert result.passed is True
        assert result.reason == ""

    def test_import_check_fails_on_import_error(self, tmp_path: Path) -> None:
        """A module that raises ``ImportError`` at import time is rejected."""
        py = tmp_path / "broken.py"
        # ``import notarealpackage`` triggers a real ``ModuleNotFoundError``,
        # which is a subclass of ``ImportError``. ``from __future__ import
        # notarealmodule`` would be a SyntaxError instead, so we deliberately
        # don't use that pattern.
        py.write_text("import notarealpackage_xyz123\n", encoding="utf-8")
        result = import_check(py)
        assert result.passed is False
        assert "import" in result.reason.lower() or "module" in result.reason.lower()

    def test_import_check_fails_on_name_error(self, tmp_path: Path) -> None:
        """A module that references an undefined name at import time is rejected."""
        py = tmp_path / "name_err.py"
        py.write_text("print(does_not_exist)\n", encoding="utf-8")
        result = import_check(py)
        assert result.passed is False
        assert "name" in result.reason.lower() or "error" in result.reason.lower()

    def test_import_check_skips_non_python(self, tmp_path: Path) -> None:
        md = tmp_path / "README.md"
        md.write_text("# Hello\n", encoding="utf-8")
        result = import_check(md)
        assert result.passed is True
        assert result.skipped is True


class TestRuffSanityCheck:
    """The ruff sanity gate — runs ``ruff check --no-fix --select=E9,F63,F7,F82``.

    These rule codes target runtime / import-time issues that
    ``compile()`` and the import check can both miss in edge cases.
    E9 = runtime errors; F63 = import problems; F7 = logic bugs that
    are likely runtime errors; F82 = undefined name (duplicate of
    the import check but tighter).
    """

    def test_ruff_sanity_passes_clean_code(self, tmp_path: Path) -> None:
        py = tmp_path / "clean.py"
        py.write_text("x = 1\n", encoding="utf-8")
        result = ruff_sanity_check(py)
        assert result.passed is True
        assert result.reason == ""

    def test_ruff_sanity_fails_undefined_name(self, tmp_path: Path) -> None:
        """An F821 (undefined name) is caught by ruff."""
        py = tmp_path / "undef.py"
        py.write_text("print(does_not_exist)\n", encoding="utf-8")
        result = ruff_sanity_check(py)
        # Ruff might not be installed; if so, the check is skipped.
        if result.skipped:
            pytest.skip("ruff not installed")
        assert result.passed is False
        assert "ruff" in result.reason.lower() or "f821" in result.reason.lower()

    def test_ruff_sanity_skips_non_python(self, tmp_path: Path) -> None:
        md = tmp_path / "README.md"
        md.write_text("# Hello\n", encoding="utf-8")
        result = ruff_sanity_check(md)
        assert result.passed is True
        assert result.skipped is True

    def test_ruff_sanity_skipped_when_ruff_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If ruff is not on PATH, the check is skipped (not failed).

        We don't want the validator to hard-fail on environments
        that haven't installed ruff; the import check still catches
        the most common failure modes.
        """
        # Pretend ruff is missing by pointing PATH at an empty dir.
        empty = tmp_path / "empty_bin"
        empty.mkdir()
        monkeypatch.setenv("PATH", str(empty))
        py = tmp_path / "anything.py"
        py.write_text("x = 1\n", encoding="utf-8")
        result = ruff_sanity_check(py)
        assert result.passed is True
        assert result.skipped is True


class TestOutputValidator:
    """The combined validator — runs all checks, returns first failure."""

    def test_combined_passes_valid_file(self, tmp_path: Path) -> None:
        py = tmp_path / "ok.py"
        py.write_text("x = 1\n", encoding="utf-8")
        validator = OutputValidator()
        result = validator.validate(py)
        assert result.passed is True

    def test_combined_fails_on_syntax_error_first(self, tmp_path: Path) -> None:
        """Syntax errors short-circuit the chain (no point running import)."""
        py = tmp_path / "broken.py"
        py.write_text("def x(:\n", encoding="utf-8")
        validator = OutputValidator()
        result = validator.validate(py)
        assert result.passed is False
        assert "syntax" in result.reason.lower()

    def test_combined_fails_on_import_error_after_syntax_passes(
        self, tmp_path: Path
    ) -> None:
        """If syntax is fine but import fails, the import check catches it."""
        py = tmp_path / "import_err.py"
        py.write_text("import notarealpackage_xyz123\n", encoding="utf-8")
        validator = OutputValidator()
        result = validator.validate(py)
        assert result.passed is False
        assert "import" in result.reason.lower() or "module" in result.reason.lower()

    def test_validator_is_chainable(self, tmp_path: Path) -> None:
        """``OutputValidator()`` constructs without args."""
        v = OutputValidator()
        assert v is not None
