"""Tests for the dependency-free issue vocabulary module.

`crackerjack.models.issues` extracts `Issue`, `IssueType`, `Priority`, and
`FixResult` out of `crackerjack.agents.base` so the ~30 files that depend on
these types as shared vocabulary don't need to import the (unstable)
orchestration machinery in `agents/`, `ai_fix/`, `intelligence/`, or
`memory/`.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from crackerjack.models.issues import (
    CrackerjackRunResult,
    FixResult,
    Issue,
    IssueType,
    Priority,
)

GOLDEN = Path(__file__).parent / "fixtures" / "json_output_v1.json"


def test_issue_type_has_no_agents_dependency() -> None:
    import crackerjack.models.issues as mod

    source = inspect.getsource(mod)
    assert "crackerjack.agents" not in source
    assert "crackerjack.ai_fix" not in source
    assert "crackerjack.intelligence" not in source
    assert "crackerjack.memory" not in source


def test_priority_enum_values() -> None:
    assert Priority.LOW.value == "low"
    assert Priority.MEDIUM.value == "medium"
    assert Priority.HIGH.value == "high"
    assert Priority.CRITICAL.value == "critical"


def test_issue_type_enum_values() -> None:
    assert IssueType.FORMATTING.value == "formatting"
    assert IssueType.TYPE_ERROR.value == "type_error"
    assert IssueType.SECURITY.value == "security"
    assert IssueType.TEST_FAILURE.value == "test_failure"
    assert IssueType.IMPORT_ERROR.value == "import_error"
    assert IssueType.COMPLEXITY.value == "complexity"
    assert IssueType.DEAD_CODE.value == "dead_code"
    assert IssueType.DEPENDENCY.value == "dependency"
    assert IssueType.DRY_VIOLATION.value == "dry_violation"
    assert IssueType.PERFORMANCE.value == "performance"
    assert IssueType.DOCUMENTATION.value == "documentation"
    assert IssueType.TEST_ORGANIZATION.value == "test_organization"
    assert IssueType.COVERAGE_IMPROVEMENT.value == "coverage_improvement"
    assert IssueType.REGEX_VALIDATION.value == "regex_validation"
    assert IssueType.SEMANTIC_CONTEXT.value == "semantic_context"
    assert IssueType.WARNING.value == "warning"
    assert IssueType.REFURB.value == "refurb"


def test_issue_constructs_with_expected_fields() -> None:
    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="test message",
        id="test-1",
        file_path="foo.py",
        line_number=42,
        details=["detail one"],
        stage="fast_hooks",
    )
    assert issue.type is IssueType.FORMATTING
    assert issue.severity is Priority.MEDIUM
    assert issue.message == "test message"
    assert issue.id == "test-1"
    assert issue.file_path == "foo.py"
    assert issue.line_number == 42
    assert issue.details == ["detail one"]
    assert issue.stage == "fast_hooks"


def test_issue_default_fields() -> None:
    issue = Issue(
        type=IssueType.SECURITY,
        severity=Priority.HIGH,
        message="default fields",
    )
    assert issue.id.startswith("issue_")
    assert issue.file_path is None
    assert issue.line_number is None
    assert issue.details == []
    assert issue.stage == "unknown"


def test_fix_result_constructs() -> None:
    result = FixResult(
        success=True,
        confidence=0.9,
        fixes_applied=["fix a"],
        remaining_issues=["issue b"],
        recommendations=["rec c"],
        files_modified=["foo.py"],
        issue_specific_confidence=0.75,
    )
    assert result.success is True
    assert result.confidence == 0.9
    assert result.fixes_applied == ["fix a"]
    assert result.remaining_issues == ["issue b"]
    assert result.recommendations == ["rec c"]
    assert result.files_modified == ["foo.py"]
    assert result.issue_specific_confidence == 0.75


def test_fix_result_defaults() -> None:
    result = FixResult(success=False)
    assert result.confidence == 0.0
    assert result.fixes_applied == []
    assert result.remaining_issues == []
    assert result.recommendations == []
    assert result.files_modified == []
    assert result.issue_specific_confidence is None


def test_fix_result_merge_with() -> None:
    a = FixResult(
        success=True,
        confidence=0.5,
        fixes_applied=["a1"],
        remaining_issues=["shared", "a-only"],
        recommendations=["rec a"],
        files_modified=["a.py", "shared.py"],
    )
    b = FixResult(
        success=True,
        confidence=0.8,
        fixes_applied=["b1"],
        remaining_issues=["shared", "b-only"],
        recommendations=["rec b"],
        files_modified=["b.py", "shared.py"],
    )
    merged = a.merge_with(b)
    assert merged.success is True
    assert merged.confidence == 0.8
    assert merged.fixes_applied == ["a1", "b1"]
    assert set(merged.remaining_issues) == {"shared", "a-only", "b-only"}
    assert merged.recommendations == ["rec a", "rec b"]
    assert set(merged.files_modified) == {"a.py", "b.py", "shared.py"}


def test_fix_result_merge_with_failure_propagates() -> None:
    a = FixResult(success=True)
    b = FixResult(success=False)
    merged = a.merge_with(b)
    assert merged.success is False


def test_run_result_matches_golden_schema() -> None:
    result = CrackerjackRunResult(
        schema_version="1",
        success=False,
        issues=[],
        summary={"total": 0, "fixed": 0, "remaining": 0},
    )
    payload = json.loads(result.model_dump_json())
    golden = json.loads(GOLDEN.read_text())
    assert set(payload.keys()) == set(golden.keys())
    assert payload["schema_version"] == golden["schema_version"]


def test_run_result_defaults_schema_version_to_1() -> None:
    result = CrackerjackRunResult(
        success=True,
        issues=[],
        summary={"total": 0, "fixed": 0, "remaining": 0},
    )
    assert result.schema_version == "1"


def test_run_result_serializes_issue_list() -> None:
    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="line too long",
        id="issue-1",
        file_path="foo.py",
        line_number=10,
    )
    result = CrackerjackRunResult(
        success=False,
        issues=[issue],
        summary={"total": 1, "fixed": 0, "remaining": 1},
    )
    payload = json.loads(result.model_dump_json())
    assert len(payload["issues"]) == 1
    assert payload["issues"][0]["message"] == "line too long"
    assert payload["issues"][0]["type"] == "formatting"
