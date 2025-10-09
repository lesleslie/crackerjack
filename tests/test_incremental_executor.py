"""Tests for Phase 10.3.2: Incremental Execution with Caching."""

import json
import time
from pathlib import Path

import pytest

from crackerjack.services.incremental_executor import (
    CacheEntry,
    ExecutionResult,
    FileHash,
    IncrementalExecutor,
)
from crackerjack.services.profiler import ProfileResult, ToolProfiler


class TestFileHash:
    """Test FileHash dataclass."""

    def test_file_hash_initialization(self):
        """Test FileHash can be initialized."""
        file_hash = FileHash(
            path="/path/to/file.py",
            hash="abc123",
            size=1024,
            modified_time=1234567890.0,
        )

        assert file_hash.path == "/path/to/file.py"
        assert file_hash.hash == "abc123"
        assert file_hash.size == 1024
        assert file_hash.modified_time == 1234567890.0


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_cache_entry_initialization(self):
        """Test CacheEntry can be initialized."""
        file_hash = FileHash(
            path="/path/to/file.py",
            hash="abc123",
            size=1024,
            modified_time=1234567890.0,
        )

        entry = CacheEntry(
            tool_name="test-tool",
            file_hash=file_hash,
            result={"status": "ok"},
            timestamp=1234567890.0,
            success=True,
        )

        assert entry.tool_name == "test-tool"
        assert entry.file_hash == file_hash
        assert entry.result == {"status": "ok"}
        assert entry.timestamp == 1234567890.0
        assert entry.success is True
        assert entry.error_message is None

    def test_cache_entry_with_error(self):
        """Test CacheEntry can store error information."""
        file_hash = FileHash(
            path="/path/to/file.py",
            hash="abc123",
            size=1024,
            modified_time=1234567890.0,
        )

        entry = CacheEntry(
            tool_name="test-tool",
            file_hash=file_hash,
            result=None,
            timestamp=1234567890.0,
            success=False,
            error_message="Tool execution failed",
        )

        assert entry.success is False
        assert entry.error_message == "Tool execution failed"


class TestExecutionResult:
    """Test ExecutionResult dataclass and properties."""

    def test_execution_result_initialization(self):
        """Test ExecutionResult can be initialized."""
        result = ExecutionResult(
            tool_name="test-tool",
            files_processed=10,
            files_cached=7,
            files_changed=3,
            cache_hit_rate=70.0,
            execution_time=1.5,
        )

        assert result.tool_name == "test-tool"
        assert result.files_processed == 10
        assert result.files_cached == 7
        assert result.files_changed == 3
        assert result.cache_hit_rate == 70.0
        assert result.execution_time == 1.5
        assert result.results == {}

    def test_cache_effective_property_true(self):
        """Test cache_effective returns True when hit rate >= 50%."""
        result = ExecutionResult(
            tool_name="test-tool",
            files_processed=10,
            files_cached=5,
            files_changed=5,
            cache_hit_rate=50.0,
            execution_time=1.0,
        )

        assert result.cache_effective is True

    def test_cache_effective_property_false(self):
        """Test cache_effective returns False when hit rate < 50%."""
        result = ExecutionResult(
            tool_name="test-tool",
            files_processed=10,
            files_cached=4,
            files_changed=6,
            cache_hit_rate=40.0,
            execution_time=1.0,
        )

        assert result.cache_effective is False


class TestIncrementalExecutor:
    """Test IncrementalExecutor class."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> IncrementalExecutor:
        """Create IncrementalExecutor with temp cache dir."""
        return IncrementalExecutor(cache_dir=tmp_path / "cache")

    @pytest.fixture
    def test_file(self, tmp_path: Path) -> Path:
        """Create a test file."""
        file = tmp_path / "test.py"
        file.write_text("print('hello')")
        return file

    def test_executor_initialization(self, tmp_path: Path):
        """Test IncrementalExecutor initializes correctly."""
        executor = IncrementalExecutor(cache_dir=tmp_path / "cache")

        assert executor.cache_dir == tmp_path / "cache"
        assert executor.cache_dir.exists()
        assert executor.ttl_seconds == 86400  # 24 hours
        assert executor._cache == {}

    def test_executor_default_cache_dir(self):
        """Test IncrementalExecutor uses default cache_dir when not provided."""
        executor = IncrementalExecutor()

        expected_dir = Path.cwd() / ".crackerjack" / "cache"
        assert executor.cache_dir == expected_dir

    def test_compute_file_hash(self, executor: IncrementalExecutor, test_file: Path):
        """Test _compute_file_hash generates correct hash."""
        file_hash = executor._compute_file_hash(test_file)

        assert file_hash.path == str(test_file)
        assert len(file_hash.hash) == 64  # SHA-256 hash length
        assert file_hash.size > 0
        assert file_hash.modified_time > 0

    def test_compute_file_hash_consistency(
        self, executor: IncrementalExecutor, test_file: Path
    ):
        """Test hash is consistent for unchanged file."""
        hash1 = executor._compute_file_hash(test_file)
        hash2 = executor._compute_file_hash(test_file)

        assert hash1.hash == hash2.hash

    def test_compute_file_hash_changes(
        self, executor: IncrementalExecutor, test_file: Path
    ):
        """Test hash changes when file content changes."""
        hash1 = executor._compute_file_hash(test_file)

        # Modify file
        test_file.write_text("print('modified')")

        hash2 = executor._compute_file_hash(test_file)

        assert hash1.hash != hash2.hash

    def test_execute_incremental_first_run(
        self, executor: IncrementalExecutor, test_file: Path
    ):
        """Test execute_incremental on first run (no cache)."""
        call_count = 0

        def tool_func(file_path: Path) -> str:
            nonlocal call_count
            call_count += 1
            return f"processed: {file_path.name}"

        result = executor.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
        )

        assert result.tool_name == "test-tool"
        assert result.files_processed == 1
        assert result.files_cached == 0
        assert result.files_changed == 1
        assert result.cache_hit_rate == 0.0
        assert call_count == 1

    def test_execute_incremental_cached_run(
        self, executor: IncrementalExecutor, test_file: Path
    ):
        """Test execute_incremental uses cache on second run."""
        call_count = 0

        def tool_func(file_path: Path) -> str:
            nonlocal call_count
            call_count += 1
            return f"processed: {file_path.name}"

        # First run - populate cache
        executor.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
        )

        # Second run - should use cache
        result = executor.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
        )

        assert result.files_cached == 1
        assert result.files_changed == 0
        assert result.cache_hit_rate == 100.0
        assert call_count == 1  # Tool only called once (first run)

    def test_execute_incremental_force_rerun(
        self, executor: IncrementalExecutor, test_file: Path
    ):
        """Test execute_incremental with force_rerun skips cache."""
        call_count = 0

        def tool_func(file_path: Path) -> str:
            nonlocal call_count
            call_count += 1
            return f"processed: {file_path.name}"

        # First run
        executor.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
        )

        # Second run with force_rerun
        result = executor.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
            force_rerun=True,
        )

        assert result.files_cached == 0
        assert result.files_changed == 1
        assert result.cache_hit_rate == 0.0
        assert call_count == 2  # Tool called both times

    def test_execute_incremental_profiler_integration(
        self, executor: IncrementalExecutor, test_file: Path
    ):
        """Test execute_incremental updates profiler cache stats."""
        profiler = ToolProfiler(cache_dir=executor.cache_dir)
        profiler.results["test-tool"] = ProfileResult(
            tool_name="test-tool",
            runs=0,
        )
        executor.profiler = profiler

        def tool_func(file_path: Path) -> str:
            return "ok"

        # First run - cache miss
        executor.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
        )

        assert profiler.results["test-tool"].cache_misses == 1
        assert profiler.results["test-tool"].cache_hits == 0

        # Second run - cache hit
        executor.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
        )

        assert profiler.results["test-tool"].cache_misses == 1
        assert profiler.results["test-tool"].cache_hits == 1

    def test_get_changed_files(
        self, executor: IncrementalExecutor, tmp_path: Path
    ):
        """Test get_changed_files identifies changed files."""
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text("content1")
        file2.write_text("content2")

        def tool_func(file_path: Path) -> str:
            return "ok"

        # Execute on file1 to cache it
        executor.execute_incremental(
            tool_name="test-tool",
            files=[file1],
            tool_func=tool_func,
        )

        # Check changed files (file2 is new, file1 is cached)
        changed = executor.get_changed_files("test-tool", [file1, file2])

        assert file2 in changed
        assert file1 not in changed

    def test_invalidate_file(
        self, executor: IncrementalExecutor, test_file: Path
    ):
        """Test invalidate_file removes cache entries."""

        def tool_func(file_path: Path) -> str:
            return "ok"

        # Populate cache
        executor.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
        )

        # Invalidate
        invalidated = executor.invalidate_file(test_file)

        assert invalidated == 1
        assert len(executor._cache) == 0

    def test_clear_cache_all(
        self, executor: IncrementalExecutor, tmp_path: Path
    ):
        """Test clear_cache removes all entries."""
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text("content1")
        file2.write_text("content2")

        def tool_func(file_path: Path) -> str:
            return "ok"

        # Populate cache with multiple entries
        executor.execute_incremental(
            tool_name="tool1",
            files=[file1],
            tool_func=tool_func,
        )
        executor.execute_incremental(
            tool_name="tool2",
            files=[file2],
            tool_func=tool_func,
        )

        # Clear all
        cleared = executor.clear_cache()

        assert cleared == 2
        assert len(executor._cache) == 0

    def test_clear_cache_specific_tool(
        self, executor: IncrementalExecutor, tmp_path: Path
    ):
        """Test clear_cache removes only specific tool entries."""
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text("content1")
        file2.write_text("content2")

        def tool_func(file_path: Path) -> str:
            return "ok"

        # Populate cache with multiple tools
        executor.execute_incremental(
            tool_name="tool1",
            files=[file1],
            tool_func=tool_func,
        )
        executor.execute_incremental(
            tool_name="tool2",
            files=[file2],
            tool_func=tool_func,
        )

        # Clear only tool1
        cleared = executor.clear_cache(tool_name="tool1")

        assert cleared == 1
        assert len(executor._cache) == 1

    def test_cache_persistence(self, tmp_path: Path, test_file: Path):
        """Test cache persists across executor instances."""

        def tool_func(file_path: Path) -> str:
            return "ok"

        # First executor - populate cache
        executor1 = IncrementalExecutor(cache_dir=tmp_path / "cache")
        executor1.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
        )

        # Second executor - should load cached data
        executor2 = IncrementalExecutor(cache_dir=tmp_path / "cache")
        result = executor2.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
        )

        assert result.cache_hit_rate == 100.0

    def test_cache_ttl_expiration(self, tmp_path: Path, test_file: Path):
        """Test cache entries expire after TTL."""

        def tool_func(file_path: Path) -> str:
            return "ok"

        # Create executor with 1 second TTL
        executor = IncrementalExecutor(
            cache_dir=tmp_path / "cache",
            ttl_seconds=1,
        )

        # Populate cache
        executor.execute_incremental(
            tool_name="test-tool",
            files=[test_file],
            tool_func=tool_func,
        )

        # Wait for expiration
        time.sleep(1.1)

        # New executor should not load expired cache
        executor2 = IncrementalExecutor(
            cache_dir=tmp_path / "cache",
            ttl_seconds=1,
        )

        assert len(executor2._cache) == 0

    def test_get_cache_stats(
        self, executor: IncrementalExecutor, tmp_path: Path
    ):
        """Test get_cache_stats returns correct statistics."""
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text("content1")
        file2.write_text("content2")

        def tool_func(file_path: Path) -> str:
            return "ok"

        # Populate cache
        executor.execute_incremental(
            tool_name="tool1",
            files=[file1],
            tool_func=tool_func,
        )
        executor.execute_incremental(
            tool_name="tool2",
            files=[file2],
            tool_func=tool_func,
        )

        stats = executor.get_cache_stats()

        assert stats["total_entries"] == 2
        assert stats["unique_tools"] == 2
        assert stats["success_rate"] == 100.0
        assert stats["cache_size_mb"] >= 0
