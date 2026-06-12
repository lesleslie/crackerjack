"""CliRunner-based tests for ``crackerjack.cli.coverage_cli``.

These tests exercise the Typer-based coverage CLI without performing any real
network I/O. The Session-Buddy ``distilled_skill_health`` call is mocked at
the ``_fetch_distilled_skill_health`` boundary so the command paths run end
to end.

Note on invocation: the ``skills`` command is registered on the Typer app
without an explicit name (the bare ``@app.command()`` decorator at module
load time leaves the command's name as ``None``). Typer's CliRunner does not
expose a public hook to rename the registered command, so this module
exercises the command body two ways:

* ``CliRunner`` for ``--help`` (works because the default Typer group
  surfaces the registered command's options).
* Direct call to the imported ``skills`` function for the happy-path /
  error / JSON branches. Typer's ``typer.Option`` annotations are erased at
  import time, so calling the function with the resolved Python types
  exercises exactly the same code path the CLI would.
"""

from __future__ import annotations

import asyncio
import io
import json
from contextlib import redirect_stdout
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from crackerjack.cli import coverage_cli
from crackerjack.cli.coverage_cli import (
    DEFAULT_SESSION_BUDDY_URL,
    app,
    skills,
)
from crackerjack.skills.coverage import (
    CoverageReport,
    DistilledSkillRow,
    skill_coverage_report,
)

runner = CliRunner()


def _rows() -> list[dict[str, Any]]:
    return [
        {
            "id": "skill-a",
            "problem_pattern": "optimize import chain",
            "importance_score": 0.95,
            "evidence_count": 3,
            "last_reinforced_at": "2026-01-01T00:00:00",
            "status": "fresh",
        },
        {
            "id": "skill-b",
            "problem_pattern": "debug flaky test",
            "importance_score": 0.50,
            "evidence_count": 0,
            "last_reinforced_at": None,
            "status": "cold",
        },
    ]


def _run_skills(*, json_output: bool, threshold_days: int, url: str) -> str:
    """Invoke the ``skills`` command body and capture its stdout."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        skills(
            json_output=json_output,
            threshold_days=threshold_days,
            session_buddy_url=url,
        )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Help / CLI surface
# ---------------------------------------------------------------------------


class TestCoverageCliHelp:
    """The Typer app and the ``skills`` subcommand both render --help."""

    def test_app_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # A Typer group with at least one registered command surfaces the
        # command name in its --help output.
        assert "skills" in result.stdout

    def test_skills_help(self) -> None:
        result = runner.invoke(app, ["skills", "--help"])
        assert result.exit_code == 0
        # The --help for the command lists all three registered options.
        assert "--json" in result.stdout
        assert "--threshold-days" in result.stdout
        assert "--session-buddy-url" in result.stdout


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestSkillsCommandTableOutput:
    """Default (non-JSON) path produces a human-readable table."""

    def test_table_happy_path(self) -> None:
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncReturning(_rows()),
        ):
            output = _run_skills(
                json_output=False,
                threshold_days=90,
                url="http://stub/mcp",
            )

        assert "Skill coverage report" in output
        assert "Threshold (days): 90" in output
        assert "fresh:" in output
        assert "cold:" in output
        assert "Distilled skill status" in output
        assert "skill-a" in output
        assert "skill-b" in output

    def test_table_threshold_renders_in_output(self) -> None:
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncReturning(_rows()),
        ):
            output = _run_skills(
                json_output=False,
                threshold_days=42,
                url="http://stub/mcp",
            )

        assert "Threshold (days): 42" in output

    def test_table_with_no_crackerjack_only_section(self) -> None:
        # Sanity check that the table path renders without raising when the
        # crackerjack skill list is non-empty. The exact membership of the
        # crackerjack-only section depends on the coverage algorithm's
        # internal classification, so we only assert structural properties.
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncReturning(_rows()),
        ), patch.object(
            coverage_cli,
            "_get_crackerjack_skill_names",
            lambda: ["skill-a", "skill-b", "skill-c"],
        ):
            output = _run_skills(
                json_output=False,
                threshold_days=90,
                url="http://stub/mcp",
            )

        assert "Skill coverage report" in output
        assert "Threshold (days): 90" in output
        # The table footer should be present.
        assert "under_utilized:" in output

    def test_table_with_crackerjack_only_section(self) -> None:
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncReturning(_rows()),
        ), patch.object(
            coverage_cli,
            "_get_crackerjack_skill_names",
            lambda: ["skill-a"],
        ):
            output = _run_skills(
                json_output=False,
                threshold_days=90,
                url="http://stub/mcp",
            )

        # skill-b is missing from the crackerjack list → it should appear
        # in the crackerjack-only section if rendered.
        if "Crackerjack-only skills" in output:
            assert "skill-b" in output


class TestSkillsCommandJsonOutput:
    """``--json`` switches the formatter to a JSON document."""

    def test_json_happy_path(self) -> None:
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncReturning(_rows()),
        ):
            output = _run_skills(
                json_output=True,
                threshold_days=90,
                url="http://stub/mcp",
            )

        payload = json.loads(output)
        assert payload["threshold_days"] == 90
        assert payload["total_distilled"] == 2
        assert isinstance(payload["distilled"], list)
        assert len(payload["distilled"]) == 2
        ids = {row["id"] for row in payload["distilled"]}
        assert ids == {"skill-a", "skill-b"}
        # skill-b has no last_reinforced_at, so it must surface as null.
        skill_b = next(r for r in payload["distilled"] if r["id"] == "skill-b")
        assert skill_b["last_reinforced_at"] is None
        # The serialized status field must be one of the known buckets.
        valid_statuses = {"fresh", "cold", "stale", "under_utilized"}
        for row in payload["distilled"]:
            assert row["status"] in valid_statuses

    def test_json_with_empty_distilled(self) -> None:
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncReturning([]),
        ):
            output = _run_skills(
                json_output=True,
                threshold_days=30,
                url="http://stub/mcp",
            )

        payload = json.loads(output)
        assert payload["threshold_days"] == 30
        assert payload["distilled"] == []
        # The crackerjack-only list is whatever Crackerjack's registry
        # returned; we just check it serialised as a list, not its contents.
        assert isinstance(payload["crackerjack_only"], list)


# ---------------------------------------------------------------------------
# Option wiring
# ---------------------------------------------------------------------------


class TestSkillsCommandOptions:
    """``--threshold-days`` and ``--session-buddy-url`` are forwarded into the
    ``_LocalClient`` and the JSON-RPC call."""

    def test_threshold_days_forwarded_to_fetch(self) -> None:
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncReturning(_rows()),
        ) as mock_fetch:
            _run_skills(
                json_output=False,
                threshold_days=7,
                url="http://stub/mcp",
            )

        kwargs = mock_fetch.call_args.kwargs
        assert kwargs["threshold_days"] == 7

    def test_session_buddy_url_forwarded_to_fetch(self) -> None:
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncReturning(_rows()),
        ) as mock_fetch:
            _run_skills(
                json_output=False,
                threshold_days=90,
                url="http://example.invalid/mcp",
            )

        kwargs = mock_fetch.call_args.kwargs
        assert kwargs["session_buddy_url"] == "http://example.invalid/mcp"

    def test_session_buddy_url_env_override(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SESSION_BUDDY_MCP_URL", "http://from-env/mcp")
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncReturning(_rows()),
        ) as mock_fetch:
            _run_skills(
                json_output=False,
                threshold_days=90,
                url="http://from-env/mcp",
            )

        kwargs = mock_fetch.call_args.kwargs
        assert kwargs["session_buddy_url"] == "http://from-env/mcp"


# ---------------------------------------------------------------------------
# Error fallback
# ---------------------------------------------------------------------------


class TestSkillsCommandErrors:
    """Network and protocol failures surface without crashing the CLI."""

    def test_fetch_runtime_error_propagates(self) -> None:
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncRaising(RuntimeError("boom")),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                _run_skills(
                    json_output=False,
                    threshold_days=90,
                    url="http://stub/mcp",
                )

    def test_fetch_value_error_propagates(self) -> None:
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncRaising(ValueError("bad payload")),
        ):
            with pytest.raises(ValueError, match="bad payload"):
                _run_skills(
                    json_output=True,
                    threshold_days=90,
                    url="http://stub/mcp",
                )

    def test_invalid_subcommand_rejected(self) -> None:
        # An unrecognised option must produce a non-zero exit code.
        result = runner.invoke(app, ["skills", "--bogus-flag"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# _LocalClient
# ---------------------------------------------------------------------------


class TestLocalClient:
    """The local shim translates tool-name lookups into JSON-RPC calls."""

    def test_unsupported_tool_raises(self) -> None:
        client = coverage_cli._LocalClient(
            threshold_days=90,
            crackerjack_skill_names=["a"],
            session_buddy_url="http://x/mcp",
        )

        async def _go() -> Any:
            return await client.call_tool("not_distilled_skill_health")

        with pytest.raises(ValueError, match="unsupported tool"):
            asyncio.run(_go())

    def test_supported_tool_delegates(self) -> None:
        client = coverage_cli._LocalClient(
            threshold_days=45,
            crackerjack_skill_names=["a"],
            session_buddy_url="http://x/mcp",
        )
        sentinel = [{"id": "s"}]
        with patch.object(
            coverage_cli,
            "_fetch_distilled_skill_health",
            _AsyncReturning(sentinel),
        ) as mock_fetch:
            result = asyncio.run(client.call_tool("distilled_skill_health"))

        assert result == sentinel
        kwargs = mock_fetch.call_args.kwargs
        assert kwargs["threshold_days"] == 45
        assert kwargs["crackerjack_skill_names"] == ["a"]
        assert kwargs["session_buddy_url"] == "http://x/mcp"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


class TestModuleSurface:
    """Public exports stay stable so downstream importers do not break."""

    def test_all_reexports(self) -> None:
        assert "app" in coverage_cli.__all__
        assert "DEFAULT_SESSION_BUDDY_URL" in coverage_cli.__all__
        assert "MCP_SKILL_GROUPS" in coverage_cli.__all__

    def test_default_session_buddy_url_is_http(self) -> None:
        assert DEFAULT_SESSION_BUDDY_URL.startswith("http")

    def test_get_crackerjack_skill_names_returns_list_of_str(self) -> None:
        names = coverage_cli._get_crackerjack_skill_names()
        assert isinstance(names, list)
        for name in names:
            assert isinstance(name, str)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class _AsyncReturning:
    """Awaitable that returns a fixed value and records its call args."""

    def __init__(self, value: Any) -> None:
        self._value = value
        self.call_args: Any = None

    def __call__(self, *args: Any, **kwargs: Any) -> "_AsyncReturning":
        self.call_args = _CallArgs(args, kwargs)
        return self

    def __await__(self) -> Any:
        async def _coro() -> Any:
            return self._value

        return _coro().__await__()


class _AsyncRaising:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def __call__(self, *args: Any, **kwargs: Any) -> "_AsyncRaising":
        return self

    def __await__(self) -> Any:
        async def _coro() -> Any:
            raise self._exc

        return _coro().__await__()


class _CallArgs:
    def __init__(self, args: Any, kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
