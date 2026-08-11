from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from crackerjack.cli.audit_cli import app
from crackerjack.skills import health as skills_health


runner = CliRunner()


@pytest.mark.unit
def test_audit_skills_reports_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "crackerjack.cli.audit_cli.fetch_skill_health",
        lambda **_: skills_health.SkillHealthReport(status="fresh", stale_count=0),
    )
    result = runner.invoke(app, ["skills"])
    assert result.exit_code == 0
    assert "fresh" in result.output.lower()


@pytest.mark.unit
def test_audit_skills_json_includes_stale_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "crackerjack.cli.audit_cli.fetch_skill_health",
        lambda **_: skills_health.SkillHealthReport(
            status="stale", stale_count=3, raw_rows=[]
        ),
    )
    result = runner.invoke(app, ["skills", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["stale_count"] == 3
    assert payload["status"] == "stale"


@pytest.mark.unit
def test_audit_skills_fail_exits_1_when_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "crackerjack.cli.audit_cli.fetch_skill_health",
        lambda **_: skills_health.SkillHealthReport(
            status="stale", stale_count=2, raw_rows=[]
        ),
    )
    result = runner.invoke(app, ["skills", "--fail"])
    assert result.exit_code == 1


@pytest.mark.unit
def test_audit_skills_unreachable_warns_but_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "crackerjack.cli.audit_cli.fetch_skill_health",
        lambda **_: skills_health.SkillHealthReport(
            status="unavailable", stale_count=0
        ),
    )
    result = runner.invoke(app, ["skills"])
    assert result.exit_code == 0
    assert "unavailable" in result.output.lower() or "warn" in result.output.lower()
