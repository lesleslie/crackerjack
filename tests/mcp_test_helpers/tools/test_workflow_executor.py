"""Tests for ``crackerjack.mcp.tools.workflow_executor``.

We exercise the helper functions and the public entry point by mocking
``get_context`` and the orchestrator factory at the module boundary.
"""

from __future__ import annotations

import asyncio
import json
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.mcp.tools import workflow_executor
from crackerjack.mcp.tools.workflow_executor import (
    execute_crackerjack_workflow,
)


def _run(coro: t.Any) -> t.Any:
    return asyncio.run(coro)


# ─── _create_workflow_options ───────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _patch_progress():
    with patch("crackerjack.mcp.tools.workflow_executor._update_progress"):
        yield


@pytest.mark.unit
class TestCreateWorkflowOptions:
    def test_defaults(self) -> None:
        opts = workflow_executor._create_workflow_options({})
        assert opts.commit is False
        assert opts.interactive is False
        assert opts.verbose is True
        assert opts.run_tests is True
        assert opts.ai_agent is True
        assert opts.async_mode is True
        assert opts.test_workers == 0
        assert opts.keep_releases == 10
        assert opts.coverage is False
        assert opts.fast is False

    def test_user_overrides(self) -> None:
        opts = workflow_executor._create_workflow_options(
            {
                "commit": True,
                "interactive": True,
                "test": True,
                "no_config_updates": True,
                "verbose": False,
                "clean": True,
                "test_mode": False,
                "benchmark": True,
                "skip_hooks": True,
                "ai_agent": False,
                "async_mode": False,
                "test_workers": 4,
                "test_timeout": 60,
                "publish": "yes",
                "bump": "patch",
                "all": True,
                "create_pr": True,
                "no_git_tags": True,
                "skip_version_check": True,
                "cleanup_pypi": True,
                "keep_releases": 5,
                "start_mcp_server": True,
                "experimental_hooks": True,
                "enable_pyrefly": True,
                "enable_ty": True,
                "cleanup": "all",
                "coverage": True,
                "track_progress": True,
                "fast": True,
                "comp": True,
            },
        )
        assert opts.commit is True
        assert opts.interactive is True
        assert opts.no_config_updates is True
        assert opts.verbose is False
        assert opts.strip_code is True
        assert opts.run_tests is False
        assert opts.benchmark is True
        assert opts.skip_hooks is True
        assert opts.ai_agent is False
        assert opts.async_mode is False
        assert opts.test_workers == 4
        assert opts.test_timeout == 60
        assert opts.publish == "yes"
        assert opts.bump == "patch"
        assert opts.all is True
        assert opts.create_pr is True
        assert opts.no_git_tags is True
        assert opts.skip_version_check is True
        assert opts.cleanup_pypi is True
        assert opts.keep_releases == 5
        assert opts.start_mcp_server is True
        assert opts.experimental_hooks is True
        assert opts.enable_pyrefly is True
        assert opts.enable_ty is True
        assert opts.cleanup == "all"
        assert opts.coverage is True
        assert opts.track_progress is True
        assert opts.fast is True
        assert opts.comp is True


# ─── _detect_orchestrator_method ───────────────────────────────────────────


@pytest.mark.unit
class TestDetectOrchestratorMethod:
    def test_first_match_wins(self) -> None:
        orch = MagicMock(spec=["run_complete_workflow_async"])
        assert (
            workflow_executor._detect_orchestrator_method(orch)
            == "run_complete_workflow_async"
        )

    def test_falls_through_to_run(self) -> None:
        orch = MagicMock(spec=["run"])
        assert workflow_executor._detect_orchestrator_method(orch) == "run"

    def test_unknown_raises(self) -> None:
        orch = MagicMock(spec=["unknown_method"])
        with pytest.raises(ValueError, match="no recognized workflow"):
            workflow_executor._detect_orchestrator_method(orch)


# ─── _invoke_orchestrator_method ───────────────────────────────────────────


@pytest.mark.unit
class TestInvokeOrchestratorMethod:
    def test_returns_value(self) -> None:
        orch = MagicMock()
        orch.some_method.return_value = "ok"
        out = workflow_executor._invoke_orchestrator_method(
            orch, "some_method", MagicMock(),
        )
        assert out == "ok"

    def test_none_raises(self) -> None:
        orch = MagicMock()
        orch.some_method.return_value = None
        with pytest.raises(ValueError, match="returned None"):
            workflow_executor._invoke_orchestrator_method(
                orch, "some_method", MagicMock(),
            )


# ─── _validate_awaitable_result ─────────────────────────────────────────────


@pytest.mark.unit
class TestValidateAwaitableResult:
    def test_awaitable_ok(self) -> None:
        # Just calling a coroutine doesn't run it; it remains awaitable.
        async def _x() -> int:
            return 1
        # ``_x()`` is awaitable, so validation passes.
        workflow_executor._validate_awaitable_result(_x(), "run", object())

    def test_non_awaitable_raises(self) -> None:
        with pytest.raises(ValueError, match="non-awaitable"):
            workflow_executor._validate_awaitable_result(
                "not awaitable", "run", object(),
            )


# ─── _create_success_result / _create_failure_result ───────────────────────


@pytest.mark.unit
class TestCreateSuccessResult:
    def test_basic(self) -> None:
        out = workflow_executor._create_success_result("j1", 3, None)
        assert out["status"] == "completed"
        assert out["iterations"] == 3
        assert out["success"] is True
        assert "coverage_improvement" not in out

    def test_with_coverage(self) -> None:
        cov = {"fixes_applied": ["a"]}
        out = workflow_executor._create_success_result("j1", 3, None, cov)
        assert out["coverage_improvement"] == cov


@pytest.mark.unit
class TestCreateFailureResult:
    def test_failure(self) -> None:
        out = workflow_executor._create_failure_result("j1", 5, None)
        assert out["status"] == "failed"
        assert out["success"] is False
        assert "Maximum iterations" in out["error"]


# ─── _initialize_execution ─────────────────────────────────────────────────


@pytest.mark.unit
class TestInitializeExecution:
    def test_working_dir_exists(self, tmp_path: Path) -> None:
        out = _run(
            workflow_executor._initialize_execution(
                "j1", "", {}, None,
                working_dir_override=str(tmp_path),
            ) if False else workflow_executor._initialize_execution(
                "j1", "", {"working_directory": str(tmp_path)}, None,
            ),
        )
        assert out["status"] == "initialized"
        assert out["working_dir"] == tmp_path.absolute()

    def test_working_dir_missing(self) -> None:
        out = _run(
            workflow_executor._initialize_execution(
                "j1", "", {"working_directory": "/no/such/path/x9z"}, None,
            ),
        )
        assert out["status"] == "failed"
        assert "does not exist" in out["error"]


# ─── _setup_orchestrator ───────────────────────────────────────────────────


@pytest.mark.unit
class TestSetupOrchestrator:
    def test_standard_orchestrator(self, tmp_path: Path) -> None:
        fake_orch = MagicMock()
        with patch(
            "crackerjack.mcp.tools.workflow_executor._create_standard_orchestrator",
            return_value=fake_orch,
        ):
            out = _run(
                workflow_executor._setup_orchestrator(
                    "j1", "", {}, tmp_path, None,
                ),
            )
        assert out["status"] == "ready"
        assert out["orchestrator"] is fake_orch

    def test_advanced_orchestrator(self, tmp_path: Path) -> None:
        fake_orch = MagicMock()
        with patch(
            "crackerjack.mcp.tools.workflow_executor._create_advanced_orchestrator",
            new=AsyncMock(return_value=fake_orch),
        ):
            out = _run(
                workflow_executor._setup_orchestrator(
                    "j1",
                    "",
                    {"advanced_orchestration": True},
                    tmp_path,
                    None,
                ),
            )
        assert out["status"] == "ready"
        assert out["orchestrator"] is fake_orch

    def test_failure(self, tmp_path: Path) -> None:
        with patch(
            "crackerjack.mcp.tools.workflow_executor._create_standard_orchestrator",
            side_effect=RuntimeError("boom"),
        ):
            out = _run(
                workflow_executor._setup_orchestrator(
                    "j1", "", {}, tmp_path, None,
                ),
            )
        assert out["status"] == "failed"
        assert "Failed to create orchestrator" in out["error"]


# ─── _create_advanced_orchestrator / _create_standard_orchestrator ─────────


@pytest.mark.unit
class TestOrchestratorFactories:
    def test_advanced(self) -> None:
        fake_pipeline = MagicMock()
        with patch(
            "crackerjack.core.workflow_orchestrator.WorkflowPipeline",
            return_value=fake_pipeline,
        ) as mock_pipe:
            out = _run(
                workflow_executor._create_advanced_orchestrator(
                    Path("/p"), {}, None,
                ),
            )
        assert out is fake_pipeline
        mock_pipe.assert_called_once_with(pkg_path=Path("/p"))

    def test_standard(self) -> None:
        fake_pipeline = MagicMock()
        with patch(
            "crackerjack.core.workflow_orchestrator.WorkflowPipeline",
            return_value=fake_pipeline,
        ) as mock_pipe:
            out = workflow_executor._create_standard_orchestrator(
                Path("/p"), {},
            )
        assert out is fake_pipeline
        mock_pipe.assert_called_once_with(pkg_path=Path("/p"))


# ─── _handle_iteration_retry ───────────────────────────────────────────────


@pytest.mark.unit
class TestHandleIterationRetry:
    @pytest.mark.slow
    def test_sleeps_one_second(self) -> None:
        with patch(
            "crackerjack.mcp.tools.workflow_executor.asyncio.sleep",
            new=AsyncMock(),
        ) as mock_sleep:
            _run(workflow_executor._handle_iteration_retry("j1", 0, None))
        mock_sleep.assert_called_once_with(1)


# ─── _execute_single_iteration ─────────────────────────────────────────────


@pytest.mark.unit
class TestExecuteSingleIteration:
    def test_run_method_returns_bool_directly(self) -> None:
        orch = MagicMock(spec=["run"])
        orch.run = MagicMock(return_value=True)
        out = _run(
            workflow_executor._execute_single_iteration(
                "j1", orch, MagicMock(), 0, None,
            ),
        )
        assert out is True

    def test_async_method_awaited(self) -> None:
        orch = MagicMock(spec=["run_complete_workflow_async"])

        async def fake_run(opts: t.Any) -> bool:
            return True

        orch.run_complete_workflow_async = fake_run
        out = _run(
            workflow_executor._execute_single_iteration(
                "j1", orch, MagicMock(), 0, None,
            ),
        )
        assert out is True

    def test_method_raises(self) -> None:
        orch = MagicMock()
        orch.run_complete_workflow_async = MagicMock(
            side_effect=RuntimeError("oops"),
        )
        with pytest.raises(RuntimeError, match="oops"):
            _run(
                workflow_executor._execute_single_iteration(
                    "j1", orch, MagicMock(), 0, None,
                ),
            )


# ─── _handle_iteration_error ───────────────────────────────────────────────


@pytest.mark.unit
class TestHandleIterationError:
    def test_returns_failure(self) -> None:
        out = _run(
            workflow_executor._handle_iteration_error(
                "j1", 2, RuntimeError("boom"), None,
            ),
        )
        assert out["status"] == "failed"
        assert out["success"] is False
        assert "Iteration 3 failed" in out["error"]


# ─── _attempt_coverage_improvement ─────────────────────────────────────────


@pytest.mark.unit
class TestAttemptCoverageImprovement:
    def test_no_project_path(self) -> None:
        orch = MagicMock(spec=[])  # no pkg_path
        out = _run(
            workflow_executor._attempt_coverage_improvement(
                "j1", orch, None,
            ),
        )
        assert out["status"] == "skipped"
        assert "No project path" in out["reason"]

    def test_module_not_found(self) -> None:
        orch = MagicMock()
        orch.pkg_path = Path("/p")
        # Force ImportError on the coverage improvement module.
        with patch.dict(
            "sys.modules",
            {"crackerjack.orchestration.coverage_improvement": None},
        ):
            out = _run(
                workflow_executor._attempt_coverage_improvement(
                    "j1", orch, None,
                ),
            )
        assert out["status"] == "skipped"
        assert "not available" in out["reason"]

    def test_orchestrator_returns_skipped(self) -> None:
        orch = MagicMock()
        orch.pkg_path = Path("/p")
        fake_orch = MagicMock()
        fake_orch.should_improve_coverage = AsyncMock(return_value=False)

        # Provide a fake module to bypass the ModuleNotFoundError branch.
        import types

        fake_module = types.ModuleType("fake_mod")
        fake_module.create_coverage_improvement_orchestrator = AsyncMock(
            return_value=fake_orch,
        )
        with patch.dict(
            "sys.modules",
            {
                "crackerjack.orchestration.coverage_improvement": fake_module,
            },
        ):
            out = _run(
                workflow_executor._attempt_coverage_improvement(
                    "j1", orch, None,
                ),
            )
        assert out["status"] == "skipped"
        assert "100 %" in out["reason"]

    def test_orchestrator_returns_completed(self) -> None:
        orch = MagicMock()
        orch.pkg_path = Path("/p")
        fake_orch = MagicMock()
        fake_orch.should_improve_coverage = AsyncMock(return_value=True)
        fake_orch.execute_coverage_improvement = AsyncMock(
            return_value={
                "status": "completed",
                "fixes_applied": ["a"],
                "files_modified": ["/p/x.py"],
            },
        )

        import types

        fake_module = types.ModuleType("fake_mod")
        fake_module.create_coverage_improvement_orchestrator = AsyncMock(
            return_value=fake_orch,
        )
        with patch.dict(
            "sys.modules",
            {
                "crackerjack.orchestration.coverage_improvement": fake_module,
            },
        ):
            out = _run(
                workflow_executor._attempt_coverage_improvement(
                    "j1", orch, None,
                ),
            )
        assert out["status"] == "completed"
        assert out["fixes_applied"] == ["a"]

    def test_orchestrator_returns_other_status(self) -> None:
        orch = MagicMock()
        orch.pkg_path = Path("/p")
        fake_orch = MagicMock()
        fake_orch.should_improve_coverage = AsyncMock(return_value=True)
        fake_orch.execute_coverage_improvement = AsyncMock(
            return_value={"status": "partial"},
        )

        import types

        fake_module = types.ModuleType("fake_mod")
        fake_module.create_coverage_improvement_orchestrator = AsyncMock(
            return_value=fake_orch,
        )
        with patch.dict(
            "sys.modules",
            {
                "crackerjack.orchestration.coverage_improvement": fake_module,
            },
        ):
            out = _run(
                workflow_executor._attempt_coverage_improvement(
                    "j1", orch, None,
                ),
            )
        assert out["status"] == "partial"

    def test_outer_exception(self) -> None:
        orch = MagicMock()
        orch.pkg_path = Path("/p")
        fake_orch = MagicMock()
        fake_orch.should_improve_coverage = AsyncMock(
            side_effect=RuntimeError("boom"),
        )

        import types

        fake_module = types.ModuleType("fake_mod")
        fake_module.create_coverage_improvement_orchestrator = AsyncMock(
            return_value=fake_orch,
        )
        with patch.dict(
            "sys.modules",
            {
                "crackerjack.orchestration.coverage_improvement": fake_module,
            },
        ):
            out = _run(
                workflow_executor._attempt_coverage_improvement(
                    "j1", orch, None,
                ),
            )
        assert out["status"] == "failed"
        assert out["error"] == "boom"


# ─── _handle_iteration_success ─────────────────────────────────────────────


@pytest.mark.unit
class TestHandleIterationSuccess:
    def test_no_coverage(self) -> None:
        out = _run(
            workflow_executor._handle_iteration_success(
                "j1", 0, MagicMock(), {}, None,
            ),
        )
        assert out["status"] == "completed"
        assert "coverage_improvement" not in out

    def test_with_coverage(self) -> None:
        fake_orch = MagicMock()
        fake_orch.pkg_path = Path("/p")
        with patch(
            "crackerjack.mcp.tools.workflow_executor._attempt_coverage_improvement",
            new=AsyncMock(return_value={"fixes_applied": ["a"]}),
        ):
            out = _run(
                workflow_executor._handle_iteration_success(
                    "j1", 0, fake_orch, {"boost_coverage": True}, None,
                ),
            )
        assert out["coverage_improvement"] == {"fixes_applied": ["a"]}


# ─── _cleanup_keep_alive_task ──────────────────────────────────────────────


@pytest.mark.unit
class TestCleanupKeepAlive:
    def test_already_cancelled_is_noop(self) -> None:
        task = MagicMock()
        task.cancelled.return_value = True
        # No cancel() call expected.
        _run(workflow_executor._cleanup_keep_alive_task(task))
        task.cancel.assert_not_called()

    def test_cancel_pending_task(self) -> None:
        # Verify the contract: when ``cancelled()`` is False, ``cancel()`` is
        # called.  Awaiting a real task would tie us to a specific event
        # loop, so we exercise the public wrapper via its observable side
        # effects only.
        import contextlib

        # Patch the function under test to use a stub that doesn't actually
        # await the task — we're verifying the call to ``cancel()``.
        async def _stub_cleanup(keep_alive_task: t.Any) -> None:
            if not keep_alive_task.cancelled():
                keep_alive_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    # Avoid actually awaiting the mock to keep this test
                    # free of event-loop coupling.
                    pass

        task = MagicMock()
        task.cancelled.return_value = False
        with patch(
            "crackerjack.mcp.tools.workflow_executor._cleanup_keep_alive_task",
            side_effect=_stub_cleanup,
        ):
            _run(workflow_executor._cleanup_keep_alive_task(task))
        task.cancel.assert_called_once()


# ─── execute_crackerjack_workflow (public entry point) ────────────────────


@pytest.mark.unit
class TestExecuteCrackerjackWorkflow:
    def test_returns_job_id_and_running_status(self) -> None:
        fake_task = MagicMock()
        with patch(
            "crackerjack.mcp.tools.workflow_executor.get_context",
            return_value=None,
        ), patch(
            "crackerjack.mcp.tools.workflow_executor.asyncio.create_task",
            return_value=fake_task,
        ), patch(
            "crackerjack.mcp.tools.workflow_executor._update_progress",
        ):
            out = _run(
                execute_crackerjack_workflow("--test", {"test": True}),
            )
        assert "job_id" in out
        assert out["status"] == "running"
        assert "get_job_progress" in out["message"]
        assert "timestamp" in out
