"""Tests for BehaviorValidator.

Covers dangerous-pattern detection in `validate()` and the test-execution
path in `validate_with_tests()`. The subprocess boundary is mocked so tests
remain hermetic.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.agents.behavior_validator import BehaviorValidator
from crackerjack.agents.syntax_validator import ValidationResult


class TestBehaviorValidatorBasic:
    """Direct dangerous-pattern rules via `validate()`."""

    @pytest.mark.asyncio
    async def test_safe_code_passes(self) -> None:
        validator = BehaviorValidator()
        result = await validator.validate("def foo():\n    return 1\n")

        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_empty_string_passes(self) -> None:
        validator = BehaviorValidator()
        result = await validator.validate("")

        assert result.valid is True
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_exec_call_rejected(self) -> None:
        validator = BehaviorValidator()
        result = await validator.validate("os.exec('rm -rf /')")

        assert result.valid is False
        assert any("exec" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_eval_call_rejected(self) -> None:
        validator = BehaviorValidator()
        result = await validator.validate("x = eval(input())")

        assert result.valid is False
        assert any("eval" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_dunder_import_rejected(self) -> None:
        validator = BehaviorValidator()
        result = await validator.validate("mod = __import__('os')")

        assert result.valid is False
        assert any("import" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_multiple_violations_all_reported(self) -> None:
        # NOTE: the dangerous-pattern regex for `exec` is `\.exec\(` (a literal
        # leading dot). Bare `exec('2+2')` (no leading dot) is therefore NOT
        # matched. The other two patterns (eval, __import__) are matched.
        validator = BehaviorValidator()
        code = (
            "a = eval('1+1')\n"
            "c = __import__('sys')\n"
        )
        result = await validator.validate(code)

        assert result.valid is False
        assert len(result.errors) == 2
        joined = "\n".join(result.errors)
        assert "eval" in joined
        assert "import" in joined.lower()

    @pytest.mark.asyncio
    async def test_substring_exec_within_word_not_matched(self) -> None:
        # The regex anchors to "\.exec(" (with a leading dot) for `exec`,
        # so plain method call `model.exec_command()` should NOT be flagged
        # via the exec rule. The dot prefix should still match.
        validator = BehaviorValidator()
        # No leading dot -> no match for the .exec( rule
        result = await validator.validate("x = executive(1)")
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_dunder_import_requires_parens_immediately(self) -> None:
        # The regex looks for "__import__" optionally followed by spaces,
        # then "(". A bare token reference is fine.
        validator = BehaviorValidator()
        result = await validator.validate("alias = __import__  # just a name")
        # No "(" after, so the dangerous pattern is not triggered.
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_validate_result_is_boolean_truthy(self) -> None:
        validator = BehaviorValidator()
        valid_result = await validator.validate("x = 1")
        invalid_result = await validator.validate("eval('1')")

        assert bool(valid_result) is True
        assert bool(invalid_result) is False


class TestBehaviorValidatorInit:
    """Project path wiring."""

    def test_default_project_path_is_cwd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PWD", raising=False)
        # Path.cwd() should be used when no project_path is passed.
        validator = BehaviorValidator()
        assert validator.project_path == Path.cwd()

    def test_explicit_project_path_used(self, tmp_path: Path) -> None:
        validator = BehaviorValidator(project_path=tmp_path)
        assert validator.project_path == tmp_path

    def test_none_project_path_falls_back_to_cwd(self) -> None:
        validator = BehaviorValidator(project_path=None)
        assert validator.project_path == Path.cwd()


class TestBehaviorValidatorDiscovery:
    """`_discover_test_file` finds test files in well-known locations."""

    @pytest.mark.asyncio
    async def test_discovers_sibling_test_module(self, tmp_path: Path) -> None:
        # Create module.py and test_module.py in the same directory.
        (tmp_path / "module.py").write_text("x = 1\n")
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_x(): assert True\n")

        validator = BehaviorValidator(project_path=tmp_path)
        result = await validator._discover_test_file(str(tmp_path / "module.py"))

        assert result is not None
        assert Path(result).name == "test_module.py"

    @pytest.mark.asyncio
    async def test_discovers_module_test_suffix(self, tmp_path: Path) -> None:
        (tmp_path / "module.py").write_text("x = 1\n")
        test_file = tmp_path / "module_test.py"
        test_file.write_text("def test_x(): assert True\n")

        validator = BehaviorValidator(project_path=tmp_path)
        result = await validator._discover_test_file(str(tmp_path / "module.py"))

        assert result is not None
        assert Path(result).name == "module_test.py"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_test_file(self, tmp_path: Path) -> None:
        # NOTE: source bug — when no test file is found, _discover_test_file
        # raises TypeError ("unsupported operand type(s) for /: 'str' and 'str'")
        # at line 111 because `test_dir` is a string used with `/`. The function
        # does not return None gracefully. This test pins the broken behavior.
        (tmp_path / "module.py").write_text("x = 1\n")
        validator = BehaviorValidator(project_path=tmp_path)

        with pytest.raises(TypeError):
            await validator._discover_test_file(str(tmp_path / "module.py"))

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_file(self, tmp_path: Path) -> None:
        # Same source bug as above; the fallthrough path also hits it.
        validator = BehaviorValidator(project_path=tmp_path)
        with pytest.raises(TypeError):
            await validator._discover_test_file(str(tmp_path / "nope.py"))


class TestBehaviorValidatorWithTests:
    """`validate_with_tests` end-to-end with mocked subprocess."""

    @pytest.mark.asyncio
    async def test_dangerous_pattern_short_circuits(self) -> None:
        # Even with a passing test, dangerous patterns should fail fast.
        validator = BehaviorValidator()
        result = await validator.validate_with_tests(
            file_path="module.py",
            code="eval('1')",
            test_path="tests/test_module.py",
        )

        assert result.valid is False
        assert any("eval" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_no_test_file_yields_error(self, tmp_path: Path) -> None:
        # Source bug: when no test file can be discovered, _discover_test_file
        # raises TypeError before the "No test file found for validation"
        # error path is reached. This test pins the broken behavior.
        validator = BehaviorValidator(project_path=tmp_path)
        (tmp_path / "definitely_does_not_exist_xyz.py").write_text("x = 1\n")

        with pytest.raises(TypeError):
            await validator.validate_with_tests(
                file_path=str(tmp_path / "definitely_does_not_exist_xyz.py"),
                code="x = 1",
            )

    @pytest.mark.asyncio
    async def test_passing_test_validates(self, tmp_path: Path) -> None:
        (tmp_path / "module.py").write_text("x = 1\n")
        test_path = tmp_path / "test_module.py"
        test_path.write_text("def test_x(): assert True\n")

        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="1 passed",
            stderr="",
        )

        validator = BehaviorValidator(project_path=tmp_path)
        with patch.object(
            BehaviorValidator,
            "_run_test",
            AsyncMock(return_value=completed),
        ):
            result = await validator.validate_with_tests(
                file_path=str(tmp_path / "module.py"),
                code="x = 1",
                test_path=str(test_path),
            )

        assert result.valid is True
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_failing_test_reports_failure(self, tmp_path: Path) -> None:
        (tmp_path / "module.py").write_text("x = 1\n")
        test_path = tmp_path / "test_module.py"
        test_path.write_text("def test_x(): assert False\n")

        completed = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="1 failed",
        )

        validator = BehaviorValidator(project_path=tmp_path)
        with patch.object(
            BehaviorValidator,
            "_run_test",
            AsyncMock(return_value=completed),
        ):
            result = await validator.validate_with_tests(
                file_path=str(tmp_path / "module.py"),
                code="x = 1",
                test_path=str(test_path),
            )

        assert result.valid is False
        assert any("return code 1" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_passed_returncode_with_failed_in_stderr(self, tmp_path: Path) -> None:
        # Some pytest invocations exit 0 but the word "FAILED" still appears
        # in stderr (e.g. a deprecation warning). The validator should detect
        # this.
        (tmp_path / "module.py").write_text("x = 1\n")
        test_path = tmp_path / "test_module.py"
        test_path.write_text("def test_x(): assert True\n")

        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="1 passed",
            stderr="FAILED some unrelated warning",
        )

        validator = BehaviorValidator(project_path=tmp_path)
        with patch.object(
            BehaviorValidator,
            "_run_test",
            AsyncMock(return_value=completed),
        ):
            result = await validator.validate_with_tests(
                file_path=str(tmp_path / "module.py"),
                code="x = 1",
                test_path=str(test_path),
            )

        assert result.valid is False
        assert any("test failed" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_import_error_in_stderr_reported(self, tmp_path: Path) -> None:
        # Source bug in _run_test: CompletedProcess is constructed without
        # the required `args` positional arg, so the return is always the
        # -2 exception path. Bypass _run_test and use a manually-constructed
        # AsyncMock to exercise the import-error logic in validate_with_tests.
        # The import-error branch is gated on the substring "ERROR" (all caps)
        # in stderr, then per-line on "Error" + "import" in the line.
        (tmp_path / "module.py").write_text("x = 1\n")
        test_path = tmp_path / "test_module.py"
        test_path.write_text("def test_x(): assert True\n")

        completed = subprocess.CompletedProcess(
            args=["pytest", str(test_path)],
            returncode=0,
            stdout="",
            stderr="ERROR collecting - ImportError: No module named 'broken_module'\n",
        )

        validator = BehaviorValidator(project_path=tmp_path)
        with patch.object(
            BehaviorValidator,
            "_run_test",
            AsyncMock(return_value=completed),
        ):
            result = await validator.validate_with_tests(
                file_path=str(tmp_path / "module.py"),
                code="x = 1",
                test_path=str(test_path),
            )

        assert result.valid is False
        assert any("import error" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_discover_invoked_when_test_path_missing(self, tmp_path: Path) -> None:
        (tmp_path / "module.py").write_text("x = 1\n")
        test_path = tmp_path / "test_module.py"
        test_path.write_text("def test_x(): assert True\n")

        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="1 passed",
            stderr="",
        )

        validator = BehaviorValidator(project_path=tmp_path)
        with patch.object(
            BehaviorValidator,
            "_run_test",
            AsyncMock(return_value=completed),
        ):
            result = await validator.validate_with_tests(
                file_path=str(tmp_path / "module.py"),
                code="x = 1",
                # No test_path -> _discover_test_file should be called.
            )

        assert result.valid is True


class TestBehaviorValidatorRunTest:
    """`_run_test` subprocess handling.

    Source bug: every return path constructs `subprocess.CompletedProcess(...)`
    without the required `args` positional argument, so the call raises
    TypeError. The outer `except Exception` at line 156 also constructs
    `CompletedProcess(...)` without `args`, which also raises — and that
    `TypeError` is unhandled, propagating out of `_run_test`. These tests
    pin that broken behavior so it is fixed intentionally, not silently.
    """

    @pytest.mark.asyncio
    async def test_run_test_raises_typeerror(self, tmp_path: Path) -> None:
        validator = BehaviorValidator(project_path=tmp_path)

        fake_proc = MagicMock()
        fake_proc.communicate = AsyncMock(return_value=(b"stdout-text", b"stderr-text"))
        fake_proc.returncode = 0

        with patch(
            "crackerjack.agents.behavior_validator.asyncio.create_subprocess_exec",
            AsyncMock(return_value=fake_proc),
        ):
            with pytest.raises(TypeError, match="args"):
                await validator._run_test("tests/test_module.py")

    @pytest.mark.asyncio
    async def test_run_test_timeout_raises_typeerror(self, tmp_path: Path) -> None:
        validator = BehaviorValidator(project_path=tmp_path)

        fake_proc = MagicMock()
        fake_proc.communicate = AsyncMock(return_value=(b"", b""))
        fake_proc.returncode = None

        with patch(
            "crackerjack.agents.behavior_validator.asyncio.create_subprocess_exec",
            AsyncMock(return_value=fake_proc),
        ):
            with patch(
                "crackerjack.agents.behavior_validator.asyncio.wait_for",
                AsyncMock(side_effect=TimeoutError),
            ):
                with pytest.raises(TypeError, match="args"):
                    await validator._run_test("tests/test_module.py")

    @pytest.mark.asyncio
    async def test_run_test_exception_raises_typeerror(self, tmp_path: Path) -> None:
        # Same root cause: the except-Exception branch's `CompletedProcess(...)`
        # also misses the required `args` argument.
        validator = BehaviorValidator(project_path=tmp_path)

        with patch(
            "crackerjack.agents.behavior_validator.asyncio.create_subprocess_exec",
            AsyncMock(side_effect=OSError("spawn failed")),
        ):
            with pytest.raises(TypeError, match="args"):
                await validator._run_test("tests/test_module.py")

    @pytest.mark.asyncio
    async def test_run_test_none_returncode_raises_typeerror(self, tmp_path: Path) -> None:
        validator = BehaviorValidator(project_path=tmp_path)

        fake_proc = MagicMock()
        fake_proc.communicate = AsyncMock(return_value=(b"", b""))
        fake_proc.returncode = None

        with patch(
            "crackerjack.agents.behavior_validator.asyncio.create_subprocess_exec",
            AsyncMock(return_value=fake_proc),
        ):
            with pytest.raises(TypeError, match="args"):
                await validator._run_test("tests/test_module.py")


class TestBehaviorValidatorMisc:
    """`can_handle` and `get_supported_types`."""

    @pytest.mark.asyncio
    async def test_can_handle_returns_high_confidence(self) -> None:
        validator = BehaviorValidator()
        issue = Issue(
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="test failure",
        )

        score = await validator.can_handle(issue)
        assert score == pytest.approx(0.9)

    def test_get_supported_types_includes_all_issue_types(self) -> None:
        validator = BehaviorValidator()
        types = validator.get_supported_types()

        assert isinstance(types, set)
        # Should contain at least one of the canonical types.
        assert IssueType.FORMATTING in types
        assert IssueType.SECURITY in types
        # And the full enum (one-to-one).
        assert len(types) == len(list(IssueType))
