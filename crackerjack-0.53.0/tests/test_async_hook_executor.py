from crackerjack.executors.async_hook_executor import AsyncHookExecutionResult
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
