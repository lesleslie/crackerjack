"""Tests for PoolRouter service.

Covers the public API of ``crackerjack.services.pool_router.PoolRouter``:

* ``route_to_best_pool`` - maps a tool name to a worker type and returns the
  routing info. Falls back to ``fast-worker`` for unknown tools.
* ``get_optimal_pool_config`` - bucketises a list of tools into heavy-CPU,
  fast, and security workers, returning recommended min/max worker counts.
* ``get_routing_summary`` - returns a summary count of supported tools per
  worker class.
"""

from __future__ import annotations

import pytest
from rich.console import Console

from crackerjack.services.pool_router import PoolRouter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def quiet_console() -> Console:
    """Rich console configured to not pollute test output."""
    return Console(quiet=True, no_color=True, force_terminal=False)


@pytest.fixture
def router(quiet_console: Console) -> PoolRouter:
    """PoolRouter wired with a quiet console."""
    return PoolRouter(console=quiet_console)


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_console_used_when_none_supplied(self) -> None:
        router = PoolRouter()
        assert router.console is not None
        assert isinstance(router.console, Console)

    def test_supplied_console_is_retained(self, quiet_console: Console) -> None:
        router = PoolRouter(console=quiet_console)
        assert router.console is quiet_console

    def test_tool_worker_map_is_class_attribute(self) -> None:
        # Sanity check: the class exposes the routing table.
        assert isinstance(PoolRouter.TOOL_WORKER_MAP, dict)
        assert "ruff" in PoolRouter.TOOL_WORKER_MAP
        assert "refurb" in PoolRouter.TOOL_WORKER_MAP


# ---------------------------------------------------------------------------
# TestRouteToBestPool
# ---------------------------------------------------------------------------


class TestRouteToBestPool:
    @pytest.mark.asyncio
    async def test_routes_heavy_cpu_tool(self, router: PoolRouter) -> None:
        info = await router.route_to_best_pool("refurb", ["a.py", "b.py"])
        assert info["tool"] == "refurb"
        assert info["worker_type"] == "heavy-cpu-worker"
        assert info["files_count"] == 2

    @pytest.mark.asyncio
    async def test_routes_another_heavy_cpu_tool(self, router: PoolRouter) -> None:
        info = await router.route_to_best_pool("mypy", ["x.py"])
        assert info["worker_type"] == "heavy-cpu-worker"
        assert info["reason"] == "MyPy needs full type checking"

    @pytest.mark.asyncio
    async def test_routes_fast_tool(self, router: PoolRouter) -> None:
        info = await router.route_to_best_pool("ruff", ["f.py"])
        assert info["worker_type"] == "fast-worker"
        assert info["reason"] == "Ruff is fast enough for shared workers"

    @pytest.mark.asyncio
    async def test_routes_security_tool(self, router: PoolRouter) -> None:
        info = await router.route_to_best_pool("semgrep", ["x.py"])
        assert info["worker_type"] == "security-worker"
        assert "Semgrep needs isolation" in info["reason"]

    @pytest.mark.asyncio
    async def test_unknown_tool_falls_back_to_fast_worker(
        self, router: PoolRouter
    ) -> None:
        info = await router.route_to_best_pool("not-a-real-tool", [])
        assert info["worker_type"] == "fast-worker"
        assert "default routing" in info["reason"]

    @pytest.mark.asyncio
    async def test_empty_files_list_yields_zero_count(
        self, router: PoolRouter
    ) -> None:
        info = await router.route_to_best_pool("ruff", [])
        assert info["files_count"] == 0

    @pytest.mark.asyncio
    async def test_bandit_routes_to_heavy_cpu_worker(
        self, router: PoolRouter
    ) -> None:
        # Sanity: bandit lives in the heavy-CPU map (not security), so
        # workers need real CPU rather than isolation.
        info = await router.route_to_best_pool("bandit", ["a.py"])
        assert info["worker_type"] == "heavy-cpu-worker"

    @pytest.mark.asyncio
    async def test_bandit_routing_reason_matches_heavy_cpu_entry(
        self, router: PoolRouter
    ) -> None:
        info = await router.route_to_best_pool("bandit", ["a.py"])
        assert info["reason"] == "Bandit requires deep security analysis"

    @pytest.mark.asyncio
    async def test_returns_dict_with_expected_keys(
        self, router: PoolRouter
    ) -> None:
        info = await router.route_to_best_pool("ruff", ["a.py"])
        assert set(info.keys()) >= {"tool", "worker_type", "reason", "files_count"}

    @pytest.mark.asyncio
    async def test_each_known_tool_has_a_non_default_reason(
        self, router: PoolRouter
    ) -> None:
        # Every tool in the routing table has an explicit reason (other than
        # the catch-all default).
        for tool in PoolRouter.TOOL_WORKER_MAP:
            info = await router.route_to_best_pool(tool, [])
            assert "default routing" not in info["reason"], (
                f"Expected explicit reason for {tool!r}, got default"
            )


# ---------------------------------------------------------------------------
# TestGetOptimalPoolConfig
# ---------------------------------------------------------------------------


class TestGetOptimalPoolConfig:
    @pytest.mark.asyncio
    async def test_empty_tool_list(self, router: PoolRouter) -> None:
        cfg = await router.get_optimal_pool_config([])
        assert cfg["total_tools"] == 0
        assert cfg["heavy_cpu_count"] == 0
        assert cfg["fast_tools_count"] == 0
        assert cfg["security_tools_count"] == 0

    @pytest.mark.asyncio
    async def test_buckets_tools_into_worker_classes(
        self, router: PoolRouter
    ) -> None:
        cfg = await router.get_optimal_pool_config(
            ["refurb", "ruff", "semgrep", "gitleaks"]
        )
        assert cfg["heavy_cpu_count"] == 1
        assert cfg["fast_tools_count"] == 1
        assert cfg["security_tools_count"] == 2
        assert cfg["total_tools"] == 4

    @pytest.mark.asyncio
    async def test_unknown_tools_go_to_fast_bucket(
        self, router: PoolRouter
    ) -> None:
        # Unknown tool names fall through to fast-worker.
        cfg = await router.get_optimal_pool_config(["mystery-tool"])
        assert cfg["fast_tools_count"] == 1
        assert cfg["heavy_cpu_count"] == 0
        assert cfg["security_tools_count"] == 0

    @pytest.mark.asyncio
    async def test_min_workers_scales_with_tool_count(
        self, router: PoolRouter
    ) -> None:
        cfg = await router.get_optimal_pool_config(["ruff"] * 5)
        assert cfg["suggested_min_workers"] == 5  # max(2, 5)

    @pytest.mark.asyncio
    async def test_min_workers_uses_floor_of_two(self, router: PoolRouter) -> None:
        cfg = await router.get_optimal_pool_config([])
        # max(2, 0) -> 2
        assert cfg["suggested_min_workers"] == 2

    @pytest.mark.asyncio
    async def test_max_workers_scales_with_tool_count(
        self, router: PoolRouter
    ) -> None:
        cfg = await router.get_optimal_pool_config(["ruff"] * 3)
        # max(8, 3 * 2) -> 8 (the floor of 8 wins for small inputs)
        assert cfg["suggested_max_workers"] == 8

    @pytest.mark.asyncio
    async def test_max_workers_grows_above_floor(self, router: PoolRouter) -> None:
        cfg = await router.get_optimal_pool_config(["ruff"] * 10)
        # 10 * 2 = 20 > 8 floor
        assert cfg["suggested_max_workers"] == 20

    @pytest.mark.asyncio
    async def test_input_tools_preserved_in_recommendation(
        self, router: PoolRouter
    ) -> None:
        tools = ["refurb", "ruff"]
        cfg = await router.get_optimal_pool_config(tools)
        assert cfg["tools"] == tools

    @pytest.mark.asyncio
    async def test_all_heavy_cpu_tools(self, router: PoolRouter) -> None:
        tools = ["refurb", "complexipy", "pylint", "mypy", "bandit"]
        cfg = await router.get_optimal_pool_config(tools)
        assert cfg["heavy_cpu_count"] == 5
        assert cfg["fast_tools_count"] == 0
        assert cfg["security_tools_count"] == 0


# ---------------------------------------------------------------------------
# TestGetRoutingSummary
# ---------------------------------------------------------------------------


class TestGetRoutingSummary:
    def test_summary_counts_match_table(self, router: PoolRouter) -> None:
        summary = router.get_routing_summary()
        assert (
            summary["heavy_cpu_tools"]
            + summary["fast_tools"]
            + summary["security_tools"]
            == summary["total_tools_supported"]
        )

    def test_total_tools_supported_matches_table_size(
        self, router: PoolRouter
    ) -> None:
        summary = router.get_routing_summary()
        assert summary["total_tools_supported"] == len(PoolRouter.TOOL_WORKER_MAP)

    def test_summary_keys(self, router: PoolRouter) -> None:
        summary = router.get_routing_summary()
        assert set(summary.keys()) == {
            "total_tools_supported",
            "heavy_cpu_tools",
            "fast_tools",
            "security_tools",
        }

    def test_heavy_cpu_count_is_correct(self, router: PoolRouter) -> None:
        expected = sum(
            1
            for worker in PoolRouter.TOOL_WORKER_MAP.values()
            if worker == "heavy-cpu-worker"
        )
        assert router.get_routing_summary()["heavy_cpu_tools"] == expected

    def test_fast_count_is_correct(self, router: PoolRouter) -> None:
        expected = sum(
            1
            for worker in PoolRouter.TOOL_WORKER_MAP.values()
            if worker == "fast-worker"
        )
        assert router.get_routing_summary()["fast_tools"] == expected

    def test_security_count_is_correct(self, router: PoolRouter) -> None:
        expected = sum(
            1
            for worker in PoolRouter.TOOL_WORKER_MAP.values()
            if worker == "security-worker"
        )
        assert router.get_routing_summary()["security_tools"] == expected
