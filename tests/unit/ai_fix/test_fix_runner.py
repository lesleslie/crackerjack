"""Unit tests for the fix-runner CLI (subprocess driver)."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from crackerjack.ai_fix.fix_runner import (
    PlanPayload,
    PlanResult,
    _payload_to_fix_plan,
    run,
)


def test_run_returns_2_on_missing_plans_json(tmp_path: Path) -> None:
    """A nonexistent plans-json path should return exit code 2 (setup error)."""
    rc = run([
        "--plans-json", str(tmp_path / "missing.json"),
        "--output-json", str(tmp_path / "out.json"),
        "--project-root", str(tmp_path),
    ])
    assert rc == 2


def test_run_returns_2_on_unknown_fixer(tmp_path: Path) -> None:
    """A plan with a non-existent fixer_id should return exit code 2."""
    plans_path = tmp_path / "plans.json"
    plans_path.write_text(json.dumps([{
        "fixer_id": "no.such.module:DoesNotExist",
        "file_path": "f.py",
        "issue_type": "FORMATTING",
        "changes": [],
        "risk_level": "low",
        "issue_message": "test",
        "issue_stage": "ruff-check",
    }]))
    out_path = tmp_path / "out.json"
    rc = run([
        "--plans-json", str(plans_path),
        "--output-json", str(out_path),
        "--project-root", str(tmp_path),
    ])
    assert rc == 2
    assert not out_path.exists() or json.loads(out_path.read_text()) == {}


def test_plan_payload_roundtrip() -> None:
    """PlanPayload can be constructed and serialized via model_dump_json."""
    p = PlanPayload(
        fixer_id="crackerjack.agents.architect_agent:ArchitectAgent",
        file_path="f.py",
        issue_type="FORMATTING",
        changes=[],
        risk_level="low",
        issue_message="test",
        issue_stage="ruff-check",
    )
    roundtrip = PlanPayload.model_validate_json(p.model_dump_json())
    assert roundtrip == p


def test_plan_result_roundtrip() -> None:
    """PlanResult can be constructed and serialized via model_dump_json."""
    r = PlanResult(
        plan_idx=0,
        success=True,
        modified_content="x = 1\n",
        files_modified=["f.py"],
        remaining_issues=[],
    )
    roundtrip = PlanResult.model_validate_json(r.model_dump_json())
    assert roundtrip == r


def test_payload_to_fix_plan_roundtrip() -> None:
    """PlanPayload must reconstruct into a real FixPlan dataclass.

    Regression test for the production-hazard finding: dispatching
    ``plan.model_dump()`` (a dict) to fixers caused
    ``AttributeError: 'dict' object has no attribute 'file_path'``.
    The fix-runner must reconstruct a FixPlan with proper ChangeSpec
    entries so fixers' attribute access works.
    """
    payload = PlanPayload(
        fixer_id="crackerjack.agents.architect_agent:ArchitectAgent",
        file_path="crackerjack/__init__.py",
        issue_type="FORMATTING",
        changes=[
            {
                "line_range": [1, 3],
                "old_code": "x = 1\n",
                "new_code": "x = 2\n",
                "reason": "refactor",
            },
            {
                "line_range": [10, 12],
                "old_code": "y = 1\n",
                "new_code": "y = 2\n",
                "reason": "refactor",
            },
        ],
        risk_level="low",
        issue_message="smoke test message",
        issue_stage="ruff-check",
    )

    fix_plan = _payload_to_fix_plan(payload)

    assert fix_plan.file_path == "crackerjack/__init__.py"
    assert fix_plan.issue_type == "FORMATTING"
    assert fix_plan.risk_level == "low"
    assert fix_plan.issue_message == "smoke test message"
    assert fix_plan.issue_stage == "ruff-check"
    assert len(fix_plan.changes) == 2
    assert fix_plan.changes[0].line_range == (1, 3)
    assert fix_plan.changes[0].old_code == "x = 1\n"
    assert fix_plan.changes[0].new_code == "x = 2\n"
    assert fix_plan.changes[0].reason == "refactor"
    assert fix_plan.changes[1].line_range == (10, 12)


def test_payload_to_fix_plan_handles_empty_and_malformed_changes() -> None:
    """Empty changes list, missing fields, and bad line_range coerce safely."""
    payload = PlanPayload(
        fixer_id="x:Foo",
        file_path="f.py",
        issue_type="FORMATTING",
        changes=[
            {},  # missing all fields → defaults
            {"line_range": "bogus", "old_code": "a", "new_code": "b"},  # bad range
        ],
        risk_level="low",
        issue_message="",
        issue_stage="ruff-check",
    )

    fix_plan = _payload_to_fix_plan(payload)

    assert fix_plan.file_path == "f.py"
    assert len(fix_plan.changes) == 2
    # Empty change gets default (0, 0) range and empty strings
    assert fix_plan.changes[0].line_range == (0, 0)
    assert fix_plan.changes[0].old_code == ""
    # Bad line_range also coerces to (0, 0)
    assert fix_plan.changes[1].line_range == (0, 0)
    assert fix_plan.changes[1].old_code == "a"
    assert fix_plan.changes[1].new_code == "b"


def test_payload_to_fix_plan_coerces_invalid_risk_level() -> None:
    """An unknown risk_level falls back to 'low' (FixPlan is a Literal)."""
    payload = PlanPayload(
        fixer_id="x:Foo",
        file_path="f.py",
        issue_type="FORMATTING",
        changes=[],
        risk_level="huge",  # invalid
        issue_message="m",
        issue_stage="ruff-check",
    )

    fix_plan = _payload_to_fix_plan(payload)
    assert fix_plan.risk_level == "low"
