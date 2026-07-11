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
    ValidationResult,
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


def test_validation_result_details_defaults_none():
    """Backward-compat: existing constructions don't need a details kwarg."""
    result = ValidationResult(passed=True)
    assert result.details is None


def test_validation_result_details_explicit_list():
    result = ValidationResult(
        passed=False,
        reason="x",
        details=["line1", "line2"],
    )
    assert result.details == ["line1", "line2"]


def test_output_validator_validate_passes_details_through(
    tmp_path, monkeypatch
):
    """The wrapper must not drop details; if any check fails with details,
    validate() must return a ValidationResult carrying those details."""
    captured_details: list[str] | None = None

    def fake_import_check(file_path: Path) -> ValidationResult:
        nonlocal captured_details
        return ValidationResult(
            passed=False,
            reason="fake failure",
            details=[
                "Traceback (most recent call last):",
                "  File \"fake.py\", line 1",
                "AttributeError: fake",
            ],
        )

    monkeypatch.setattr(
        "crackerjack.ai_fix.output_validator.import_check",
        fake_import_check,
    )

    fake_file = tmp_path / "fake.py"
    fake_file.write_text("x = 1\n")

    validator = OutputValidator()
    result = validator.validate(fake_file)

    assert result.passed is False
    assert result.details is not None
    assert "fake.py" in result.details[1]
    assert result.details[-1] == "AttributeError: fake"


def test_import_check_reason_unchanged_for_syntax_error(tmp_path):
    """Backward-compat: reason field must remain the last line of stderr."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def foo(:\n  pass\n")

    result = import_check(bad_file)

    assert result.passed is False
    assert result.reason
    assert "SyntaxError" in result.reason or "invalid syntax" in result.reason


def test_import_check_details_none_on_empty_stderr(tmp_path, monkeypatch):
    """If subprocess exits non-zero with empty stderr, details is None."""
    import subprocess
    fake_proc = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    def fake_run(*args, **kwargs):
        return fake_proc

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = import_check(tmp_path / "fake.py")

    assert result.passed is False
    assert result.details is None
    assert "import exit 1" in result.reason


def test_import_check_details_none_on_success(tmp_path):
    """When the file imports cleanly, details is None (no failure to capture)."""
    good_file = tmp_path / "ok.py"
    good_file.write_text("x = 1\n")

    result = import_check(good_file)

    assert result.passed is True
    assert result.details is None


def test_import_check_captures_full_traceback_for_top_level_none_dict(tmp_path):
    """Regression for Cluster 1: validator previously reported only the last
    line of stderr, hiding the actual crash frame. With details populated,
    the fixer can see which line raised AttributeError on None.__dict__."""
    bad_file = tmp_path / "crash.py"
    bad_file.write_text(
        "import os\n"
        "value = None\n"
        "value.__dict__  # NoneType has no __dict__\n"
    )

    result = import_check(bad_file)

    assert result.passed is False
    assert result.details is not None
    assert len(result.details) >= 3
    # The driver's stderr begins with the AttributeError message (from the
    # explicit print) followed by the traceback, so "Traceback" is not at
    # index 0. Spec criterion 3 requires details to *contain* the traceback
    # lines, not to be ordered a particular way.
    assert any("Traceback" in line for line in result.details)
    assert any("crash.py" in line for line in result.details)
    assert result.details[-1].startswith("AttributeError:")
    assert result.reason == result.details[-1]
