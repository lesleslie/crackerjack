"""Tests for ``crackerjack.mcp.tools.monitoring_tools``.

We exercise the helper functions and registered tool behaviors. External
dependencies (the secure status subsystem, MCP context, async services) are
mocked at the module boundary.
"""

from __future__ import annotations

import asyncio
import json
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.mcp.tools import monitoring_tools
from crackerjack.mcp.tools.monitoring_tools import (
    register_monitoring_tools,
)
from crackerjack.services.secure_status_formatter import StatusVerbosity


# ─── helpers ────────────────────────────────────────────────────────────────


def _run(coro: t.Any) -> t.Any:
    return asyncio.run(coro)


def _captured_tool(name: str) -> t.Any:
    """Return the tool function named ``name`` from the registration."""
    mock_app = MagicMock()
    captured: list[t.Any] = []

    def decorator() -> t.Any:
        def wrap(func: t.Any) -> t.Any:
            captured.append(func)
            return func

        return wrap

    mock_app.tool = decorator  # type: ignore[method-assign]
    register_monitoring_tools(mock_app)
    for fn in captured:
        if fn.__name__ == name:
            return fn
    raise AssertionError(f"{name} not registered")


# ─── _suggest_agent_for_context ─────────────────────────────────────────────


@pytest.mark.unit
class TestSuggestAgentForContext:
    def test_no_state_returns_default_suggestion(self) -> None:
        sm = MagicMock()
        sm.recent_errors = []
        sm.get_stage_status = MagicMock(return_value="completed")
        out = monitoring_tools._suggest_agent_for_context(sm)
        # All stages completed, no errors => architect medium
        assert out["recommended_agent"] == "crackerjack-architect"
        assert out["priority"] == "MEDIUM"

    def test_test_failures_suggests_test_specialist(self) -> None:
        sm = MagicMock()
        sm.recent_errors = []
        sm.get_stage_status = MagicMock(return_value="failed")
        out = monitoring_tools._suggest_agent_for_context(sm)
        assert out["recommended_agent"] == "test-specialist"
        assert out["priority"] == "HIGH"

    def test_security_error_suggests_security_auditor(self) -> None:
        sm = MagicMock()
        sm.recent_errors = ["bandit security warning: ..."]
        sm.get_stage_status = MagicMock(return_value="completed")
        out = monitoring_tools._suggest_agent_for_context(sm)
        assert out["recommended_agent"] == "security-auditor"
        assert "Security issues detected" in out["reason"]

    def test_complexity_error_suggests_architect(self) -> None:
        sm = MagicMock()
        sm.recent_errors = ["complex function detected"]
        sm.get_stage_status = MagicMock(return_value="completed")
        out = monitoring_tools._suggest_agent_for_context(sm)
        assert out["recommended_agent"] == "crackerjack-architect"
        assert "Complexity issues" in out["reason"]


# ─── small helpers ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestErrorResponse:
    def test_error_response(self) -> None:
        out = json.loads(monitoring_tools._create_error_response("oops"))
        assert out["error"] == "oops"
        assert out["success"] is False

    def test_error_response_with_success(self) -> None:
        out = json.loads(
            monitoring_tools._create_error_response("oops", success=True),
        )
        assert out["success"] is True


@pytest.mark.unit
class TestGetStageStatusDict:
    def test_returns_four_stages(self) -> None:
        sm = MagicMock()
        sm.get_stage_status = MagicMock(
            side_effect=lambda s: {
                "fast": "completed",
                "comprehensive": "failed",
                "tests": "completed",
                "cleaning": "completed",
            }[s],
        )
        out = monitoring_tools._get_stage_status_dict(sm)
        assert out == {
            "fast": "completed",
            "comprehensive": "failed",
            "tests": "completed",
            "cleaning": "completed",
        }


@pytest.mark.unit
class TestGetSessionInfo:
    def test_uses_getattr_defaults(self) -> None:
        out = monitoring_tools._get_session_info(MagicMock(spec=[]))
        assert out == {
            "total_iterations": 0,
            "current_iteration": 0,
            "session_active": False,
        }

    def test_uses_attributes_when_present(self) -> None:
        sm = MagicMock()
        sm.iteration_count = 5
        sm.current_iteration = 3
        sm.session_active = True
        out = monitoring_tools._get_session_info(sm)
        assert out == {
            "total_iterations": 5,
            "current_iteration": 3,
            "session_active": True,
        }


# ─── _determine_next_action ────────────────────────────────────────────────


@pytest.mark.unit
class TestDetermineNextAction:
    def test_returns_run_stage_fast_when_incomplete(self) -> None:
        sm = MagicMock()
        sm.get_stage_status = MagicMock(return_value="pending")
        out = _run(monitoring_tools._determine_next_action(sm))
        assert out["recommended_action"] == "run_stage"
        assert out["parameters"]["stage"] == "fast"

    def test_returns_run_stage_tests_when_fast_done(self) -> None:
        sm = MagicMock()
        sm.get_stage_status = MagicMock(
            side_effect=lambda s: {
                "fast": "completed",
                "tests": "pending",
                "comprehensive": "pending",
            }[s],
        )
        out = _run(monitoring_tools._determine_next_action(sm))
        assert out["parameters"]["stage"] == "tests"

    def test_returns_complete_when_all_done(self) -> None:
        sm = MagicMock()
        sm.get_stage_status = MagicMock(return_value="completed")
        out = _run(monitoring_tools._determine_next_action(sm))
        assert out["recommended_action"] == "complete"


# ─── _build_server_stats ───────────────────────────────────────────────────


@pytest.mark.unit
class TestBuildServerStats:
    def test_stats_include_project_path_and_rate_limiting(self, tmp_path: Path) -> None:
        ctx = MagicMock()
        ctx.config.project_path = Path("/p")
        ctx.rate_limiter = None
        ctx.progress_dir = tmp_path
        out = _run(monitoring_tools._build_server_stats(ctx))
        assert out["server_info"]["project_path"] == "/p"
        assert out["rate_limiting"]["enabled"] is False
        assert out["resource_usage"]["temp_files_count"] == 0
        assert "timestamp" in out

    def test_progress_dir_missing(self, tmp_path: Path) -> None:
        ctx = MagicMock()
        ctx.config.project_path = Path("/p")
        ctx.rate_limiter = None
        ctx.progress_dir = tmp_path / "no-such-dir"
        out = _run(monitoring_tools._build_server_stats(ctx))
        assert out["resource_usage"]["temp_files_count"] == 0


# ─── _add_state_manager_stats ──────────────────────────────────────────────


@pytest.mark.unit
class TestAddStateManagerStats:
    def test_no_state_manager(self) -> None:
        stats: dict[str, t.Any] = {}
        monitoring_tools._add_state_manager_stats(stats, None)
        assert "state_manager" not in stats

    def test_with_state_manager(self) -> None:
        sm = MagicMock()
        sm.iteration_count = 4
        sm.session_active = True
        sm.issues = ["a", "b", "c"]
        stats: dict[str, t.Any] = {}
        monitoring_tools._add_state_manager_stats(stats, sm)
        assert stats["state_manager"]["iteration_count"] == 4
        assert stats["state_manager"]["session_active"] is True
        assert stats["state_manager"]["issues_count"] == 3


# ─── _get_active_jobs ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestGetActiveJobs:
    def test_no_progress_dir(self, tmp_path: Path) -> None:
        ctx = MagicMock()
        ctx.progress_dir = tmp_path / "missing"
        out = monitoring_tools._get_active_jobs(ctx)
        assert out == []

    def test_parses_job_files(self, tmp_path: Path) -> None:
        job_file = tmp_path / "job-abc.json"
        job_file.write_text(
            json.dumps(
                {
                    "job_id": "abc",
                    "status": "running",
                    "iteration": 2,
                    "max_iterations": 10,
                    "current_stage": "tests",
                    "overall_progress": 50,
                    "stage_progress": 75,
                    "message": "running",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "error_counts": {"ruff": 1},
                },
            ),
        )
        ctx = MagicMock()
        ctx.progress_dir = tmp_path
        out = monitoring_tools._get_active_jobs(ctx)
        assert len(out) == 1
        assert out[0]["job_id"] == "abc"
        assert out[0]["status"] == "running"
        assert out[0]["stage_progress"] == 75
        assert out[0]["error_counts"] == {"ruff": 1}

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "job-x.json").write_text("{not valid")
        ctx = MagicMock()
        ctx.progress_dir = tmp_path
        out = monitoring_tools._get_active_jobs(ctx)
        assert out == []


# ─── _validate_status_components ────────────────────────────────────────────


@pytest.mark.unit
class TestValidateStatusComponents:
    def test_valid(self) -> None:
        requested, err = monitoring_tools._validate_status_components(
            "services, jobs, resources",
        )
        assert err is None
        assert requested == {"services", "jobs", "resources"}

    def test_invalid_component(self) -> None:
        requested, err = monitoring_tools._validate_status_components(
            "services, foo",
        )
        assert requested == set()
        assert err is not None
        assert "foo" in err

    def test_all_is_valid(self) -> None:
        requested, err = monitoring_tools._validate_status_components("all")
        assert err is None
        assert requested == {"all"}


# ─── _get_services_status ──────────────────────────────────────────────────


@pytest.mark.unit
class TestGetServicesStatus:
    def test_returns_mcp_server_section(self) -> None:
        with patch(
            "crackerjack.services.server_manager.find_mcp_server_processes",
            return_value=[{"pid": 1}],
        ):
            out = monitoring_tools._get_services_status()
        assert out["mcp_server"]["running"] == [{"pid": 1}]
        assert out["mcp_server"]["processes"] == [{"pid": 1}]


# ─── _get_resources_status ─────────────────────────────────────────────────


@pytest.mark.unit
class TestGetResourcesStatus:
    def test_counts_json_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")
        ctx = MagicMock()
        ctx.progress_dir = tmp_path
        out = monitoring_tools._get_resources_status(ctx)
        assert out["temp_files_count"] == 2

    def test_missing_dir_zero(self, tmp_path: Path) -> None:
        ctx = MagicMock()
        ctx.progress_dir = tmp_path / "absent"
        out = monitoring_tools._get_resources_status(ctx)
        assert out["temp_files_count"] == 0


# ─── _build_filtered_status ────────────────────────────────────────────────


@pytest.mark.unit
class TestBuildFilteredStatus:
    def test_includes_services(self) -> None:
        with patch(
            "crackerjack.services.server_manager.find_mcp_server_processes",
            return_value=[],
        ):
            out = _run(
                monitoring_tools._build_filtered_status({"services"}, MagicMock()),
            )
        assert "services" in out
        assert "timestamp" in out

    def test_includes_jobs_and_resources(self, tmp_path: Path) -> None:
        ctx = MagicMock()
        ctx.progress_dir = tmp_path
        with patch(
            "crackerjack.services.server_manager.find_mcp_server_processes",
            return_value=[],
        ):
            out = _run(
                monitoring_tools._build_filtered_status(
                    {"jobs", "resources"}, ctx,
                ),
            )
        assert "jobs" in out
        assert "resources" in out


# ─── Tool: get_stage_status ────────────────────────────────────────────────


@pytest.mark.unit
class TestGetStageStatusTool:
    def test_no_context(self) -> None:
        tool = _captured_tool("get_stage_status")
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=None,
        ):
            out = json.loads(_run(tool()))
        assert out["success"] is False
        assert "Server context" in out["error"]

    def test_no_state_manager(self) -> None:
        tool = _captured_tool("get_stage_status")
        ctx = MagicMock(spec=[])  # no state_manager attribute
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=ctx,
        ):
            out = json.loads(_run(tool()))
        assert out["success"] is False
        assert "State manager" in out["error"]

    def test_success(self) -> None:
        tool = _captured_tool("get_stage_status")
        sm = MagicMock()
        sm.get_stage_status = MagicMock(
            side_effect=lambda s: {
                "fast": "completed",
                "comprehensive": "completed",
                "tests": "completed",
                "cleaning": "completed",
            }[s],
        )
        sm.iteration_count = 1
        sm.current_iteration = 1
        sm.session_active = True
        ctx = MagicMock()
        ctx.state_manager = sm
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=ctx,
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.execute_bounded_status_operation",
            new=AsyncMock(
                return_value={
                    "stages": {"fast": "completed"},
                    "session": {"total_iterations": 1},
                },
            ),
        ):
            out = json.loads(_run(tool()))
        assert "stages" in out

    def test_exception_returns_error(self) -> None:
        tool = _captured_tool("get_stage_status")
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            out = json.loads(_run(tool()))
        parsed = json.loads(out) if isinstance(out, str) else out
        # Output is a string literal from the tool — just check it contains "Failed"
        assert "Failed to get stage status" in out or parsed.get("error")


# ─── Tool: get_next_action ─────────────────────────────────────────────────


@pytest.mark.unit
class TestGetNextActionTool:
    def test_no_context(self) -> None:
        tool = _captured_tool("get_next_action")
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=None,
        ):
            out = json.loads(_run(tool()))
        assert out["success"] is False

    def test_no_state_manager_returns_initialize(self) -> None:
        tool = _captured_tool("get_next_action")
        ctx = MagicMock(spec=[])
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=ctx,
        ):
            out = json.loads(_run(tool()))
        assert out["recommended_action"] == "initialize"

    def test_success(self) -> None:
        tool = _captured_tool("get_next_action")
        sm = MagicMock()
        sm.get_stage_status = MagicMock(return_value="pending")
        ctx = MagicMock()
        ctx.state_manager = sm
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=ctx,
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.execute_bounded_status_operation",
            new=AsyncMock(
                return_value={
                    "recommended_action": "run_stage",
                    "parameters": {"stage": "fast"},
                },
            ),
        ):
            out = json.loads(_run(tool()))
        assert out["recommended_action"] == "run_stage"

    def test_exception(self) -> None:
        tool = _captured_tool("get_next_action")
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(side_effect=RuntimeError("x")),
        ):
            out = _run(tool())
        # The source returns a f-string literal, not JSON, on exception.
        assert "Failed to determine next action" in out


# ─── Tool: get_server_stats ───────────────────────────────────────────────


@pytest.mark.unit
class TestGetServerStatsTool:
    def test_no_context_returns_formatted_error(self) -> None:
        tool = _captured_tool("get_server_stats")

        @asynccontextmanager_noop
        async def _sec():
            yield

        # Patch secure_status_operation to be a no-op async context manager.
        class _CM:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *a: t.Any) -> None:
                return None

        async def _make_sec(*_a: t.Any, **_k: t.Any) -> t.Any:
            return _CM()

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.secure_status_operation",
            new=_make_sec,
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=None,
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_secure_status_formatter",
        ) as mock_fmt:
            mock_fmt.return_value.format_error_response = MagicMock(
                return_value={"error": "no context"},
            )
            out = json.loads(_run(tool()))
        assert "error" in out

    def test_exception_returns_error(self) -> None:
        tool = _captured_tool("get_server_stats")

        class _CM:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *a: t.Any) -> None:
                return None

        async def _make_sec(*_a: t.Any, **_k: t.Any) -> t.Any:
            return _CM()

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(side_effect=RuntimeError("x")),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.secure_status_operation",
            new=_make_sec,
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_secure_status_formatter",
        ) as mock_fmt:
            mock_fmt.return_value.format_error_response = MagicMock(
                return_value={"error": "x"},
            )
            out = json.loads(_run(tool()))
        assert "error" in out


# ─── Tool: get_comprehensive_status ────────────────────────────────────────


@pytest.mark.unit
class TestComprehensiveStatusTool:
    def test_exception(self) -> None:
        tool = _captured_tool("get_comprehensive_status")

        class _CM:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *a: t.Any) -> None:
                return None

        async def _make_sec(*_a: t.Any, **_k: t.Any) -> t.Any:
            return _CM()

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.secure_status_operation",
            new=_make_sec,
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools._get_comprehensive_status_secure",
            new=AsyncMock(side_effect=RuntimeError("x")),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_secure_status_formatter",
        ) as mock_fmt:
            mock_fmt.return_value.format_error_response = MagicMock(
                return_value={"error": "x"},
            )
            out = json.loads(_run(tool()))
        assert "error" in out


# ─── Tool: list_slash_commands ─────────────────────────────────────────────


@pytest.mark.unit
class TestListSlashCommandsTool:
    def test_success(self) -> None:
        tool = _captured_tool("list_slash_commands")
        out = json.loads(_run(tool()))
        assert "available_commands" in out
        # Note: the source has a typo — the keys are "/ crackerjack: ..." (with
        # a leading space) rather than "/crackerjack: ...".
        assert "/ crackerjack: run" in out["available_commands"]
        assert out["total_commands"] == 3

    def test_exception(self) -> None:
        tool = _captured_tool("list_slash_commands")
        # Patch ``json.dumps`` only on the FIRST call.  The source catches
        # the resulting exception and emits its own error response using
        # ``json.dumps`` again — by then we want the patched function to
        # delegate to the real one so the tool returns a valid JSON string.
        real_dumps = json.dumps

        calls = {"n": 0}

        def side_effect(*a: t.Any, **k: t.Any) -> t.Any:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("x")
            # Use the real dumps — note this is the original function
            # captured before patching, so it is NOT itself patched.
            return real_dumps(*a, **k)

        with patch("json.dumps", side_effect=side_effect):
            out = _run(tool())
        assert json.loads(out)["success"] is False
        assert "x" in json.loads(out)["error"]


# ─── Tool: get_filtered_status ─────────────────────────────────────────────


@pytest.mark.unit
class TestGetFilteredStatusTool:
    def test_invalid_components(self) -> None:
        tool = _captured_tool("get_filtered_status")
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_secure_status_formatter",
        ) as mock_fmt:
            mock_fmt.return_value.format_error_response = MagicMock(
                return_value={"error": "Invalid components: {'foo'}"},
            )
            out = json.loads(_run(tool("foo")))
        assert "error" in out

    def test_all_routes_to_comprehensive(self) -> None:
        tool = _captured_tool("get_filtered_status")

        class _CM:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *a: t.Any) -> None:
                return None

        async def _make_sec(*_a: t.Any, **_k: t.Any) -> t.Any:
            return _CM()

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.secure_status_operation",
            new=_make_sec,
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools._get_comprehensive_status_secure",
            new=AsyncMock(return_value={"services": {}, "jobs": []}),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=MagicMock(config=MagicMock(project_path=Path("/p"))),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.format_secure_status",
            return_value={"services": {}},
        ):
            out = json.loads(_run(tool("all")))
        assert "services" in out

    def test_components_routes_to_filtered(self) -> None:
        tool = _captured_tool("get_filtered_status")

        class _CM:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *a: t.Any) -> None:
                return None

        async def _make_sec(*_a: t.Any, **_k: t.Any) -> t.Any:
            return _CM()

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.secure_status_operation",
            new=_make_sec,
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=MagicMock(config=MagicMock(project_path=Path("/p"))),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.execute_bounded_status_operation",
            new=AsyncMock(
                return_value={"timestamp": 1.0, "jobs": {"active": []}},
            ),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.format_secure_status",
            return_value={"timestamp": 1.0, "jobs": {"active": []}},
        ):
            out = json.loads(_run(tool("jobs")))
        assert "jobs" in out

    def test_exception(self) -> None:
        tool = _captured_tool("get_filtered_status")
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(side_effect=RuntimeError("x")),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_secure_status_formatter",
        ) as mock_fmt:
            mock_fmt.return_value.format_error_response = MagicMock(
                return_value={"error": "x"},
            )
            out = json.loads(_run(tool("all")))
        assert "error" in out


# ─── _get_comprehensive_status_secure ───────────────────────────────────────


@pytest.mark.unit
class TestGetComprehensiveStatusSecure:
    def test_auth_fails(self) -> None:
        async def fake() -> dict[str, t.Any]:
            return await monitoring_tools._get_comprehensive_status_secure(
                client_id="c", client_ip="1.1.1.1", auth_header=None,
            )

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.authenticate_status_request",
            new=AsyncMock(side_effect=RuntimeError("auth fail")),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_status_authenticator",
        ) as mock_auth:
            mock_auth.return_value.is_operation_allowed = MagicMock(return_value=True)
            out = _run(fake())
        assert "Authentication failed" in out["error"]

    def test_insufficient_privileges(self) -> None:
        async def fake() -> dict[str, t.Any]:
            return await monitoring_tools._get_comprehensive_status_secure(
                client_id="c", client_ip="1.1.1.1", auth_header=None,
            )

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.authenticate_status_request",
            new=AsyncMock(return_value=MagicMock(access_level=1)),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_status_authenticator",
        ) as mock_auth:
            mock_auth.return_value.is_operation_allowed = MagicMock(return_value=False)
            out = _run(fake())
        assert "Insufficient privileges" in out["error"]

    def test_security_validation_fails(self) -> None:
        async def fake() -> dict[str, t.Any]:
            return await monitoring_tools._get_comprehensive_status_secure(
                client_id="c", client_ip="1.1.1.1", auth_header=None,
            )

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.authenticate_status_request",
            new=AsyncMock(return_value=MagicMock(access_level=10)),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_status_authenticator",
        ) as mock_auth, patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(side_effect=RuntimeError("invalid")),
        ):
            mock_auth.return_value.is_operation_allowed = MagicMock(return_value=True)
            out = _run(fake())
        assert "Security validation failed" in out["error"]

    def test_resource_limit_exceeded(self) -> None:
        async def fake() -> dict[str, t.Any]:
            return await monitoring_tools._get_comprehensive_status_secure(
                client_id="c", client_ip="1.1.1.1", auth_header=None,
            )

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.authenticate_status_request",
            new=AsyncMock(return_value=MagicMock(access_level=10)),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_status_authenticator",
        ) as mock_auth, patch(
            "crackerjack.mcp.tools.monitoring_tools.validate_status_request",
            new=AsyncMock(),
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.execute_bounded_status_operation",
            new=AsyncMock(side_effect=RuntimeError("limit")),
        ):
            mock_auth.return_value.is_operation_allowed = MagicMock(return_value=True)
            out = _run(fake())
        assert "Resource limit exceeded" in out["error"]


# ─── _collect_comprehensive_status_internal ────────────────────────────────


@pytest.mark.unit
class TestCollectComprehensiveStatusInternal:
    def test_returns_snapshot_data(self) -> None:
        snapshot = MagicMock()
        snapshot.services = {"svc": "ok"}
        snapshot.jobs = [{"id": "a"}]
        snapshot.server_stats = {"k": 1}
        snapshot.timestamp = 1.0
        snapshot.collection_duration = 0.5
        snapshot.is_complete = True
        snapshot.errors = []
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_thread_safe_status_collector",
        ) as mock_coll:
            mock_coll.return_value.collect_comprehensive_status = AsyncMock(
                return_value=snapshot,
            )
            with patch(
                "crackerjack.mcp.tools.monitoring_tools.get_context",
                return_value=None,
            ):
                out = _run(
                    monitoring_tools._collect_comprehensive_status_internal(),
                )
        assert out["services"] == {"svc": "ok"}
        assert out["jobs"] == [{"id": "a"}]
        assert out["collection_info"]["is_complete"] is True

    def test_collector_error(self) -> None:
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_thread_safe_status_collector",
        ) as mock_coll:
            mock_coll.return_value.collect_comprehensive_status = AsyncMock(
                side_effect=RuntimeError("boom"),
            )
            out = _run(
                monitoring_tools._collect_comprehensive_status_internal(),
            )
        assert "Failed to collect" in out["error"]

    def test_includes_agent_suggestions_when_state_manager_present(self) -> None:
        snapshot = MagicMock()
        snapshot.services = {}
        snapshot.jobs = []
        snapshot.server_stats = {}
        snapshot.timestamp = 1.0
        snapshot.collection_duration = 0.1
        snapshot.is_complete = True
        snapshot.errors = []
        sm = MagicMock()
        sm.recent_errors = []
        sm.get_stage_status = MagicMock(return_value="completed")
        ctx = MagicMock()
        ctx.state_manager = sm
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_thread_safe_status_collector",
        ) as mock_coll, patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=ctx,
        ):
            mock_coll.return_value.collect_comprehensive_status = AsyncMock(
                return_value=snapshot,
            )
            out = _run(
                monitoring_tools._collect_comprehensive_status_internal(),
            )
        assert "agent_suggestions" in out
        assert out["agent_suggestions"]["recommended_agent"] == "crackerjack-architect"


# ─── _build_server_stats_secure ────────────────────────────────────────────


@pytest.mark.unit
class TestBuildServerStatsSecure:
    def test_includes_security_status(self, tmp_path: Path) -> None:
        ctx = MagicMock()
        ctx.config.project_path = Path("/p")
        ctx.rate_limiter = None
        ctx.progress_dir = tmp_path
        ctx.state_manager = None
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_status_security_manager",
        ) as mock_sec:
            mock_sec.return_value.get_security_status.return_value = {
                "ok": True,
            }
            out = _run(monitoring_tools._build_server_stats_secure(ctx))
        assert "security_status" in out


# ─── module surface ────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRegisterMonitoringTools:
    def test_registers_six_tools(self) -> None:
        mock_app = MagicMock()
        register_monitoring_tools(mock_app)
        assert mock_app.tool.call_count == 6

    def test_registers_expected_names(self) -> None:
        mock_app = MagicMock()
        registered: list[str] = []

        def decorator() -> t.Any:
            def wrap(func: t.Any) -> t.Any:
                registered.append(func.__name__)
                return func

            return wrap

        mock_app.tool = decorator  # type: ignore[method-assign]
        register_monitoring_tools(mock_app)
        for name in (
            "get_stage_status",
            "get_next_action",
            "get_server_stats",
            "get_comprehensive_status",
            "list_slash_commands",
            "get_filtered_status",
        ):
            assert name in registered


# ─── unused / helper stubs ────────────────────────────────────────────────


def asynccontextmanager_noop(func: t.Any) -> t.Any:  # pragma: no cover
    return func
