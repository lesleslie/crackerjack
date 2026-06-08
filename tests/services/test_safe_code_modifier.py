"""Tests for `crackerjack.services.safe_code_modifier`.

Covers the AST-based source editing helpers: backup/rollback, validation
(syntax + ruff quality), change application, and dataclass behaviour.

Subprocess calls (`ruff format`, `ruff check`) are mocked at the boundary
because ruff is a dev-tool, not a runtime dependency of the modifier.
"""

from __future__ import annotations

import os
import subprocess
import typing as t
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.services.safe_code_modifier import (
    BackupMetadata,
    SafeCodeModifier,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_modifier(tmp_path: Path) -> SafeCodeModifier:
    """Build a SafeCodeModifier with a MagicMock console."""
    return SafeCodeModifier(
        console=MagicMock(),
        project_path=tmp_path,
        max_backups=3,
    )


def _completed_proc(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a fake CompletedProcess-like object for subprocess.run."""
    cp = MagicMock()
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


# ---------------------------------------------------------------------------
# Dataclass behaviour
# ---------------------------------------------------------------------------


class TestValidationSeverity:
    def test_values(self) -> None:
        assert ValidationSeverity.ERROR == "error"
        assert ValidationSeverity.WARNING == "warning"
        assert ValidationSeverity.INFO == "info"


class TestValidationResult:
    def test_errors_filters_by_severity(self) -> None:
        result = ValidationResult(
            success=False,
            issues=[
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="boom",
                    file_path=Path("/tmp/x.py"),
                ),
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="careful",
                    file_path=Path("/tmp/x.py"),
                ),
            ],
        )

        assert len(result.errors) == 1
        assert result.errors[0].message == "boom"

    def test_warnings_filters_by_severity(self) -> None:
        result = ValidationResult(
            success=True,
            issues=[
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="boom",
                    file_path=Path("/tmp/x.py"),
                ),
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="careful",
                    file_path=Path("/tmp/x.py"),
                ),
            ],
        )

        assert len(result.warnings) == 1
        assert result.warnings[0].message == "careful"

    def test_empty_issues(self) -> None:
        result = ValidationResult(success=True)
        assert result.errors == []
        assert result.warnings == []

    def test_default_factory_provides_new_list(self) -> None:
        # Two instances should not share the same default list.
        a = ValidationResult(success=True)
        b = ValidationResult(success=True)
        a.issues.append(
            ValidationIssue(
                severity=ValidationSeverity.INFO,
                message="x",
                file_path=Path("/tmp"),
            )
        )
        assert b.issues == []


class TestBackupMetadata:
    def test_construction(self) -> None:
        ts = datetime(2026, 1, 2, 3, 4, 5)
        meta = BackupMetadata(
            original_path=Path("/tmp/a.py"),
            backup_path=Path("/tmp/a.bak.py"),
            timestamp=ts,
            hash="abc123",
            size=10,
            sequence=1,
        )
        assert meta.original_path == Path("/tmp/a.py")
        assert meta.backup_path == Path("/tmp/a.bak.py")
        assert meta.timestamp == ts
        assert meta.hash == "abc123"
        assert meta.size == 10
        assert meta.sequence == 1


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestSafeCodeModifierInit:
    def test_init_stores_paths_and_sequences(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        assert mod.project_path == tmp_path
        assert mod.max_backups == 3
        assert mod._backup_sequences == {}


# ---------------------------------------------------------------------------
# _backup_file
# ---------------------------------------------------------------------------


class TestBackupFile:
    async def test_creates_backup_with_expected_name(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "hello.py"
        target.write_text("print('hi')")

        meta = await mod._backup_file(target)

        assert meta is not None
        assert meta.original_path == target
        assert meta.hash  # non-empty
        assert meta.size == len("print('hi')")
        assert meta.sequence == 1
        # backup should live next to the original with .bak.<ts>.<seq>.py
        assert meta.backup_path.parent == target.parent
        assert meta.backup_path.stem.startswith("hello.bak.")
        assert meta.backup_path.suffix == ".py"
        assert meta.backup_path.read_text() == "print('hi')"
        # Permission should be 0o600 (owner-only)
        mode = meta.backup_path.stat().st_mode & 0o777
        assert mode == 0o600

    async def test_sequence_increments_per_file(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("a")
        b.write_text("b")

        m_a = await mod._backup_file(a)
        m_a2 = await mod._backup_file(a)
        m_b = await mod._backup_file(b)

        assert m_a is not None and m_a2 is not None and m_b is not None
        assert m_a.sequence == 1
        assert m_a2.sequence == 2
        assert m_b.sequence == 1

    async def test_lock_is_cached_per_path(self, tmp_path: Path) -> None:
        from crackerjack.services import safe_code_modifier as scm

        scm._backup_locks.clear()
        mod = _make_modifier(tmp_path)
        target = tmp_path / "c.py"
        target.write_text("c")

        await mod._backup_file(target)
        first_lock = scm._backup_locks.get(target)
        assert first_lock is not None

        await mod._backup_file(target)
        second_lock = scm._backup_locks.get(target)
        # Same lock reused for the same path
        assert first_lock is second_lock

    async def test_returns_none_on_failure(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        nonexistent = tmp_path / "nope.py"

        with patch(
            "crackerjack.services.async_file_io.async_read_file",
            side_effect=FileNotFoundError("missing"),
        ):
            result = await mod._backup_file(nonexistent)

        assert result is None


# ---------------------------------------------------------------------------
# _apply_changes
# ---------------------------------------------------------------------------


class TestApplyChanges:
    async def test_replaces_known_string_in_file(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("hello world\n")

        result = await mod._apply_changes(
            target, [("hello", "goodbye")]
        )

        assert result == "goodbye world\n"
        # on-disk content also updated
        assert target.read_text() == "goodbye world\n"

    async def test_raises_when_old_string_missing(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("abc")

        with pytest.raises(ValueError, match="Could not find old string"):
            await mod._apply_changes(target, [("xyz", "123")])

    async def test_idempotent_when_already_replaced(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("foo bar")

        # First call replaces foo with baz.
        out1 = await mod._apply_changes(target, [("foo", "baz")])
        assert out1 == "baz bar"

        # Second call (no old string present) should raise.
        with pytest.raises(ValueError):
            await mod._apply_changes(target, [("foo", "baz")])

    async def test_python_files_trigger_ruff_format(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x=1\n")

        with patch(
            "subprocess.run", return_value=_completed_proc(0)
        ) as run_mock:
            await mod._apply_changes(target, [("x=1", "x = 1")])

        # ruff format was invoked at least once
        assert any(
            call.args and call.args[0][:1] == ["ruff"]
            and "format" in call.args[0]
            for call in run_mock.call_args_list
        )

    async def test_ruff_format_nonzero_returncode_does_not_raise(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x=1\n")

        with patch(
            "subprocess.run",
            return_value=_completed_proc(1, stderr="bad format"),
        ):
            # Should not raise despite ruff format failure
            result = await mod._apply_changes(target, [("x=1", "x = 1")])

        assert "x = 1" in result

    async def test_ruff_format_exception_does_not_raise(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x=1\n")

        with patch(
            "subprocess.run",
            side_effect=FileNotFoundError("ruff not installed"),
        ):
            result = await mod._apply_changes(target, [("x=1", "x = 1")])

        assert "x = 1" in result

    async def test_non_python_files_skip_ruff(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.md"
        target.write_text("hello world\n")

        with patch("subprocess.run") as run_mock:
            result = await mod._apply_changes(target, [("hello", "bye")])

        assert result == "bye world\n"
        run_mock.assert_not_called()


# ---------------------------------------------------------------------------
# _validate_syntax / _validate_changes / _validate_quality
# ---------------------------------------------------------------------------


class TestValidateSyntax:
    async def test_valid_python_succeeds(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "ok.py"

        result = await mod._validate_syntax(target, "x = 1\n")

        assert result.success is True
        assert result.issues == []

    async def test_invalid_python_records_syntax_error(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "bad.py"

        result = await mod._validate_syntax(target, "def ::\n")

        assert result.success is False
        assert len(result.issues) == 1
        issue = result.issues[0]
        assert issue.severity == ValidationSeverity.ERROR
        assert "Syntax error" in issue.message
        assert issue.file_path == target


class TestValidateQuality:
    async def test_ruff_clean_returns_no_issues(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x = 1")

        with patch(
            "subprocess.run", return_value=_completed_proc(0)
        ):
            result = await mod._validate_quality(target)

        assert result.success is True
        assert result.issues == []

    async def test_ruff_findings_become_warnings(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x = 1")

        ruff_output = f"{target}:1:1: F401 unused import\n"
        with patch(
            "subprocess.run",
            return_value=_completed_proc(1, stdout=ruff_output),
        ):
            result = await mod._validate_quality(target)

        assert result.success is True  # ruff findings are warnings, not errors
        assert len(result.issues) == 1
        assert result.issues[0].severity == ValidationSeverity.WARNING
        assert "F401" in result.issues[0].message

    async def test_ruff_timeout_does_not_raise(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x = 1")

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ruff", timeout=30),
        ):
            result = await mod._validate_quality(target)

        assert result.success is True
        assert result.issues == []

    async def test_ruff_not_installed_is_silent(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x = 1")

        with patch(
            "subprocess.run",
            side_effect=FileNotFoundError("ruff"),
        ):
            result = await mod._validate_quality(target)

        assert result.success is True
        assert result.issues == []

    async def test_malformed_ruff_lines_are_skipped(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x = 1")

        # Mix malformed + well-formed lines; the well-formed should be reported
        # and the malformed skipped.
        ruff_output = (
            f"junk line\n"
            f"{target}:notanumber:1: F401 unused\n"
            f"{target}:2:3: E501 line too long\n"
        )
        with patch(
            "subprocess.run",
            return_value=_completed_proc(1, stdout=ruff_output),
        ):
            result = await mod._validate_quality(target)

        # Only the parseable line should be reported
        assert len(result.issues) == 1
        assert result.issues[0].line_number == 2
        assert "E501" in result.issues[0].message


class TestValidateChanges:
    async def test_syntax_error_short_circuits_before_quality(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("def ::\n")

        # If we got to ruff, subprocess.run would be invoked. It should NOT
        # be invoked because syntax check fails first.
        with patch("subprocess.run") as run_mock:
            result = await mod._validate_changes(target, "def ::\n")

        assert result.success is False
        run_mock.assert_not_called()
        assert any(
            i.severity == ValidationSeverity.ERROR for i in result.issues
        )


# ---------------------------------------------------------------------------
# _rollback_file
# ---------------------------------------------------------------------------


class TestRollbackFile:
    async def test_rollback_restores_backup_content(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("ORIGINAL")
        backup = tmp_path / "x.py.bak"
        backup.write_text("ORIGINAL")

        meta = BackupMetadata(
            original_path=target,
            backup_path=backup,
            timestamp=datetime.now(),
            hash="hash",
            size=len("ORIGINAL"),
            sequence=1,
        )
        # Mutate target so rollback is meaningful
        target.write_text("MUTATED")

        ok = await mod._rollback_file(target, meta)

        assert ok is True
        assert target.read_text() == "ORIGINAL"

    async def test_rollback_returns_false_when_backup_missing(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        meta = BackupMetadata(
            original_path=target,
            backup_path=tmp_path / "missing.bak",
            timestamp=datetime.now(),
            hash="hash",
            size=0,
            sequence=1,
        )

        ok = await mod._rollback_file(target, meta)

        assert ok is False

    async def test_rollback_returns_false_on_copy_error(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        backup = tmp_path / "x.py.bak"
        backup.write_text("ORIGINAL")

        meta = BackupMetadata(
            original_path=target,
            backup_path=backup,
            timestamp=datetime.now(),
            hash="hash",
            size=8,
            sequence=1,
        )

        with patch(
            "shutil.copy2",
            side_effect=PermissionError("nope"),
        ):
            ok = await mod._rollback_file(target, meta)

        assert ok is False


# ---------------------------------------------------------------------------
# _cleanup_old_backups
# ---------------------------------------------------------------------------


class TestCleanupOldBackups:
    async def test_keeps_max_backups_and_removes_rest(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "f.py"
        target.write_text("now")

        # Create 5 backup files with explicit mtimes so ordering is deterministic
        for i in range(5):
            p = tmp_path / f"f.bak.20260101_0000{i}.{i}.py"
            p.write_text(f"v{i}")
            ts = (1_700_000_000 + i)
            os.utime(p, (ts, ts))

        await mod._cleanup_old_backups(target)

        remaining = sorted(tmp_path.glob("f.bak.*.py"))
        # max_backups=3 → 3 remain
        assert len(remaining) == 3
        # The two oldest should be removed (mtime-ordered desc, take top 3)
        contents = {p.read_text() for p in remaining}
        assert "v2" in contents
        assert "v3" in contents
        assert "v4" in contents

    async def test_no_backup_files_is_noop(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "missing.py"

        # Should not raise even with no matching files
        await mod._cleanup_old_backups(target)


# ---------------------------------------------------------------------------
# apply_changes_with_validation
# ---------------------------------------------------------------------------


class TestApplyChangesWithValidation:
    async def test_happy_path_returns_true(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("foo")

        with patch("subprocess.run", return_value=_completed_proc(0)):
            ok = await mod.apply_changes_with_validation(
                target, [("foo", "bar")], context="rename foo to bar"
            )

        assert ok is True
        assert target.read_text() == "bar"
        # A backup was created
        assert any(target.parent.glob("x.bak.*.py"))

    async def test_rollback_when_apply_raises(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("foo")

        with patch.object(
            mod,
            "_apply_changes",
            side_effect=RuntimeError("boom"),
        ):
            ok = await mod.apply_changes_with_validation(
                target, [("foo", "bar")], context="ctx"
            )

        assert ok is False
        # File should be rolled back to original "foo"
        assert target.read_text() == "foo"

    async def test_rollback_when_validation_fails(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("foo")

        with patch(
            "crackerjack.services.safe_code_modifier.SafeCodeModifier._validate_changes",
            return_value=ValidationResult(
                success=False,
                issues=[
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        message="nope",
                        file_path=target,
                    )
                ],
            ),
        ):
            ok = await mod.apply_changes_with_validation(
                target, [("foo", "bar")], context="ctx"
            )

        assert ok is False
        # Rollback should restore original
        assert target.read_text() == "foo"

    async def test_rollback_when_smoke_test_fails(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("foo")

        async def fake_smoke(_cmd: list[str]) -> bool:
            return False

        # _run_smoke_test is referenced but not defined in the source — use
        # create=True to install it for the duration of the test.
        with patch.object(
            mod, "_validate_changes", return_value=ValidationResult(success=True)
        ), patch.object(
            mod, "_run_smoke_test", side_effect=fake_smoke, create=True
        ):
            ok = await mod.apply_changes_with_validation(
                target,
                [("foo", "bar")],
                context="ctx",
                smoke_test_cmd=["true"],
            )

        assert ok is False
        # Rollback should restore original
        assert target.read_text() == "foo"

    async def test_returns_false_when_backup_fails(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("foo")

        with patch.object(
            mod, "_backup_file", return_value=None
        ):
            ok = await mod.apply_changes_with_validation(
                target, [("foo", "bar")], context="ctx"
            )

        assert ok is False


# ---------------------------------------------------------------------------
# apply_content_with_validation
# ---------------------------------------------------------------------------


class TestApplyContentWithValidation:
    async def test_writes_new_content(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("old")

        with patch("subprocess.run", return_value=_completed_proc(0)):
            ok = await mod.apply_content_with_validation(
                target, "x = 1\n", context="rewrite"
            )

        assert ok is True
        assert target.read_text() == "x = 1\n"

    async def test_rollback_on_syntax_error(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("original")

        ok = await mod.apply_content_with_validation(
            target, "def ::\n", context="bad"
        )

        assert ok is False
        # Rollback should restore original
        assert target.read_text() == "original"

    async def test_rollback_on_write_failure(self, tmp_path: Path) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("original")

        with patch(
            "crackerjack.services.async_file_io.async_write_file",
            side_effect=PermissionError("nope"),
        ):
            ok = await mod.apply_content_with_validation(
                target, "x = 1", context="ctx"
            )

        assert ok is False
        assert target.read_text() == "original"

    async def test_smoke_test_failure_rolls_back(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("original")

        async def fake_smoke(_cmd: list[str]) -> bool:
            return False

        with patch.object(
            mod, "_run_smoke_test", side_effect=fake_smoke, create=True
        ):
            ok = await mod.apply_content_with_validation(
                target,
                "x = 1",
                context="ctx",
                smoke_test_cmd=["true"],
            )

        assert ok is False
        assert target.read_text() == "original"

    async def test_warnings_are_surfaced_but_written(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("original")

        warnings = [
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=f"w{i}",
                file_path=target,
            )
            for i in range(5)
        ]
        with patch.object(
            mod,
            "_validate_changes",
            return_value=ValidationResult(success=True, issues=warnings),
        ):
            ok = await mod.apply_content_with_validation(
                target, "x = 1", context="ctx"
            )

        # Warnings don't block; change is applied
        assert ok is True
        assert target.read_text() == "x = 1"
        # But warnings should have been printed (capped at 3)
        printed = " ".join(
            str(c.args[0]) for c in mod.console.print.call_args_list
        )
        assert "warnings" in printed

    async def test_returns_false_when_backup_fails(
        self, tmp_path: Path
    ) -> None:
        mod = _make_modifier(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("original")

        with patch.object(mod, "_backup_file", return_value=None):
            ok = await mod.apply_content_with_validation(
                target, "x = 1", context="ctx"
            )

        assert ok is False


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------


class TestModuleExports:
    def test_all_exports(self) -> None:
        from crackerjack.services import safe_code_modifier as scm

        assert set(scm.__all__) == {
            "SafeCodeModifier",
            "BackupMetadata",
            "ValidationResult",
            "ValidationIssue",
            "ValidationSeverity",
        }
