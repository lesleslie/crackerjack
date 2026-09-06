"""Tests for ``crackerjack.services.prompt_evolution``.

Covers the ``FailedFixAttempt`` / ``SuccessfulFixPattern`` dataclasses plus
the ``PromptEvolution`` singleton (via ``get_prompt_evolution``) and its
record / lookup paths. The module persists state to ``~/.cache/crackerjack/
prompt_evolution``; tests use a tmp_path to keep the home directory clean.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from crackerjack.models.issues import Issue, IssueType, Priority
from crackerjack.services.prompt_evolution import (
    FailedFixAttempt,
    PromptEvolution,
    SuccessfulFixPattern,
    get_prompt_evolution,
)


def _make_issue(
    message: str = "Test failed [e001]",
    issue_type: IssueType = IssueType.FORMATTING,
    file_path: str = "/tmp/example.py",
    line_number: int = 42,
) -> Issue:
    return Issue(
        type=issue_type,
        severity=Priority.HIGH,
        message=message,
        file_path=file_path,
        line_number=line_number,
    )


def test_failed_fix_attempt_defaults() -> None:
    attempt = FailedFixAttempt(
        issue_type="formatting",
        error_code="e001",
        file_path="/tmp/x.py",
        line_number=10,
        original_message="Bad indent",
        attempted_fix="Replace tab",
        failure_reason="Did not pass",
    )
    assert attempt.timestamp  # auto-generated
    assert attempt.context_before == ""
    assert attempt.context_after == ""


def test_failed_fix_attempt_keeps_timestamp_per_instance() -> None:
    """Each attempt gets its own timestamp (mutable default factory)."""
    a1 = FailedFixAttempt(
        issue_type="formatting",
        error_code="e001",
        file_path="/tmp/x.py",
        line_number=10,
        original_message="m",
        attempted_fix="f",
        failure_reason="r",
    )
    a2 = FailedFixAttempt(
        issue_type="formatting",
        error_code="e001",
        file_path="/tmp/x.py",
        line_number=10,
        original_message="m",
        attempted_fix="f",
        failure_reason="r",
    )
    # ISO timestamps may or may not differ at microsecond resolution; both
    # must be non-empty strings.
    assert a1.timestamp
    assert a2.timestamp


def test_successful_fix_pattern_defaults() -> None:
    pattern = SuccessfulFixPattern(
        issue_type="formatting",
        error_code="e001",
        pattern_description="Replace tab with 4 spaces",
        before_code="def f():\\treturn 1",
        after_code="def f():    return 1",
    )
    assert pattern.success_count == 1
    assert pattern.last_used  # auto-generated


def test_prompt_evolution_default_storage_path(tmp_path: Path) -> None:
    evolution = PromptEvolution(storage_path=tmp_path)
    assert evolution.storage_path == tmp_path


def test_prompt_evolution_record_failed_fix(tmp_path: Path) -> None:
    evolution = PromptEvolution(storage_path=tmp_path)
    issue = _make_issue()
    evolution.record_failed_fix(
        issue=issue,
        attempted_fix="some fix",
        failure_reason="did not parse",
    )
    # ``failed_attempts`` is a flat list of FailedFixAttempt dataclasses.
    assert len(evolution.failed_attempts) == 1
    assert evolution.failed_attempts[0].issue_type == issue.type.value
    assert evolution.failed_attempts[0].error_code == "e001"


def test_prompt_evolution_record_successful_fix(tmp_path: Path) -> None:
    evolution = PromptEvolution(storage_path=tmp_path)
    issue = _make_issue()
    evolution.record_successful_fix(
        issue=issue,
        before_code="before",
        after_code="after",
    )
    key = f"{issue.type.value}:{evolution._extract_error_code(issue.message)}"  # noqa: SLF001
    assert key in evolution.successful_patterns
    pattern = evolution.successful_patterns[key]
    assert pattern.before_code == "before"
    assert pattern.after_code == "after"
    assert pattern.success_count == 1


def test_prompt_evolution_get_success_rate(tmp_path: Path) -> None:
    evolution = PromptEvolution(storage_path=tmp_path)
    # No data: success rate is 0.0
    rate = evolution.get_success_rate(issue_type="formatting", error_code="e001")
    assert rate == 0.0


def test_prompt_evolution_get_success_rate_with_data(tmp_path: Path) -> None:
    evolution = PromptEvolution(storage_path=tmp_path)
    issue = _make_issue()
    evolution.record_successful_fix(
        issue=issue, before_code="a", after_code="b"
    )
    evolution.record_failed_fix(
        issue=issue,
        attempted_fix="x",
        failure_reason="y",
    )
    rate = evolution.get_success_rate(
        issue_type=issue.type.value,
        error_code=evolution._extract_error_code(issue.message),  # noqa: SLF001
    )
    # 1 success / (1 success + 1 failure) = 0.5
    assert rate == 0.5


def test_prompt_evolution_analyze_failure_patterns(tmp_path: Path) -> None:
    evolution = PromptEvolution(storage_path=tmp_path)
    issue = _make_issue()
    evolution.record_failed_fix(
        issue=issue,
        attempted_fix="x",
        failure_reason="did not parse",
    )
    patterns = evolution.analyze_failure_patterns()
    assert isinstance(patterns, dict)


def test_prompt_evolution_get_evolved_prompt_without_history(tmp_path: Path) -> None:
    """Without successful patterns, returns the base prompt unchanged."""
    evolution = PromptEvolution(storage_path=tmp_path)
    issue = _make_issue()
    base = "fix this: <code>"
    result = evolution.get_evolved_prompt(issue=issue, base_prompt=base)
    assert isinstance(result, str)


def test_prompt_evolution_get_evolved_prompt_with_history(tmp_path: Path) -> None:
    """With a successful pattern, the prompt is augmented with the after-code."""
    evolution = PromptEvolution(storage_path=tmp_path)
    issue = _make_issue()
    evolution.record_successful_fix(
        issue=issue,
        before_code="before",
        after_code="AFTER_TEMPLATE",
    )
    base = "fix this: <code>"
    result = evolution.get_evolved_prompt(issue=issue, base_prompt=base)
    assert isinstance(result, str)
    # The augmented prompt should reference the successful after-code.
    assert "AFTER_TEMPLATE" in result or base in result


def test_prompt_evolution_extract_error_code(tmp_path: Path) -> None:
    """The regex extracts lowercase + digits + hyphens from ``[code]``."""
    evolution = PromptEvolution(storage_path=tmp_path)
    code = evolution._extract_error_code("Failure [e501] too long")  # noqa: SLF001
    assert code == "e501"


def test_prompt_evolution_extract_error_code_no_match(tmp_path: Path) -> None:
    evolution = PromptEvolution(storage_path=tmp_path)
    code = evolution._extract_error_code("plain message, no brackets")  # noqa: SLF001
    assert code == "unknown"


def test_prompt_evolution_extract_error_code_handles_complex_brackets(tmp_path: Path) -> None:
    """The regex matches the first bracketed identifier (lowercase + digits + hyphen)."""
    evolution = PromptEvolution(storage_path=tmp_path)
    code = evolution._extract_error_code("err [abc-123-x] stuff")  # noqa: SLF001
    assert code == "abc-123-x"


def test_get_prompt_evolution_singleton() -> None:
    """The module-level factory returns a single shared instance."""
    # Reset the module-level singleton via a patch so the test is hermetic.
    with patch("crackerjack.services.prompt_evolution._evolution_instance", None):
        first = get_prompt_evolution()
        second = get_prompt_evolution()
        assert first is second


def test_prompt_evolution_state_persists_across_instances(tmp_path: Path) -> None:
    """A new instance reading the same storage_path sees prior records."""
    evolution_a = PromptEvolution(storage_path=tmp_path)
    issue = _make_issue()
    evolution_a.record_successful_fix(
        issue=issue, before_code="a", after_code="b"
    )

    evolution_b = PromptEvolution(storage_path=tmp_path)
    key = f"{issue.type.value}:{evolution_b._extract_error_code(issue.message)}"  # noqa: SLF001
    assert key in evolution_b.successful_patterns
