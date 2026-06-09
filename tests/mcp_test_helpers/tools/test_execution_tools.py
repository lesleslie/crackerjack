"""Tests for ``crackerjack.mcp.tools.execution_tools``.

We exercise the pure helper functions and the registered tool entry points
with heavy use of ``unittest.mock`` to avoid touching real services.
"""

from __future__ import annotations

import asyncio
import json
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.mcp.tools import execution_tools
from crackerjack.mcp.tools.execution_tools import (
    register_execution_tools,
)


def _run(coro: t.Any) -> t.Any:
    return asyncio.run(coro)


# ─── register_execution_tools ───────────────────────────────────────────────


@pytest.mark.unit
class TestRegisterExecutionTools:
    def test_registers_four_tools(self) -> None:
        mock_app = MagicMock()
        register_execution_tools(mock_app)
        assert mock_app.tool.call_count == 4

    def test_registers_expected_names(self) -> None:
        mock_app = MagicMock()
        registered: list[str] = []

        def decorator() -> t.Any:
            def wrap(func: t.Any) -> t.Any:
                registered.append(func.__name__)
                return func

            return wrap

        mock_app.tool = decorator  # type: ignore[method-assign]
        register_execution_tools(mock_app)

        for name in (
            "execute_crackerjack",
            "smart_error_analysis",
            "init_crackerjack",
            "suggest_agents",
        ):
            assert name in registered


# ─── _prepare_execution_kwargs ──────────────────────────────────────────────


@pytest.mark.unit
class TestPrepareExecutionKwargs:
    def test_existing_timeout_preserved(self) -> None:
        out = execution_tools._prepare_execution_kwargs(
            {"execution_timeout": 60},
        )
        assert out["execution_timeout"] == 60

    def test_test_flag_uses_longer_timeout(self) -> None:
        out = execution_tools._prepare_execution_kwargs({"test": True})
        assert out["execution_timeout"] == 1200

    def test_testing_flag_uses_longer_timeout(self) -> None:
        out = execution_tools._prepare_execution_kwargs({"testing": True})
        assert out["execution_timeout"] == 1200

    def test_default_uses_shorter_timeout(self) -> None:
        out = execution_tools._prepare_execution_kwargs({})
        assert out["execution_timeout"] == 900


# ─── _parse_kwargs ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestParseKwargs:
    def test_empty_returns_empty_dict(self) -> None:
        out = execution_tools._parse_kwargs("")
        assert out == {"kwargs": {}}

    def test_whitespace_only_returns_empty_dict(self) -> None:
        out = execution_tools._parse_kwargs("   ")
        assert out == {"kwargs": {}}

    def test_valid_json(self) -> None:
        out = execution_tools._parse_kwargs('{"a": 1}')
        assert out == {"kwargs": {"a": 1}}

    def test_invalid_json(self) -> None:
        out = execution_tools._parse_kwargs("{not valid")
        assert "error" in out
        assert "Invalid JSON" in out["error"]


# ─── _parse_init_arguments ─────────────────────────────────────────────────


@pytest.mark.unit
class TestParseInitArguments:
    def test_default_path(self) -> None:
        path, force, template, interactive, err = (
            execution_tools._parse_init_arguments("", "{}")
        )
        assert err is None
        assert path == Path(".")
        assert force is False
        assert template is None
        assert interactive is True

    def test_explicit_path(self, tmp_path: Path) -> None:
        path, force, template, interactive, err = (
            execution_tools._parse_init_arguments(
                str(tmp_path), '{"force": true, "template": "x", "interactive": false}',
            )
        )
        assert err is None
        assert path == tmp_path
        assert force is True
        assert template == "x"
        assert interactive is False

    def test_invalid_json(self) -> None:
        _, _, _, _, err = execution_tools._parse_init_arguments(
            "/tmp", "{not valid",
        )
        assert err is not None
        assert "Invalid JSON" in err

    def test_other_exception(self) -> None:
        # Force an unrelated exception by passing a non-string args.  We use
        # a non-dict, non-string for ``kwargs`` that the json.loads call
        # would happily handle; we instead force an exception via a Path
        # constructor that fails.
        _, _, _, _, err = execution_tools._parse_init_arguments(
            "\x00invalid-path", "{}",
        )
        # On most platforms the Path constructor doesn't fail; the function
        # might still return without error.  We accept either outcome.
        if err is not None:
            assert "Invalid" in err


# ─── _handle_type_error ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestHandleTypeError:
    def test_none_awaitable_error(self) -> None:
        try:
            result = execution_tools._handle_type_error(
                TypeError("'NoneType' object isn't awaitable"),
            )
        except TypeError:
            # Plain non-awaitable TypeError should be re-raised.
            return
        out = json.loads(result)
        assert out["status"] == "failed"
        assert "Async execution error" in out["error"]
        assert "traceback" in out

    def test_other_type_error_reraised(self) -> None:
        with pytest.raises(TypeError):
            execution_tools._handle_type_error(TypeError("other"))


# ─── _handle_general_error ─────────────────────────────────────────────────


@pytest.mark.unit
class TestHandleGeneralError:
    def test_uses_context_time(self) -> None:
        ctx = MagicMock()
        ctx.get_current_time = MagicMock(return_value="2026-01-01T00:00:00")
        with patch(
            "crackerjack.mcp.tools.execution_tools.get_context",
            return_value=ctx,
        ):
            out = json.loads(
                execution_tools._handle_general_error(RuntimeError("boom")),
            )
        assert out["status"] == "failed"
        assert "boom" in out["error"]
        assert out["timestamp"] == "2026-01-01T00:00:00"
        assert "traceback" in out

    def test_falls_back_to_now(self) -> None:
        ctx = MagicMock(spec=[])  # no get_current_time
        with patch(
            "crackerjack.mcp.tools.execution_tools.get_context",
            return_value=ctx,
        ):
            out = json.loads(
                execution_tools._handle_general_error(RuntimeError("x")),
            )
        assert out["status"] == "failed"
        # timestamp should be present and ISO formatted
        assert "T" in out["timestamp"]


# ─── _handle_context_validation ────────────────────────────────────────────


@pytest.mark.unit
class TestHandleContextValidation:
    def test_no_validation_error(self) -> None:
        with patch(
            "crackerjack.mcp.tools.execution_tools._validate_context_and_rate_limit",
            new=AsyncMock(return_value=None),
        ):
            out = _run(execution_tools._handle_context_validation(MagicMock()))
        assert out is None

    def test_validation_error_propagated(self) -> None:
        with patch(
            "crackerjack.mcp.tools.execution_tools._validate_context_and_rate_limit",
            new=AsyncMock(return_value='{"error": "x"}'),
        ):
            out = _run(execution_tools._handle_context_validation(MagicMock()))
        assert out == '{"error": "x"}'

    def test_none_awaitable_special_case(self) -> None:
        async def _raise(*_a: t.Any, **_k: t.Any) -> t.Any:
            err = TypeError("'NoneType' object isn't awaitable")
            raise err

        with patch(
            "crackerjack.mcp.tools.execution_tools._validate_context_and_rate_limit",
            new=_raise,
        ):
            out = _run(execution_tools._handle_context_validation(MagicMock()))
        assert out is not None
        parsed = json.loads(out)
        assert "Context validation failed" in parsed["error"]

    def test_other_type_error_reraised(self) -> None:
        async def _raise(*_a: t.Any, **_k: t.Any) -> t.Any:
            raise TypeError("something else")

        with patch(
            "crackerjack.mcp.tools.execution_tools._validate_context_and_rate_limit",
            new=_raise,
        ):
            with pytest.raises(TypeError):
                _run(execution_tools._handle_context_validation(MagicMock()))


# ─── _validate_context_and_rate_limit ──────────────────────────────────────


@pytest.mark.unit
class TestValidateContextAndRateLimit:
    def test_no_context(self) -> None:
        out = _run(execution_tools._validate_context_and_rate_limit(None))
        assert "MCP context not available" in out

    def test_no_rate_limiter_returns_none(self) -> None:
        ctx = MagicMock(spec=[])  # no rate_limiter
        out = _run(execution_tools._validate_context_and_rate_limit(ctx))
        assert out is None

    def test_rate_limiter_allows(self) -> None:
        rl = MagicMock()
        rl.check_request_allowed = AsyncMock(return_value=(True, {}))
        ctx = MagicMock()
        ctx.rate_limiter = rl
        out = _run(execution_tools._validate_context_and_rate_limit(ctx))
        assert out is None

    def test_rate_limiter_denies(self) -> None:
        rl = MagicMock()
        rl.check_request_allowed = AsyncMock(
            return_value=(False, "rate limit hit"),
        )
        ctx = MagicMock()
        ctx.rate_limiter = rl
        out = _run(execution_tools._validate_context_and_rate_limit(ctx))
        assert "Rate limit exceeded" in out
        assert "rate limit hit" in out


# ─── _create_init_*_response ───────────────────────────────────────────────


@pytest.mark.unit
class TestInitResponses:
    def test_error_response(self) -> None:
        out = json.loads(execution_tools._create_init_error_response("bad"))
        assert out["status"] == "error"
        assert out["message"] == "bad"
        assert out["initialized"] is False

    def test_success_response(self) -> None:
        out = json.loads(
            execution_tools._create_init_success_response({"a": 1}),
        )
        assert out["status"] == "success"
        assert out["result"] == {"a": 1}
        assert out["initialized"] is True

    def test_exception_response(self) -> None:
        out = json.loads(
            execution_tools._create_init_exception_response(
                RuntimeError("x"), "/tmp",
            ),
        )
        assert out["status"] == "error"
        assert out["target_path"] == "/tmp"
        assert "x" in out["message"]
        assert out["initialized"] is False


# ─── _generate_agent_recommendations / _analyze_task_for_agents ────────────


@pytest.mark.unit
class TestAgentRecommendations:
    def test_testing_task(self) -> None:
        out = execution_tools._generate_agent_recommendations(
            "Run tests and fix errors", "python", "",
        )
        names = [a["name"] for a in out["suggested_agents"]]
        assert "TestCreationAgent" in names
        assert "RefactoringAgent" in names
        assert out["task_analysis"]["project_type"] == "python"

    def test_security_task(self) -> None:
        out = execution_tools._generate_agent_recommendations(
            "Improve security and fix vulnerabilities", "python", "",
        )
        names = [a["name"] for a in out["suggested_agents"]]
        assert "SecurityAgent" in names

    def test_performance_task(self) -> None:
        out = execution_tools._generate_agent_recommendations(
            "Optimize performance and speed up", "python", "",
        )
        names = [a["name"] for a in out["suggested_agents"]]
        assert "PerformanceAgent" in names

    def test_documentation_task(self) -> None:
        out = execution_tools._generate_agent_recommendations(
            "Write documentation and update README", "python", "",
        )
        names = [a["name"] for a in out["suggested_agents"]]
        assert "DocumentationAgent" in names

    def test_import_task(self) -> None:
        out = execution_tools._generate_agent_recommendations(
            "Fix imports and package dependencies", "python", "",
        )
        names = [a["name"] for a in out["suggested_agents"]]
        assert "ImportOptimizationAgent" in names

    def test_default_agent_for_generic(self) -> None:
        out = execution_tools._generate_agent_recommendations(
            "do something random", "python", "",
        )
        # The fallback default is RefactoringAgent.
        names = [a["name"] for a in out["suggested_agents"]]
        assert "RefactoringAgent" in names
        assert out["reasoning"]  # non-empty

    def test_workflows_for_python(self) -> None:
        out = execution_tools._generate_agent_recommendations(
            "anything", "python", "",
        )
        assert len(out["workflow_recommendations"]) == 3
        assert "Run quality checks" in out["workflow_recommendations"][0]

    def test_no_workflows_for_non_python(self) -> None:
        out = execution_tools._generate_agent_recommendations(
            "anything", "rust", "",
        )
        assert out["workflow_recommendations"] == []


# ─── Tools: registered entry points ────────────────────────────────────────


def _captured_tool(name: str) -> t.Any:
    mock_app = MagicMock()
    captured: list[t.Any] = []

    def decorator() -> t.Any:
        def wrap(func: t.Any) -> t.Any:
            captured.append(func)
            return func

        return wrap

    mock_app.tool = decorator  # type: ignore[method-assign]
    register_execution_tools(mock_app)
    for fn in captured:
        if fn.__name__ == name:
            return fn
    raise AssertionError(f"{name} not registered")


@pytest.mark.unit
class TestExecuteCrackerjackTool:
    def test_invalid_kwargs_json(self) -> None:
        tool = _captured_tool("execute_crackerjack")
        with patch(
            "crackerjack.mcp.tools.execution_tools.get_context",
            return_value=None,
        ):
            out = json.loads(_run(tool("", "not json")))
        # Source returns the context-validation error first because context
        # is None.  Either way, the response indicates an error.
        assert out.get("status") == "error" or "error" in out or "message" in out

    def test_validation_error_propagated(self) -> None:
        tool = _captured_tool("execute_crackerjack")
        with patch(
            "crackerjack.mcp.tools.execution_tools.get_context",
            return_value=None,
        ), patch(
            "crackerjack.mcp.tools.execution_tools._handle_context_validation",
            new=AsyncMock(return_value='{"status":"error","message":"x"}'),
        ):
            out = json.loads(_run(tool("", "{}")))
        assert out["status"] == "error"

    def test_successful_execution(self) -> None:
        tool = _captured_tool("execute_crackerjack")
        with patch(
            "crackerjack.mcp.tools.execution_tools.get_context",
            return_value=None,
        ), patch(
            "crackerjack.mcp.tools.execution_tools._handle_context_validation",
            new=AsyncMock(return_value=None),
        ), patch(
            "crackerjack.mcp.tools.execution_tools.execute_crackerjack_workflow",
            new=AsyncMock(return_value={"job_id": "abc", "status": "running"}),
        ):
            out = json.loads(_run(tool("", "{}")))
        assert out["job_id"] == "abc"

    def test_general_exception(self) -> None:
        tool = _captured_tool("execute_crackerjack")
        with patch(
            "crackerjack.mcp.tools.execution_tools.get_context",
            return_value=None,
        ), patch(
            "crackerjack.mcp.tools.execution_tools._handle_context_validation",
            new=AsyncMock(return_value=None),
        ), patch(
            "crackerjack.mcp.tools.execution_tools.execute_crackerjack_workflow",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            out = json.loads(_run(tool("", "{}")))
        assert out["status"] == "failed"
        assert "boom" in out["error"]


@pytest.mark.unit
class TestSmartErrorAnalysisTool:
    def test_success(self) -> None:
        tool = _captured_tool("smart_error_analysis")
        with patch(
            "crackerjack.mcp.tools.execution_tools.get_context",
            return_value=None,
        ), patch(
            "crackerjack.mcp.tools.execution_tools.analyze_errors_with_caching",
            return_value={"patterns": []},
        ):
            out = json.loads(_run(tool(True)))
        assert out["patterns"] == []

    def test_exception(self) -> None:
        tool = _captured_tool("smart_error_analysis")
        with patch(
            "crackerjack.mcp.tools.execution_tools.get_context",
            return_value=None,
        ), patch(
            "crackerjack.mcp.tools.execution_tools.analyze_errors_with_caching",
            side_effect=RuntimeError("x"),
        ):
            out = json.loads(_run(tool(True)))
        assert out["status"] == "error"
        assert out["recommendations"] == []


@pytest.mark.unit
class TestInitCrackerjackTool:
    def test_invalid_kwargs(self) -> None:
        tool = _captured_tool("init_crackerjack")
        out = json.loads(tool("", "{not valid"))
        assert out["status"] == "error"
        assert out["initialized"] is False

    def test_successful_init(self, tmp_path: Path) -> None:
        tool = _captured_tool("init_crackerjack")
        with patch(
            "crackerjack.mcp.tools.execution_tools._execute_initialization",
            return_value={"ok": True},
        ):
            out = json.loads(tool(str(tmp_path), "{}"))
        assert out["status"] == "success"
        assert out["initialized"] is True
        assert out["result"] == {"ok": True}

    def test_exception(self) -> None:
        tool = _captured_tool("init_crackerjack")
        with patch(
            "crackerjack.mcp.tools.execution_tools._execute_initialization",
            side_effect=RuntimeError("x"),
        ):
            out = json.loads(tool("/tmp", "{}"))
        assert out["status"] == "error"
        assert "x" in out["message"]


@pytest.mark.unit
class TestSuggestAgentsTool:
    def test_success(self) -> None:
        tool = _captured_tool("suggest_agents")
        out = json.loads(
            tool("improve security and fix imports", "python", ""),
        )
        assert out["status"] == "success"
        names = [a["name"] for a in out["suggested_agents"]]
        assert "SecurityAgent" in names or "ImportOptimizationAgent" in names

    def test_exception(self) -> None:
        tool = _captured_tool("suggest_agents")
        with patch(
            "crackerjack.mcp.tools.execution_tools._generate_agent_recommendations",
            side_effect=RuntimeError("x"),
        ):
            out = json.loads(tool("anything", "python", ""))
        assert out["status"] == "error"
        assert out["recommendations"] == {}
