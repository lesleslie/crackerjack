from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crackerjack.executors.async_hook_executor import (
    AsyncHookExecutionResult,
    AsyncHookExecutor,
)
from crackerjack.models.task import HookResult


class TestAsyncHookExecutionResult:
    def test_result_properties(self) -> None:
        results = [
            HookResult(
                id="1",
                name="hook1",
                status="passed",
                duration=1.0,
                issues_found=[],
                stage="fast",
            ),
            HookResult(
                id="2",
                name="hook2",
                status="failed",
                duration=2.0,
                issues_found=["error"],
                stage="fast",
            ),
            HookResult(
                id="3",
                name="hook3",
                status="timeout",
                duration=3.0,
                issues_found=["timeout"],
                stage="fast",
            ),
        ]

        result = AsyncHookExecutionResult(
            strategy_name="test",
            results=results,
            total_duration=6.0,
            success=False,
            cache_hits=5,
            cache_misses=3,
            performance_gain=25.0,
        )

        assert result.passed_count == 1
        assert result.failed_count == 1
        assert result.cache_hit_rate == 62.5

        summary = result.performance_summary
        assert summary["total_hooks"] == 3
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["cache_hit_rate_percent"] == 62.5
        assert summary["performance_gain_percent"] == 25.0


class TestAsyncHookExecutor:
    @pytest.mark.asyncio
    async def test_build_success_result_preserves_ruff_issue_lines(self) -> None:
        executor = AsyncHookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        executor._last_stdout = (
            b"session_buddy/server.py:63:1: F401 unused import `os`\n"
            b"session_buddy/subscribers/code_graph_subscriber.py:313:5: E501 line too long"
        )
        executor._last_stderr = b""

        hook = MagicMock()
        hook.name = "ruff-check"
        hook.stage = SimpleNamespace(value="fast")

        process = SimpleNamespace(returncode=1)

        result = await executor._build_success_result(process, hook, duration=1.23)

        assert result.status == "failed"
        assert result.output.startswith("session_buddy/server.py:63:1")
        assert result.issues_found == [
            "session_buddy/server.py:63:1: F401 unused import `os`",
            "session_buddy/subscribers/code_graph_subscriber.py:313:5: E501 line too long",
        ]
        assert result.issues_count == 2
