from __future__ import annotations

import pytest
from typer.testing import CliRunner

from crackerjack.cli.audit_cli import app as audit_app
from crackerjack.cli.skills_cli import app as skills_app
from crackerjack.skills import health as skills_health


runner = CliRunner()


@pytest.mark.integration
def test_audit_skills_pipeline_reports_stale_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: stand up a Session-Buddy stub via monkeypatch and verify
    the CLI surfaces the stale count.

    Implementation lands in the follow-up PR. This file ships now so CI
    can pick the marker up and the test is discovered by pytest.
    """
    monkeypatch.setattr(
        "crackerjack.cli.audit_cli.fetch_skill_health",
        lambda **_: skills_health.SkillHealthReport(
            status="stale", stale_count=2, raw_rows=[]
        ),
    )
    result = runner.invoke(audit_app, ["skills", "--json"])
    assert result.exit_code == 0
    assert '"stale_count": 2' in result.output


@pytest.mark.integration
def test_skills_refresh_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: confirm `skills refresh` exits 0 against a stubbed
    Session-Buddy."""
    async def _stub_post_json(url: str, **_: object) -> object:
        return _ok_response(url)

    monkeypatch.setattr(
        "crackerjack.cli.skills_cli._post_json",
        _stub_post_json,
    )
    result = runner.invoke(skills_app, ["refresh"])
    assert result.exit_code == 0


def _ok_response(url: str) -> object:
    """Helper: minimal mock of httpx.Response-shaped return value."""
    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    return _Resp()
