"""Unit tests for validation coordinator behavior."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from crackerjack.agents.syntax_validator import ValidationResult
from crackerjack.agents.validation_coordinator import (
    TypeChangeValidationResult,
    ValidationCoordinator,
)


@pytest.mark.asyncio
async def test_validate_fix_ruff_only_skips_refurb() -> None:
    """Ruff-only validation should not invoke refurb checks."""
    coordinator = ValidationCoordinator(project_path=Path("/tmp"))

    coordinator.syntax.validate = AsyncMock(return_value=ValidationResult(True, []))
    coordinator.logic.validate = AsyncMock(return_value=ValidationResult(True, []))
    coordinator.behavior.validate = AsyncMock(
        return_value=ValidationResult(True, [])
    )
    coordinator.quality._check_ruff = AsyncMock(return_value=[])
    coordinator.quality._check_refurb = AsyncMock(return_value=["refurb: should not run"])

    is_valid, feedback = await coordinator.validate_fix(
        code="def hello() -> None:\n    print('hello')\n",
        file_path="/tmp/test.py",
        quality_checks=("ruff",),
    )

    assert is_valid is True
    assert feedback == "Fix validated"
    coordinator.quality._check_ruff.assert_awaited_once()
    coordinator.quality._check_refurb.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_fix_strict_ruff_validation_fails_on_existing_issue() -> None:
    """Strict Ruff validation should fail if the issue is still present."""
    coordinator = ValidationCoordinator(project_path=Path("/tmp"))

    coordinator.syntax.validate = AsyncMock(return_value=ValidationResult(True, []))
    coordinator.logic.validate = AsyncMock(return_value=ValidationResult(True, []))
    coordinator.behavior.validate = AsyncMock(
        return_value=ValidationResult(True, [])
    )
    coordinator.quality._check_ruff = AsyncMock(
        return_value=["ruff C901 (line 1): still too complex"]
    )
    coordinator.quality._check_refurb = AsyncMock(return_value=[])

    is_valid, feedback = await coordinator.validate_fix(
        code="def hello():\n    return 1\n",
        file_path="/tmp/test.py",
        original_code="def hello():\n    return 1\n",
        quality_checks=("ruff",),
        compare_to_original=False,
    )

    assert is_valid is False
    assert "Quality validation failed" in feedback
    coordinator.quality._check_ruff.assert_awaited_once()
    coordinator.quality._check_refurb.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_with_retry_forwards_strict_validation_mode() -> None:
    """Retry validation should preserve strict Ruff behavior."""
    coordinator = ValidationCoordinator(project_path=Path("/tmp"))
    coordinator.validate_fix = AsyncMock(return_value=(True, "Fix validated"))

    result = await coordinator.validate_with_retry(
        code="def hello():\n    return 1\n",
        file_path="/tmp/test.py",
        original_code="def hello():\n    return 1\n",
        quality_checks=("ruff",),
        compare_to_original=False,
    )

    assert result == (True, "Fix validated", 1)
    coordinator.validate_fix.assert_awaited_once_with(
        code="def hello():\n    return 1\n",
        file_path="/tmp/test.py",
        test_path=None,
        run_tests=False,
        original_code="def hello():\n    return 1\n",
        quality_checks=("ruff",),
        compare_to_original=False,
    )


def test_quality_validator_normalizes_ruff_baseline_keys() -> None:
    """Ruff baseline matching should ignore line shifts for same rule/message."""
    from crackerjack.agents.validation_coordinator import QualityValidator

    key_a = QualityValidator._normalize_ruff_key(
        "F401", "`json` imported but unused"
    )
    key_b = QualityValidator._normalize_ruff_key(
        "F401", "`json` imported but unused"
    )
    assert key_a == key_b


def test_quality_validator_normalizes_refurb_line_prefixes() -> None:
    """Refurb baseline matching should ignore file/line prefixes."""
    from crackerjack.agents.validation_coordinator import QualityValidator

    normalized = QualityValidator._normalize_refurb_line(
        "/tmp/x.py:123: SIM102 Use a single if statement"
    )
    assert normalized == "SIM102 Use a single if statement"


@pytest.mark.asyncio
async def test_validate_fix_rejects_dangerous_eval() -> None:
    """Bug: validation_coordinator.py defined a local stub
    ``BehaviorValidator`` whose ``validate()`` always returned
    ``valid=True`` with no actual checks. The real
    ``BehaviorValidator`` in ``behavior_validator.py`` rejects
    ``eval()``/``exec()``/``__import__`` patterns — but it was
    shadowed by the stub, so dangerous code passed validation.

    Fix: use the real BehaviorValidator. When logic also fails (so
    behavior is the only validator that could pass), a fix
    introducing ``eval()`` must NOT validate.
    """
    coordinator = ValidationCoordinator(project_path=Path("/tmp"))
    coordinator.syntax.validate = AsyncMock(return_value=ValidationResult(True, []))
    # Logic fails so behavior is the only validator that could pass.
    coordinator.logic.validate = AsyncMock(
        return_value=ValidationResult(False, ["logic fail"])
    )
    coordinator.quality._check_ruff = AsyncMock(return_value=[])
    coordinator.quality._check_refurb = AsyncMock(return_value=[])

    is_valid, feedback = await coordinator.validate_fix(
        # NOTE: eval() below is a static fixture string passed to
        # validate()'s regex check — it is NEVER executed.
        code="result = eval(user_input)\n",
        file_path="/tmp/test.py",
        quality_checks=("ruff",),
    )

    assert is_valid is False, (
        "A fix containing eval() must NOT pass validation when "
        "behavior is the only validator that could pass — the "
        "BehaviorValidator's dangerous-pattern detector (eval/exec/"
        "__import__) was being shadowed by a stub."
    )
    assert "eval" in feedback.lower()


@pytest.mark.asyncio
async def test_validate_fix_rejects_exec_call() -> None:
    """Same regression test for ``exec()`` dangerous pattern."""
    coordinator = ValidationCoordinator(project_path=Path("/tmp"))
    coordinator.syntax.validate = AsyncMock(return_value=ValidationResult(True, []))
    coordinator.logic.validate = AsyncMock(
        return_value=ValidationResult(False, ["logic fail"])
    )
    coordinator.quality._check_ruff = AsyncMock(return_value=[])
    coordinator.quality._check_refurb = AsyncMock(return_value=[])

    is_valid, feedback = await coordinator.validate_fix(
        code="os.exec('rm -rf /')\n",
        file_path="/tmp/test.py",
        quality_checks=("ruff",),
    )

    assert is_valid is False, (
        "A fix containing exec() must NOT pass validation when "
        "behavior is the only validator that could pass"
    )


@pytest.mark.asyncio
async def test_validate_fix_for_type_change_rejects_when_new_ty_errors_in_dependents(
    tmp_path,
) -> None:
    """Bug B: validate_fix_for_type_change must reject a fix that
    introduces new type errors in dependent files (callers of the
    changed file) even when ruff/refurb on the modified file alone
    pass.

    This protects against the regression where ``validate_fix`` only
    ran lint tools on a SINGLE modified file and missed cascade
    errors in callers — letting the broken change be saved to disk.
    """
    target = tmp_path / "target.py"
    target.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    target_path = str(target)
    new_code = "def add(a: str, b: str) -> str:\n    return a + b\n"

    coordinator = ValidationCoordinator(project_path=tmp_path)

    # Stub the ty adapter to simulate "no errors on baseline" and
    # "two NEW errors on dependents after the fix".
    baseline_result = AsyncMock()
    baseline_result.issues_found = 0
    baseline_result.parsed_issues = []

    post_fix_result = AsyncMock()
    post_fix_result.issues_found = 2
    post_fix_result.parsed_issues = [
        {
            "file_path": str(tmp_path / "caller.py"),
            "line_number": 10,
            "column_number": 5,
            "message": "Argument 1 has incompatible type 'int'",
            "code": "arg-type",
            "severity": "error",
        },
        {
            "file_path": str(tmp_path / "caller.py"),
            "line_number": 20,
            "column_number": 5,
            "message": "Argument 2 has incompatible type 'int'",
            "code": "arg-type",
            "severity": "error",
        },
    ]

    fake_adapter = AsyncMock()
    fake_adapter.check = AsyncMock(side_effect=[baseline_result, post_fix_result])

    with pytest.MonkeyPatch.context() as mp:
        from crackerjack.adapters.type import ty as ty_module

        mp.setattr(ty_module, "TyAdapter", lambda: fake_adapter)

        is_valid, feedback = await coordinator.validate_fix_for_type_change(
            code=new_code,
            file_path=target_path,
            original_code="def add(a: int, b: int) -> int:\n    return a + b\n",
        )

    assert is_valid is False, (
        "validate_fix_for_type_change must reject a fix that "
        "introduces new ty errors in dependent files. Got valid=True."
    )
    assert "ty" in feedback.lower() or "type" in feedback.lower(), (
        f"Feedback must mention the type-check failure, got: {feedback!r}"
    )
    # Ty was invoked twice — baseline then post-fix.
    assert fake_adapter.check.await_count == 2


@pytest.mark.asyncio
async def test_validate_fix_for_type_change_accepts_when_no_new_ty_errors(
    tmp_path,
) -> None:
    """Bug B: validate_fix_for_type_change must accept a fix when
    the project-wide ty run finds no NEW errors in dependent files
    relative to the baseline.
    """
    target = tmp_path / "target.py"
    target.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    target_path = str(target)
    new_code = "def add(a: int, b: int) -> int:\n    return a + b\n"

    coordinator = ValidationCoordinator(project_path=tmp_path)

    # Both baseline and post-fix report 0 issues.
    clean_result = AsyncMock()
    clean_result.issues_found = 0
    clean_result.parsed_issues = []

    fake_adapter = AsyncMock()
    fake_adapter.check = AsyncMock(side_effect=[clean_result, clean_result])

    with pytest.MonkeyPatch.context() as mp:
        from crackerjack.adapters.type import ty as ty_module

        mp.setattr(ty_module, "TyAdapter", lambda: fake_adapter)

        is_valid, feedback = await coordinator.validate_fix_for_type_change(
            code=new_code,
            file_path=target_path,
            original_code="def add(a: int, b: int) -> int:\n    return a + b\n",
        )

    assert is_valid is True, (
        "validate_fix_for_type_change must accept a fix that does "
        f"not introduce new ty errors. Got feedback: {feedback!r}"
    )
    assert fake_adapter.check.await_count == 2


def test_type_change_validation_result_dataclass() -> None:
    """TypeChangeValidationResult must carry a structured diff
    (new_issues, resolved_issues) so callers can decide whether to
    keep, roll back, or escalate the fix."""
    result = TypeChangeValidationResult(
        is_valid=True,
        new_issues=(),
        resolved_issues=("old_issue_1",),
        feedback="no new type errors",
    )
    assert result.is_valid is True
    assert result.new_issues == ()
    assert result.resolved_issues == ("old_issue_1",)
    assert result.feedback == "no new type errors"
