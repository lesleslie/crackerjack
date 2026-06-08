"""Tests for crackerjack.services.thread_safe_status_collector.

These tests cover the public surface of ``ThreadSafeStatusCollector`` and the
``StatusSnapshot`` dataclass. The heavy I/O collaborators
(``crackerjack.services.server_manager.find_mcp_server_processes`` and
``crackerjack.mcp.context.get_context``) are mocked at the module boundary so
no real subprocess or filesystem activity is performed.

The concurrent aggregator invariants are exercised with
``concurrent.futures.ThreadPoolExecutor`` to drive real thread interleavings
across the collector's locks.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.services.thread_safe_status_collector import (
    StatusSnapshot,
    ThreadSafeStatusCollector,
    collect_secure_status,
    get_thread_safe_status_collector,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_context(
    tmp_path: Path,
    *,
    rate_limiter: Any = None,
    state_manager: Any = None,
) -> MagicMock:
    """Build a MagicMock that quacks like ``MCPServerContext``."""
    config = MagicMock()
    config.project_path = tmp_path
    context = MagicMock()
    context.config = config
    context.progress_dir = tmp_path
    context.rate_limiter = rate_limiter
    context.state_manager = state_manager
    return context


def _reset_status_collector_singleton() -> None:
    """Drop the module-level singleton between tests for isolation."""
    import crackerjack.services.thread_safe_status_collector as mod

    mod._status_collector = None


@pytest.fixture
def reset_singleton() -> None:
    _reset_status_collector_singleton()
    yield
    _reset_status_collector_singleton()


@pytest.fixture
def collector() -> ThreadSafeStatusCollector:
    return ThreadSafeStatusCollector(timeout=2.0)


# ---------------------------------------------------------------------------
# StatusSnapshot dataclass
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStatusSnapshot:
    def test_default_field_values(self) -> None:
        snap = StatusSnapshot()
        assert snap.services == {}
        assert snap.jobs == {}
        assert snap.server_stats == {}
        assert snap.agent_suggestions == {}
        assert snap.errors == []
        assert snap.is_complete is False
        assert snap.collection_duration == 0.0
        # ``timestamp`` is auto-populated to roughly ``time.time()``
        assert snap.timestamp <= time.time()
        assert snap.timestamp > 0

    def test_each_instance_gets_independent_containers(self) -> None:
        """Verify field defaults don't share mutable state across instances."""
        a = StatusSnapshot()
        b = StatusSnapshot()
        a.services["k"] = 1
        a.errors.append("oops")
        assert b.services == {}
        assert b.errors == []

    def test_custom_field_override(self) -> None:
        snap = StatusSnapshot(
            services={"x": 1},
            jobs={"j": 2},
            is_complete=True,
            collection_duration=0.42,
            errors=["boom"],
        )
        assert snap.services == {"x": 1}
        assert snap.jobs == {"j": 2}
        assert snap.is_complete is True
        assert snap.collection_duration == 0.42
        assert snap.errors == ["boom"]


# ---------------------------------------------------------------------------
# Construction & module singleton
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInit:
    def test_init_defaults(self, collector: ThreadSafeStatusCollector) -> None:
        assert collector.timeout == 2.0
        assert collector._cache == {}
        assert collector._cache_timestamps == {}
        assert collector._cache_ttl == 5.0
        assert collector._current_snapshot is None
        assert collector._collection_in_progress is False
        assert collector._collection_start_time == 0.0
        # All three locks are RLock instances (re-entrant).
        assert isinstance(collector._collection_lock, type(threading.RLock()))
        assert isinstance(collector._data_lock, type(threading.RLock()))
        assert isinstance(collector._file_lock, type(threading.RLock()))

    def test_singleton_returns_same_instance(
        self,
        reset_singleton: None,
    ) -> None:
        first = get_thread_safe_status_collector()
        second = get_thread_safe_status_collector()
        assert first is second

    def test_singleton_is_collectable_after_reset(
        self,
        reset_singleton: None,
    ) -> None:
        a = get_thread_safe_status_collector()
        _reset_status_collector_singleton()
        b = get_thread_safe_status_collector()
        assert a is not b


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCache:
    def test_set_and_get_within_ttl(self, collector: ThreadSafeStatusCollector) -> None:
        collector._set_cached_data("services", {"mcp": {"running": []}})
        result = collector._get_cached_data("services")
        assert result == {"mcp": {"running": []}}

    def test_get_returns_none_for_missing_key(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        assert collector._get_cached_data("missing") is None

    def test_get_returns_none_after_ttl_expired(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        collector._set_cached_data("services", {"v": 1})
        # Backdate the entry so it looks older than the TTL.
        collector._cache_timestamps["services"] = time.time() - 100.0
        assert collector._get_cached_data("services") is None

    def test_clear_cache_empties_both_dicts(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        collector._set_cached_data("services", {"a": 1})
        collector._set_cached_data("jobs", {"b": 2})
        assert len(collector._cache) == 2
        collector.clear_cache()
        assert collector._cache == {}
        assert collector._cache_timestamps == {}

    def test_set_cached_data_stores_a_copy_when_possible(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        """``_set_cached_data`` should not alias caller-owned dicts."""
        original: dict[str, Any] = {"v": 1}
        collector._set_cached_data("services", original)
        original["v"] = 99  # mutate caller-side
        # Cached value reflects the value at set-time, not the alias.
        assert collector._cache["services"] == {"v": 1}


# ---------------------------------------------------------------------------
# Collection status snapshot
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetCollectionStatus:
    def test_initial_status(self, collector: ThreadSafeStatusCollector) -> None:
        status = collector.get_collection_status()
        assert status == {
            "collection_in_progress": False,
            "collection_duration": 0.0,
            "cache_entries": 0,
            "timeout": 2.0,
        }

    def test_status_reports_cache_size(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        collector._set_cached_data("services", {"x": 1})
        collector._set_cached_data("jobs", {"y": 2})
        status = collector.get_collection_status()
        assert status["cache_entries"] == 2

    def test_status_reports_active_collection_duration(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        with collector._collection_lock:
            collector._collection_in_progress = True
            collector._collection_start_time = time.time() - 0.5
        status = collector.get_collection_status()
        assert status["collection_in_progress"] is True
        assert status["collection_duration"] >= 0.5

    def test_status_releases_lock_for_concurrent_readers(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        """Two threads can call get_collection_status without deadlocking."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(collector.get_collection_status) for _ in range(8)]
            results = [f.result(timeout=2.0) for f in futures]
        assert len(results) == 8
        assert all(r["timeout"] == 2.0 for r in results)


# ---------------------------------------------------------------------------
# Comprehensive collection — happy paths (heavy I/O mocked)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCollectComprehensiveStatus:
    async def test_collects_all_three_sections(
        self,
        collector: ThreadSafeStatusCollector,
        tmp_path: Path,
    ) -> None:
        """All three sub-collectors feed snapshot on success."""
        context = _make_context(tmp_path)
        with (
            patch(
                "crackerjack.services.server_manager.find_mcp_server_processes",
                return_value=[{"pid": 1, "name": "x"}],
            ),
            patch(
                "crackerjack.mcp.context.get_context",
                return_value=context,
            ),
            patch.object(
                ThreadSafeStatusCollector,
                "_build_server_stats_safe",
                return_value={"server_info": {"project_path": str(tmp_path)}},
            ),
        ):
            snap = await collector.collect_comprehensive_status("client-1")

        assert snap.is_complete is True
        assert snap.collection_duration >= 0.0
        assert snap.services["mcp_server"]["running"] == [{"pid": 1, "name": "x"}]
        # The cached ``services`` key now exists; jobs were never cached.
        assert collector._get_cached_data("services") is not None

    async def test_excludes_each_section_when_disabled(
        self,
        collector: ThreadSafeStatusCollector,
        tmp_path: Path,
    ) -> None:
        """Each include_* flag controls whether the section is gathered."""
        context = _make_context(tmp_path)
        with (
            patch(
                "crackerjack.services.server_manager.find_mcp_server_processes",
                return_value=[],
            ),
            patch(
                "crackerjack.mcp.context.get_context",
                return_value=context,
            ),
            patch.object(
                ThreadSafeStatusCollector,
                "_build_server_stats_safe",
                return_value={"server_info": {"project_path": str(tmp_path)}},
            ),
        ):
            snap = await collector.collect_comprehensive_status(
                "client-1",
                include_jobs=False,
                include_services=False,
                include_stats=False,
            )

        assert snap.services == {}
        assert snap.jobs == {}
        assert snap.server_stats == {}
        assert snap.is_complete is True

    async def test_uses_cached_data_when_available(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        """If a cache hit is present, the heavy collector is NOT called."""
        cached_services = {"mcp_server": {"running": ["cached"]}}
        collector._set_cached_data("services", cached_services)
        cached_jobs = {
            "active_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "details": [],
        }
        collector._set_cached_data("jobs", cached_jobs)

        with patch(
            "crackerjack.services.server_manager.find_mcp_server_processes",
        ) as mcp_mock:
            snap = await collector.collect_comprehensive_status(
                "client-1",
                # Force services to use the cache; skip stats (avoids mocking context)
                include_stats=False,
            )

        assert snap.services == cached_services
        assert snap.jobs == cached_jobs
        mcp_mock.assert_not_called()

    async def test_skips_server_stats_when_context_unavailable(
        self,
        collector: ThreadSafeStatusCollector,
        tmp_path: Path,
    ) -> None:
        """No MCP context -> server_stats carries an error key, not a raise."""
        with (
            patch(
                "crackerjack.services.server_manager.find_mcp_server_processes",
                return_value=[],
            ),
            patch(
                "crackerjack.mcp.context.get_context",
                side_effect=RuntimeError("no context"),
            ),
        ):
            snap = await collector.collect_comprehensive_status(
                "client-1",
                include_jobs=False,
            )
        assert snap.server_stats == {"error": "Server context not available"}
        assert snap.is_complete is True

    async def test_records_error_in_snapshot_on_subcollector_failure(
        self,
        collector: ThreadSafeStatusCollector,
        tmp_path: Path,
    ) -> None:
        """Sub-collector exceptions are surfaced via ``snapshot.errors``.

        Note: the collector wraps sub-collectors in
        ``asyncio.gather(..., return_exceptions=True)`` and then unconditionally
        sets ``is_complete = True`` -- so the *snapshot itself* is still
        flagged complete even when one of the sub-collectors raised. The
        error is recorded on ``snapshot.errors`` and the failing section is
        populated with an ``{"error": ...}`` envelope. This test pins that
        current behavior.
        """
        context = _make_context(tmp_path)
        with (
            patch(
                "crackerjack.services.server_manager.find_mcp_server_processes",
                return_value=[],
            ),
            patch(
                "crackerjack.mcp.context.get_context",
                return_value=context,
            ),
            patch.object(
                ThreadSafeStatusCollector,
                "_build_server_stats_safe",
                side_effect=RuntimeError("boom"),
            ),
        ):
            snap = await collector.collect_comprehensive_status("client-1")

        assert any("Failed to collect server stats" in e for e in snap.errors)
        assert snap.server_stats == {"error": "Failed to collect server stats: boom"}
        # ``is_complete`` is True because the gather swallows sub-collector
        # exceptions via return_exceptions=True and the outer success branch
        # runs to completion. The presence of the error in
        # ``snapshot.errors`` is how callers learn something went wrong.
        assert snap.is_complete is True

    async def test_services_subcollector_error_path(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        """If the services sub-collector raises, an error is recorded."""
        with (
            patch(
                "crackerjack.services.server_manager.find_mcp_server_processes",
                side_effect=RuntimeError("mcp-list-broken"),
            ),
            patch(
                "crackerjack.mcp.context.get_context",
                return_value=None,
            ),
        ):
            snap = await collector.collect_comprehensive_status(
                "client-1",
                include_jobs=False,
                include_stats=False,
            )
        assert any("Failed to collect services data" in e for e in snap.errors)
        assert snap.services == {"error": "Failed to collect services data: mcp-list-broken"}

    async def test_jobs_subcollector_error_path(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        """If the jobs sub-collector raises, an error is recorded."""
        with (
            patch(
                "crackerjack.services.server_manager.find_mcp_server_processes",
                return_value=[],
            ),
            patch(
                "crackerjack.mcp.context.get_context",
                return_value=None,
            ),
            patch.object(
                ThreadSafeStatusCollector,
                "_get_active_jobs_safe",
                side_effect=RuntimeError("jobs-broken"),
            ),
        ):
            snap = await collector.collect_comprehensive_status("client-1")
        assert any("Failed to collect jobs data" in e for e in snap.errors)
        assert snap.jobs == {"error": "Failed to collect jobs data: jobs-broken"}

    async def test_outer_exception_returns_incomplete_snapshot(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        """A non-timeout exception in the collector body yields ``is_complete=False``.

        The collector's outer ``except Exception`` is reachable when something
        outside the gather call fails. We trigger it by making the first
        sub-collector raise synchronously in a way the gather cannot swallow.
        """
        # Patch one of the sub-collectors at the class level so that its
        # coroutine raises *before* being awaited by gather. asyncio.gather
        # with return_exceptions=True catches exceptions from the await, so
        # we need a non-async function that raises on attribute access.
        def _boom(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("outer-failure")

        with patch.object(
            ThreadSafeStatusCollector,
            "_collect_services_data",
            _boom,
        ):
            snap = await collector.collect_comprehensive_status(
                "client-1",
                include_jobs=False,
                include_stats=False,
            )
        assert snap.is_complete is False
        assert any("outer-failure" in e for e in snap.errors)


# ---------------------------------------------------------------------------
# Timeout / RuntimeError paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCollectFailurePaths:
    async def test_timeout_propagates_timeout_error(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        """If the inner gather hangs, TimeoutError is re-raised."""

        async def _hang(*_args: Any, **_kwargs: Any) -> None:
            await asyncio.sleep(10)

        # Use a tight timeout to keep the test fast.
        collector.timeout = 0.05
        with patch.object(
            ThreadSafeStatusCollector,
            "_collect_services_data",
            side_effect=_hang,
        ):
            with pytest.raises(TimeoutError):
                await collector.collect_comprehensive_status("client-1")

    async def test_collect_lock_busy_raises_runtime_error(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        """If a collection is already in progress, a second call fails fast."""
        # Mark the collection as permanently in-progress to skip the busy-wait.
        collector._collection_in_progress = True
        with pytest.raises(RuntimeError, match="Unable to acquire collection lock"):
            await collector.collect_comprehensive_status("client-1")


# ---------------------------------------------------------------------------
# Job-file scanning
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetActiveJobsSafe:
    async def test_returns_empty_when_no_context(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        with patch(
            "crackerjack.mcp.context.get_context",
            return_value=None,
        ):
            jobs = await collector._get_active_jobs_safe()
        assert jobs == []

    async def test_returns_empty_when_progress_dir_missing(
        self,
        collector: ThreadSafeStatusCollector,
        tmp_path: Path,
    ) -> None:
        # tmp_path exists; configure context with a non-existent subdir.
        missing = tmp_path / "no-such-dir"
        context = MagicMock()
        context.progress_dir = missing
        with patch(
            "crackerjack.mcp.context.get_context",
            return_value=context,
        ):
            jobs = await collector._get_active_jobs_safe()
        assert jobs == []

    async def test_parses_valid_job_files(
        self,
        collector: ThreadSafeStatusCollector,
        tmp_path: Path,
    ) -> None:
        # Two valid JSON files matching ``job-*.json``.
        payload_a = {
            "job_id": "j-1",
            "status": "running",
            "iteration": 2,
            "max_iterations": 5,
            "current_stage": "lint",
            "overall_progress": 0.4,
            "stage_progress": 0.5,
            "message": "linting",
            "timestamp": "2026-01-01T00:00:00Z",
            "error_counts": {"ruff": 1},
        }
        (tmp_path / "job-1.json").write_text(json.dumps(payload_a), encoding="utf-8")
        (tmp_path / "job-2.json").write_text(
            json.dumps({"job_id": "j-2", "status": "completed"}),
            encoding="utf-8",
        )
        # And one corrupt file that should be skipped, not raise.
        (tmp_path / "job-3.json").write_text("{not json", encoding="utf-8")

        context = _make_context(tmp_path)
        with patch(
            "crackerjack.mcp.context.get_context",
            return_value=context,
        ):
            jobs = await collector._get_active_jobs_safe()

        ids = sorted(j["job_id"] for j in jobs)
        assert ids == ["j-1", "j-2"]
        assert jobs[0]["status"] in {"running", "completed"}


# ---------------------------------------------------------------------------
# Server stats builder
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildServerStatsSafe:
    def test_builds_expected_shape(
        self,
        collector: ThreadSafeStatusCollector,
        tmp_path: Path,
    ) -> None:
        class _RateLimiterConfig:
            def __init__(self) -> None:
                self.max_calls = 10
                self.window = 60.0

        class _RateLimiter:
            def __init__(self) -> None:
                self.config = _RateLimiterConfig()

        class _StateManager:
            def __init__(self) -> None:
                self.iteration_count = 3
                self.session_active = True
                self.issues = [object(), object()]

        context = _make_context(
            tmp_path,
            rate_limiter=_RateLimiter(),
            state_manager=_StateManager(),
        )
        # Put a couple of progress files so the count is non-zero.
        (tmp_path / "job-a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "job-b.json").write_text("{}", encoding="utf-8")

        stats = collector._build_server_stats_safe(context)

        assert stats["server_info"]["project_path"] == str(tmp_path)
        assert stats["rate_limiting"]["enabled"] is True
        assert stats["rate_limiting"]["config"] == {
            "max_calls": 10,
            "window": 60.0,
        }
        assert stats["resource_usage"]["temp_files_count"] == 2
        assert stats["resource_usage"]["progress_dir"] == str(tmp_path)
        assert stats["state_manager"] == {
            "iteration_count": 3,
            "session_active": True,
            "issues_count": 2,
        }
        assert "timestamp" in stats

    def test_handles_missing_optional_components(
        self,
        collector: ThreadSafeStatusCollector,
        tmp_path: Path,
    ) -> None:
        context = _make_context(tmp_path, rate_limiter=None, state_manager=None)
        stats = collector._build_server_stats_safe(context)
        assert stats["rate_limiting"] == {"enabled": False, "config": None}
        # No state_manager key when the attribute is None.
        assert "state_manager" not in stats

    def test_internal_exception_returns_error_envelope(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        class _Boom:
            @property
            def project_path(self) -> None:
                raise RuntimeError("kapow")

        # Patch the dataclass attribute access to blow up.
        bad = MagicMock()
        bad.config = _Boom()
        stats = collector._build_server_stats_safe(bad)
        assert "error" in stats
        assert "kapow" in stats["error"]


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCollectSecureStatus:
    async def test_delegates_to_singleton(
        self,
        reset_singleton: None,
    ) -> None:
        with patch.object(
            ThreadSafeStatusCollector,
            "collect_comprehensive_status",
            new=AsyncMockReturning(
                StatusSnapshot(
                    is_complete=True,
                    collection_duration=0.01,
                ),
            ),
        ):
            snap = await collect_secure_status("client-9")
        assert snap.is_complete is True


# ---------------------------------------------------------------------------
# Tiny async-returning shim used in tests above
# ---------------------------------------------------------------------------


class AsyncMockReturning:
    """A drop-in for an async method: ``await AsyncMockReturning(x)`` returns ``x``."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def __call__(self, *args: Any, **kwargs: Any) -> "AsyncMockReturning":
        return self

    def __await__(self):  # type: ignore[no-untyped-def]
        async def _coro() -> Any:
            return self._value

        return _coro().__await__()


# ---------------------------------------------------------------------------
# Concurrent invariants (slow, real threads)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.unit
class TestConcurrentInvariants:
    async def test_collection_lock_serializes_concurrent_calls(
        self,
        collector: ThreadSafeStatusCollector,
        tmp_path: Path,
    ) -> None:
        """Two simultaneous ``collect_*`` calls must not interleave their bodies.

        We monkey-patch the sub-collectors to record overlap; if the lock is
        doing its job the overlap counter stays at zero.
        """
        context = _make_context(tmp_path)
        overlap = 0
        in_section = 0
        lock = threading.Lock()

        async def _fake_services(
            self: ThreadSafeStatusCollector,
            client_id: str,
            snapshot: StatusSnapshot,
        ) -> None:
            nonlocal overlap, in_section
            with lock:
                in_section += 1
                if in_section > 1:
                    overlap += 1
            try:
                await asyncio.sleep(0.05)
                snapshot.services = {"ok": True}
            finally:
                with lock:
                    in_section -= 1

        async def _fake_jobs(
            self: ThreadSafeStatusCollector,
            client_id: str,
            snapshot: StatusSnapshot,
        ) -> None:
            snapshot.jobs = {"active_count": 0, "completed_count": 0, "failed_count": 0, "details": []}

        with (
            patch.object(
                ThreadSafeStatusCollector,
                "_collect_services_data",
                _fake_services,
            ),
            patch.object(
                ThreadSafeStatusCollector,
                "_collect_jobs_data",
                _fake_jobs,
            ),
            patch(
                "crackerjack.mcp.context.get_context",
                return_value=context,
            ),
            patch.object(
                ThreadSafeStatusCollector,
                "_collect_server_stats",
                new=AsyncMockReturning(None),
            ),
        ):
            coros = [
                collector.collect_comprehensive_status(f"client-{i}")
                for i in range(4)
            ]
            results = await asyncio.gather(*coros, return_exceptions=True)

        # Every call must have succeeded; none raised RuntimeError due to lock.
        assert all(isinstance(r, StatusSnapshot) for r in results)
        assert overlap == 0
        # Collection flag must be released after every call.
        assert collector._collection_in_progress is False

    def test_cache_lock_serializes_writers(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        """Heavy parallel writes to the cache must not lose data."""
        N = 200

        def writer(i: int) -> None:
            collector._set_cached_data(f"key-{i}", {"i": i})

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(writer, range(N)))

        assert len(collector._cache) == N
        # Every key must be retrievable (no torn writes).
        for i in range(N):
            assert collector._get_cached_data(f"key-{i}") == {"i": i}

    def test_status_snapshot_is_consistent_under_contention(
        self,
        collector: ThreadSafeStatusCollector,
    ) -> None:
        """Status snapshot reads must see internally consistent values."""
        collector._set_cached_data("services", {"v": 1})

        def reader() -> dict[str, Any]:
            return collector.get_collection_status()

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            futures = [pool.submit(reader) for _ in range(100)]
            results = [f.result(timeout=2.0) for f in futures]

        # Every snapshot must carry its own ``timeout`` value -- no torn read.
        assert all(r["timeout"] == 2.0 for r in results)
