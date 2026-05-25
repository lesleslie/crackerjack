"""Unit tests for thread-safe status collection."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

import crackerjack.services.thread_safe_status_collector as collector_module
from crackerjack.services.thread_safe_status_collector import (
    StatusSnapshot,
    ThreadSafeStatusCollector,
    collect_secure_status,
    get_thread_safe_status_collector,
)


@pytest.fixture
def security_logger() -> Mock:
    return Mock()


@pytest.fixture
def collector(security_logger: Mock) -> ThreadSafeStatusCollector:
    with patch(
        "crackerjack.services.thread_safe_status_collector.get_security_logger",
        return_value=security_logger,
    ):
        return ThreadSafeStatusCollector(timeout=1.0)


def test_cache_helpers_and_collection_status(collector: ThreadSafeStatusCollector) -> None:
    data = {"count": 1}
    collector._set_cached_data("services", data)

    assert collector._get_cached_data("services") == data

    status = collector.get_collection_status()
    assert status["collection_in_progress"] is False
    assert status["cache_entries"] == 1
    assert status["timeout"] == 1.0


def test_build_server_stats_safe_includes_context_details(collector: ThreadSafeStatusCollector, tmp_path: Path) -> None:
    progress_dir = tmp_path / "progress"
    progress_dir.mkdir()
    (progress_dir / "one.json").write_text("{}", encoding="utf-8")
    (progress_dir / "two.json").write_text("{}", encoding="utf-8")

    context = SimpleNamespace(
        config=SimpleNamespace(project_path=tmp_path / "project"),
        rate_limiter=SimpleNamespace(config=SimpleNamespace(limit=3)),
        progress_dir=progress_dir,
        state_manager=SimpleNamespace(
            iteration_count=8,
            session_active=True,
            issues=["a", "b"],
        ),
    )

    with patch("crackerjack.services.thread_safe_status_collector.time.time", return_value=100.0):
        stats = collector._build_server_stats_safe(context)

    assert stats["server_info"]["project_path"] == str(tmp_path / "project")
    assert stats["rate_limiting"]["enabled"] is True
    assert stats["resource_usage"]["temp_files_count"] == 2
    assert stats["state_manager"]["iteration_count"] == 8
    assert stats["state_manager"]["session_active"] is True
    assert stats["state_manager"]["issues_count"] == 2


@pytest.mark.asyncio
async def test_collect_services_data_caches_results(
    collector: ThreadSafeStatusCollector,
) -> None:
    snapshot = StatusSnapshot()

    with patch(
        "crackerjack.services.server_manager.find_mcp_server_processes",
        return_value=[{"pid": 123}],
    ):
        await collector._collect_services_data("client", snapshot)

    assert snapshot.services["mcp_server"]["running"] == [{"pid": 123}]
    assert collector._get_cached_data("services") == snapshot.services

    with patch(
        "crackerjack.services.server_manager.find_mcp_server_processes",
        side_effect=AssertionError("cache should have short-circuited"),
    ):
        second_snapshot = StatusSnapshot()
        await collector._collect_services_data("client", second_snapshot)

    assert second_snapshot.services == snapshot.services


@pytest.mark.asyncio
async def test_get_active_jobs_safe_reads_valid_files_and_logs_errors(
    collector: ThreadSafeStatusCollector,
    security_logger: Mock,
    tmp_path: Path,
) -> None:
    progress_dir = tmp_path / "progress"
    progress_dir.mkdir()
    (progress_dir / "job-1.json").write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "status": "running",
                "iteration": 4,
                "message": "working",
            },
        ),
        encoding="utf-8",
    )
    (progress_dir / "job-2.json").write_text("{invalid", encoding="utf-8")

    context = SimpleNamespace(progress_dir=progress_dir)

    with patch("crackerjack.mcp.context.get_context", return_value=context):
        jobs = await collector._get_active_jobs_safe()

    assert jobs == [
        {
            "job_id": "job-1",
            "status": "running",
            "iteration": 4,
            "max_iterations": 10,
            "current_stage": "unknown",
            "overall_progress": 0,
            "stage_progress": 0,
            "message": "working",
            "timestamp": "",
            "error_counts": {},
        },
    ]
    assert security_logger.log_security_event.call_count == 1


@pytest.mark.asyncio
async def test_collect_server_stats_handles_missing_context(
    collector: ThreadSafeStatusCollector,
) -> None:
    snapshot = StatusSnapshot()

    with patch(
        "crackerjack.mcp.context.get_context",
        side_effect=RuntimeError("missing context"),
    ):
        await collector._collect_server_stats("client", snapshot)

    assert snapshot.server_stats == {"error": "Server context not available"}


@pytest.mark.asyncio
async def test_collect_comprehensive_status_runs_all_collectors(
    collector: ThreadSafeStatusCollector,
) -> None:
    async def set_services(client_id: str, snapshot: StatusSnapshot) -> None:
        snapshot.services = {"services": True}

    async def set_jobs(client_id: str, snapshot: StatusSnapshot) -> None:
        snapshot.jobs = {"jobs": True}

    async def set_stats(client_id: str, snapshot: StatusSnapshot) -> None:
        snapshot.server_stats = {"stats": True}

    collector._collect_services_data = AsyncMock(side_effect=set_services)
    collector._collect_jobs_data = AsyncMock(side_effect=set_jobs)
    collector._collect_server_stats = AsyncMock(side_effect=set_stats)

    snapshot = await collector.collect_comprehensive_status("client")

    assert snapshot.is_complete is True
    assert snapshot.services == {"services": True}
    assert snapshot.jobs == {"jobs": True}
    assert snapshot.server_stats == {"stats": True}
    assert collector._collect_services_data.await_count == 1
    assert collector._collect_jobs_data.await_count == 1
    assert collector._collect_server_stats.await_count == 1


def test_get_thread_safe_status_collector_singleton() -> None:
    collector_module._status_collector = None

    first = get_thread_safe_status_collector()
    second = get_thread_safe_status_collector()

    assert first is second


@pytest.mark.asyncio
async def test_collect_secure_status_wrapper(collector: ThreadSafeStatusCollector) -> None:
    collector_module._status_collector = collector

    with patch.object(collector, "collect_comprehensive_status", new=AsyncMock(return_value=StatusSnapshot(is_complete=True))) as mock_collect:
        snapshot = await collect_secure_status("client", include_jobs=False, include_services=False, include_stats=False)

    assert snapshot.is_complete is True
    mock_collect.assert_awaited_once_with(
        client_id="client",
        include_jobs=False,
        include_services=False,
        include_stats=False,
    )
