"""Unit tests for the SandboxedFixerDispatcher.

These tests use a fake ``FixSandbox`` (no real subprocess) and a fake
``fixer_resolver`` to exercise the dispatcher's contract in isolation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from crackerjack.ai_fix.fix_sandbox import SandboxResult
from crackerjack.ai_fix.sandboxed_dispatcher import SandboxedFixerDispatcher
from crackerjack.agents.base import FixResult
from crackerjack.models.fix_plan import FixPlan


def _make_plan(file_path: str, issue_type: str = "FORMATTING") -> FixPlan:
    return FixPlan(
        file_path=file_path,
        issue_type=issue_type,
        changes=[],
        rationale="test",
        risk_level="low",
        validated_by="test",
        issue_message="test message",
        issue_stage="ruff-check",
    )


def _write_result_json(
    output_path: Path,
    results: list[dict[str, Any]],
) -> None:
    output_path.write_text(
        json.dumps({"results": results}),
        encoding="utf-8",
    )


def test_dispatch_batch_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sandbox returns a valid result JSON → dispatcher builds FixResult per plan."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    output_json = tmp_path / "out" / "results.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    # Pre-write the result JSON that the (mocked) fix-runner would have
    # written. The dispatcher's command path goes through
    # ``sandbox.run_command`` (a MagicMock), so the in-process ``fix_runner.run``
    # is bypassed — we must stage the output file directly.
    _write_result_json(output_json, [{
        "plan_idx": 0,
        "success": True,
        "modified_content": "x = 2\n",
        "files_modified": [str(source)],
        "remaining_issues": [],
    }])
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=True,
        modified_content="x = 2\n",
        duration_s=0.1,
    ))

    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 0,
    )

    dispatcher = SandboxedFixerDispatcher(sandbox=sandbox)
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].files_modified == [str(source)]
    assert sandbox.run_command.call_count == 1


def test_dispatch_batch_missing_result_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sandbox passed=True but output file missing → all plans fail.

    Regression test for the production-hazard finding: a missing
    output file with passed=True used to synthesize success, masking
    real bugs. Now it returns failure with a clear reason.
    """
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=True,
        modified_content="x = 1\n",
        duration_s=0.1,
    ))

    # Patch fix_runner.run to do nothing — the output file is never created.
    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 0,
    )

    dispatcher = SandboxedFixerDispatcher(sandbox=sandbox)
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is False
    assert "result file not found" in results[0].remaining_issues[0]


def test_dispatch_batch_subprocess_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sandbox returns passed=False, reason='<err>' → all plans fail."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=False,
        reason="subprocess exit code 1",
        duration_s=0.1,
    ))

    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 1,
    )

    dispatcher = SandboxedFixerDispatcher(sandbox=sandbox)
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is False
    assert "subprocess exit code 1" in results[0].remaining_issues[0]


def test_dispatch_batch_validation_failure_no_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validation failure: fallback must NOT be attempted, even when env var is set."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=False,
        reason="output validation failed: SyntaxError",
        duration_s=0.1,
    ))

    fallback_called = MagicMock()
    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 1,
    )
    monkeypatch.setenv("CRACKERJACK_AI_FIX_SANDBOX_FALLBACK", "1")

    dispatcher = SandboxedFixerDispatcher(
        sandbox=sandbox, in_process_fallback=fallback_called,
    )
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is False
    assert "validation failed" in results[0].remaining_issues[0]
    fallback_called.assert_not_called()


def test_dispatch_batch_timeout_with_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subprocess timeout: fallback IS attempted when env var is set."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=False,
        reason="subprocess timeout after 300s",
        duration_s=300.0,
    ))

    fallback_result = [FixResult(success=True, files_modified=[str(source)])]
    fallback_called = MagicMock(return_value=fallback_result)
    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 1,
    )
    monkeypatch.setenv("CRACKERJACK_AI_FIX_SANDBOX_FALLBACK", "1")

    dispatcher = SandboxedFixerDispatcher(
        sandbox=sandbox, in_process_fallback=fallback_called,
    )
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    fallback_called.assert_called_once()
    assert results is fallback_result


def test_dispatch_batch_serialization_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plan that fails Pydantic validation → that plan gets a failure result."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock()
    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 2,
    )

    # Force a serialization error by passing a plan that will fail
    # model_dump_json. (Pydantic v2 doesn't normally fail; we patch
    # the dispatcher's _serialize_plans to raise.)
    dispatcher = SandboxedFixerDispatcher(sandbox=sandbox)
    monkeypatch.setattr(
        dispatcher, "_serialize_plans", MagicMock(side_effect=ValueError("boom"))
    )

    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is False
    assert "plan serialization failed" in results[0].remaining_issues[0]
    sandbox.run_command.assert_not_called()


def test_dispatch_batch_malformed_result_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sandbox returns passed=True but result file has invalid JSON → all plans fail."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    output_json = tmp_path / "out" / "results.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text("not valid json {{{", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=True,
        modified_content="x = 1\n",
        duration_s=0.1,
    ))

    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 0,
    )

    dispatcher = SandboxedFixerDispatcher(sandbox=sandbox)
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is False
    assert "malformed result" in results[0].remaining_issues[0]
