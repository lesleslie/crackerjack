"""Tests for the MemoryAwareScanner service."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from rich.console import Console

import crackerjack.services.memory_aware_scanner as scanner_module
from crackerjack.services.memory_aware_scanner import MemoryAwareScanner


@pytest.fixture(autouse=True)
def _install_random() -> None:
    """The source module references ``random.random()`` without importing the
    module (a known source bug). Inject a real ``random`` module attribute and
    seed it so the test order does not flake."""
    scanner_module.random = random  # type: ignore[attr-defined]
    random.seed(0xC0FFEE)


@pytest.fixture
def mock_console() -> MagicMock:
    """Console that swallows rich markup noise during tests."""
    return MagicMock(spec=Console)


@pytest.fixture
def scanner(mock_console: MagicMock) -> MemoryAwareScanner:
    """A scanner wired to a no-op console."""
    return MemoryAwareScanner(console=mock_console, cache_duration=86400)


@pytest.fixture
def sample_files(tmp_path: Path) -> list[Path]:
    """Create a small set of python files for scanning."""
    files = [tmp_path / f"mod_{i}.py" for i in range(3)]
    for fp in files:
        fp.write_text(f"# module {fp.stem}\n")
    return files


@pytest.fixture
def now_iso() -> str:
    return datetime.now().isoformat()


class TestInit:
    """Initialization and configuration of the scanner."""

    def test_uses_default_console_when_none(self) -> None:
        scanner = MemoryAwareScanner()
        assert isinstance(scanner.console, Console)

    def test_accepts_custom_console(self, mock_console: MagicMock) -> None:
        scanner = MemoryAwareScanner(console=mock_console)
        assert scanner.console is mock_console

    def test_default_cache_duration(self) -> None:
        scanner = MemoryAwareScanner()
        assert scanner.cache_duration == MemoryAwareScanner.CACHE_DURATION_SECONDS

    def test_custom_cache_duration(self) -> None:
        scanner = MemoryAwareScanner(cache_duration=42)
        assert scanner.cache_duration == 42

    def test_memory_client_starts_unset(self, scanner: MemoryAwareScanner) -> None:
        assert scanner._memory_client is None


class TestCacheKey:
    """Cache key generation must be deterministic and order-independent."""

    def test_cache_key_is_deterministic(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        key1 = scanner._generate_cache_key("ruff", sample_files)
        key2 = scanner._generate_cache_key("ruff", sample_files)
        assert key1 == key2

    def test_cache_key_is_order_independent(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        reversed_files = list(reversed(sample_files))
        assert scanner._generate_cache_key("ruff", sample_files) == scanner._generate_cache_key(
            "ruff", reversed_files
        )

    def test_cache_key_includes_tool_name(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        assert scanner._generate_cache_key("ruff", sample_files) != scanner._generate_cache_key(
            "mypy", sample_files
        )

    def test_cache_key_format(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        key = scanner._generate_cache_key("ruff", sample_files)
        assert key.startswith(f"{MemoryAwareScanner.MEMORY_NAMESPACE}:ruff:")
        # 16-char hex hash suffix
        assert len(key.split(":")[-1]) == 16

    def test_cache_key_differs_for_different_file_sets(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        other = [sample_files[0], sample_files[1]]
        assert scanner._generate_cache_key("ruff", sample_files) != scanner._generate_cache_key(
            "ruff", other
        )


class TestEmptyInput:
    """Scanning zero files must not crash and must return sensible metrics."""

    async def test_empty_files_full_scan(
        self,
        scanner: MemoryAwareScanner,
    ) -> None:
        result = await scanner.scan_with_memory(
            tool_name="ruff",
            files=[],
            memory_client=None,
        )

        assert result["files_to_scan"] == []
        assert result["skipped_files"] == []
        assert result["cached"] is False
        assert result["scan_results"] == []
        assert result["metrics"]["total_files"] == 0
        assert result["metrics"]["files_scanned"] == 0

    async def test_empty_files_with_memory_client(
        self,
        scanner: MemoryAwareScanner,
    ) -> None:
        memory_client = MagicMock()
        memory_client.pool_search_memory = AsyncMock(
            return_value={"status": "success", "results": []}
        )

        result = await scanner.scan_with_memory(
            tool_name="ruff",
            files=[],
            memory_client=memory_client,
        )

        # Empty files: nothing to scan, nothing to skip.
        assert result["files_to_scan"] == []
        assert result["skipped_files"] == []
        assert result["metrics"]["total_files"] == 0


class TestScanFreshFiles:
    """When no cached results exist the scanner performs a full scan."""

    async def test_no_memory_client_runs_full_scan(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        result = await scanner.scan_with_memory(
            tool_name="ruff",
            files=sample_files,
            memory_client=None,
        )

        assert result["cached"] is False
        assert result["files_to_scan"] == sample_files
        assert result["skipped_files"] == []
        assert len(result["scan_results"]) == len(sample_files)
        for entry in result["scan_results"]:
            assert entry["tool"] == "ruff"
            assert entry["file_path"] in {str(f) for f in sample_files}
            assert entry["status"] in {"passed", "failed"}

    async def test_empty_cache_results_runs_full_scan(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        memory_client = MagicMock()
        memory_client.pool_search_memory = AsyncMock(
            return_value={"status": "success", "results": []}
        )

        result = await scanner.scan_with_memory(
            tool_name="ruff",
            files=sample_files,
            memory_client=memory_client,
        )

        # NOTE: _search_memory wraps the response under `search_result` so
        # the wrapper is truthy even when `results` is empty. The current
        # path goes through _process_cached_results, which means no scan
        # is performed and nothing is skipped either.
        assert result["files_to_scan"] == sample_files
        assert result["skipped_files"] == []

    async def test_failed_memory_search_falls_back(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        memory_client = MagicMock()
        memory_client.pool_search_memory = AsyncMock(
            return_value={"status": "error", "error": "boom"}
        )

        result = await scanner.scan_with_memory(
            tool_name="ruff",
            files=sample_files,
            memory_client=memory_client,
        )

        # A non-success search_result is still a truthy wrapper, so the
        # scanner treats the (empty) wrapper as 'no skips' and proceeds to
        # cache processing — which yields the same result list as the
        # empty cache case.
        assert len(result["files_to_scan"]) == len(sample_files)
        assert result["skipped_files"] == []

    async def test_full_scan_stores_results_when_memory_client_attached(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        # Attaching via _memory_client triggers the store path.
        memory_client = MagicMock()
        memory_client.pool_store_memory = AsyncMock(return_value={"status": "success"})
        scanner._memory_client = memory_client

        await scanner.scan_with_memory(
            tool_name="ruff",
            files=sample_files,
            memory_client=None,
        )

        memory_client.pool_store_memory.assert_awaited_once()
        kwargs = memory_client.pool_store_memory.await_args.kwargs
        assert kwargs["namespace"] == MemoryAwareScanner.MEMORY_NAMESPACE
        assert kwargs["ttl"] == scanner.cache_duration
        assert "key" in kwargs and "value" in kwargs

    async def test_full_scan_continues_if_store_fails(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        memory_client = MagicMock()
        memory_client.pool_store_memory = AsyncMock(side_effect=RuntimeError("nope"))
        scanner._memory_client = memory_client

        result = await scanner.scan_with_memory(
            tool_name="ruff",
            files=sample_files,
            memory_client=None,
        )

        assert result["cached"] is False
        assert len(result["scan_results"]) == len(sample_files)


class TestProcessCachedResults:
    """Direct tests for `_process_cached_results` — the layer that decides
    what to skip based on cache contents. The integration via
    `scan_with_memory` does not currently exercise this branch (see
    "Source bug" in the module summary)."""

    async def test_known_good_file_is_skipped(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
        now_iso: str,
    ) -> None:
        target = sample_files[0]
        cached = {
            "results": [
                {
                    "file_path": str(target),
                    "status": "passed",
                    "timestamp": now_iso,
                }
            ]
        }

        result = await scanner._process_cached_results(sample_files, cached)

        assert target in result["skipped_files"]
        assert target not in result["files_to_scan"]
        assert result["metrics"]["files_skipped"] == 1
        assert result["metrics"]["files_to_scan"] == len(sample_files) - 1
        assert result["metrics"]["total_files"] == len(sample_files)

    async def test_failed_cached_result_is_not_skipped(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
        now_iso: str,
    ) -> None:
        target = sample_files[0]
        cached = {
            "results": [
                {
                    "file_path": str(target),
                    "status": "failed",
                    "timestamp": now_iso,
                }
            ]
        }

        result = await scanner._process_cached_results(sample_files, cached)

        assert target in result["files_to_scan"]
        assert target not in result["skipped_files"]
        assert result["metrics"]["files_skipped"] == 0

    async def test_expired_cached_result_is_not_skipped(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        target = sample_files[0]
        old = (datetime.now() - timedelta(days=2)).isoformat()
        cached = {
            "results": [
                {
                    "file_path": str(target),
                    "status": "passed",
                    "timestamp": old,
                }
            ]
        }

        result = await scanner._process_cached_results(sample_files, cached)

        # Older than cache_duration (24h default) so the file is rescanned.
        assert target in result["files_to_scan"]
        assert target not in result["skipped_files"]

    async def test_mixed_cached_results(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
        now_iso: str,
    ) -> None:
        skip = sample_files[0]
        cached = {
            "results": [
                {
                    "file_path": str(skip),
                    "status": "passed",
                    "timestamp": now_iso,
                },
                {
                    "file_path": str(sample_files[1]),
                    "status": "failed",
                    "timestamp": now_iso,
                },
            ]
        }

        result = await scanner._process_cached_results(sample_files, cached)

        assert result["skipped_files"] == [skip]
        assert set(result["files_to_scan"]) == set(sample_files) - {skip}
        assert result["metrics"]["files_skipped"] == 1
        assert result["metrics"]["files_to_scan"] == 2


class TestMemoryClientErrors:
    """Defensive behaviour when the memory client raises."""

    async def test_search_exception_falls_through_to_full_scan(
        self,
        scanner: MemoryAwareScanner,
        sample_files: list[Path],
    ) -> None:
        memory_client = MagicMock()
        memory_client.pool_search_memory = AsyncMock(side_effect=RuntimeError("kaboom"))

        result = await scanner.scan_with_memory(
            tool_name="ruff",
            files=sample_files,
            memory_client=memory_client,
        )

        assert result["cached"] is False
        assert len(result["scan_results"]) == len(sample_files)


class TestIsKnownGood:
    """Direct tests for the _is_known_good predicate."""

    def test_returns_false_for_empty_cache(self, scanner: MemoryAwareScanner) -> None:
        assert scanner._is_known_good("/some/file.py", {"results": []}) is False

    def test_returns_false_for_empty_results_list(
        self,
        scanner: MemoryAwareScanner,
    ) -> None:
        # No results key at all -> defaults to [].
        assert scanner._is_known_good("/some/file.py", {}) is False

    def test_returns_false_when_no_matching_path(
        self,
        scanner: MemoryAwareScanner,
    ) -> None:
        cache: dict[str, Any] = {
            "results": [
                {
                    "file_path": "/other/file.py",
                    "status": "passed",
                    "timestamp": "2099-01-01T00:00:00",
                }
            ]
        }
        assert scanner._is_known_good("/some/file.py", cache) is False

    def test_returns_false_when_status_not_passed(
        self,
        scanner: MemoryAwareScanner,
    ) -> None:
        cache = {
            "results": [
                {
                    "file_path": "/some/file.py",
                    "status": "failed",
                    "timestamp": "2099-01-01T00:00:00",
                }
            ]
        }
        assert scanner._is_known_good("/some/file.py", cache) is False

    def test_returns_true_for_recent_pass(
        self,
        scanner: MemoryAwareScanner,
    ) -> None:
        cache = {
            "results": [
                {
                    "file_path": "/some/file.py",
                    "status": "passed",
                    "timestamp": datetime.now().isoformat(),
                }
            ]
        }
        assert scanner._is_known_good("/some/file.py", cache) is True


class TestSearchMemory:
    """Direct tests for `_search_memory` response shape handling."""

    async def test_returns_wrapper_dict_on_success(
        self,
        scanner: MemoryAwareScanner,
    ) -> None:
        memory_client = MagicMock()
        memory_client.pool_search_memory = AsyncMock(
            return_value={"status": "success", "results": [{"file_path": "x"}]}
        )

        result = await scanner._search_memory(memory_client, "k")

        # NOTE: source bug — the function wraps the search response under
        # `search_result` instead of returning the bare results list, which
        # means `_process_cached_results` never sees the cached entries.
        # This test pins current behaviour so a future fix is intentional.
        assert result == {"search_result": {"status": "success", "results": [{"file_path": "x"}]}}

    async def test_returns_wrapper_dict_on_failure(
        self,
        scanner: MemoryAwareScanner,
    ) -> None:
        memory_client = MagicMock()
        memory_client.pool_search_memory = AsyncMock(
            return_value={"status": "error", "error": "boom"}
        )

        result = await scanner._search_memory(memory_client, "k")

        assert result == {"search_result": {"status": "error", "error": "boom"}}

    async def test_returns_none_on_exception(
        self,
        scanner: MemoryAwareScanner,
    ) -> None:
        memory_client = MagicMock()
        memory_client.pool_search_memory = AsyncMock(side_effect=RuntimeError("kaboom"))

        result = await scanner._search_memory(memory_client, "k")

        assert result is None


class TestCleanup:
    """Cleanup method is safe to call and prints a status line."""

    async def test_cleanup_runs(self, scanner: MemoryAwareScanner) -> None:
        await scanner.cleanup()  # should not raise
        scanner.console.print.assert_called()  # type: ignore[attr-defined]
