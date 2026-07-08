"""Unit tests for the fix-runner CLI (subprocess driver)."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

from crackerjack.ai_fix.fix_runner import (
    PlanPayload,
    PlanResult,
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
