from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.services.frontmatter_validator import (
    FrontmatterValidationError,
    FrontmatterValidationResult,
    FrontmatterValidator,
)


def test_validate_does_not_spawn_subprocess() -> None:
    """The wrapper must NOT spawn a subprocess when calling validate().

    Regression: the old wrapper spawned `python scripts/validate_document_frontmatter.py`
    as a subprocess. After the refactor, all validation happens in-process.

    Verification: the wrapper module no longer imports or references
    `secure_subprocess`; if the attribute is missing, the in-process path is
    the only one possible. We also exercise the in-process path against an
    empty repo to confirm validation runs without ever spawning a subprocess.
    """
    # The wrapper module must not even have a `secure_subprocess` attribute;
    # the refactor removed the subprocess path entirely.
    wrapper_module = __import__(
        "crackerjack.services.frontmatter_validator", fromlist=["secure_subprocess"]
    )
    assert not hasattr(wrapper_module, "secure_subprocess"), (
        "wrapper must not expose secure_subprocess; validation must be in-process"
    )

    v = FrontmatterValidator(pkg_path=Path("/tmp/repo"))
    with patch(
        "crackerjack.services.frontmatter.discover_files",
        return_value=[],
    ):
        result = v.validate()
    assert result.success is True


def test_validate_parses_clean_json(tmp_path: Path) -> None:
    """Clean validator run returns success with zero errors."""
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    v = FrontmatterValidator(pkg_path=tmp_path)
    result = v.validate()
    assert isinstance(result, FrontmatterValidationResult)
    assert result.success is True
    assert result.files_scanned == 0
    assert result.error_count == 0
    assert result.warning_count == 0


def test_validate_raises_on_errors(tmp_path: Path) -> None:
    """Bad frontmatter produces errors; validate_or_raise raises."""
    plans = tmp_path / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "bad.md").write_text(
        "---\nstatus: bogus\n---\n# Hi\n",
        encoding="utf-8",
    )
    v = FrontmatterValidator(pkg_path=tmp_path)
    with pytest.raises(FrontmatterValidationError) as exc_info:
        v.validate_or_raise()
    assert exc_info.value.result.error_count >= 1


def test_validate_crash_raises() -> None:
    """A crash during validator execution becomes FrontmatterValidationError(reason='crash')."""
    v = FrontmatterValidator(pkg_path=Path("/tmp/repo"))
    with patch(
        "crackerjack.services.frontmatter.discover_files",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(FrontmatterValidationError) as exc_info:
            v.validate()
    assert exc_info.value.reason == "crash"


def test_validate_passes_store_flag(tmp_path: Path) -> None:
    """The --store flag narrows the scan to a single store."""
    plans = tmp_path / "docs" / "plans"
    decisions = tmp_path / ".claude" / "decisions"
    plans.mkdir(parents=True)
    decisions.mkdir(parents=True)
    (plans / "a.md").write_text("# No frontmatter\n", encoding="utf-8")
    (decisions / "b.md").write_text("# Missing here too\n", encoding="utf-8")

    v = FrontmatterValidator(pkg_path=tmp_path)
    plans_only = v.validate(store="plans")
    assert plans_only.files_scanned == 1
    decisions_only = v.validate(store="decisions")
    assert decisions_only.files_scanned == 1


def test_validate_strict_promotes_warnings_to_failure(tmp_path: Path) -> None:
    """strict=True causes success=False when warnings exist."""
    plans = tmp_path / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "warny.md").write_text(
        "---\nstatus: draft\n---\n# Hi\n",
        encoding="utf-8",
    )
    v = FrontmatterValidator(pkg_path=tmp_path)
    lenient = v.validate(strict=False)
    strict = v.validate(strict=True)
    if lenient.warning_count > 0:
        assert strict.success is False
    if lenient.error_count > 0:
        assert lenient.success is False
        assert strict.success is False


def test_validate_allow_nonstandard_false_emits_missing_frontmatter(
    tmp_path: Path,
) -> None:
    """allow_nonstandard=False surfaces MISSING_FRONTMATTER errors."""
    plans = tmp_path / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "legacy.md").write_text("# No frontmatter\n", encoding="utf-8")
    v = FrontmatterValidator(pkg_path=tmp_path)
    result = v.validate(allow_nonstandard=False)
    assert result.success is False
    assert result.error_count >= 1
    codes = {e.code for e in result.errors}
    assert "MISSING_FRONTMATTER" in codes


def test_validate_in_process_real_file_with_status_field(tmp_path: Path) -> None:
    """A file with valid frontmatter validates cleanly via the in-process path."""
    plans = tmp_path / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "ok.md").write_text(
        "---\n"
        "status: draft\n"
        "role: implementation\n"
        "date: 2026-01-01\n"
        "last_reviewed: 2026-01-01\n"
        "topic: example-topic\n"
        "---\n"
        "# Hi\n",
        encoding="utf-8",
    )
    v = FrontmatterValidator(pkg_path=tmp_path)
    result = v.validate()
    assert result.success is True
    assert result.files_scanned == 1
