import time
from typing import Never
from unittest.mock import Mock

import pytest

from crackerjack.core.performance import (
    FileCache,
    PerformanceMonitor,
    batch_file_operations,
    memoize_with_ttl,
)


class TestFileCache:
    def test_init(self) -> None:
        cache = FileCache()
        assert cache.ttl == 300.0
        assert cache.size() == 0

    def test_init_with_custom_ttl(self) -> None:
        cache = FileCache(ttl=60.0)
        assert cache.ttl == 60.0

    def test_set_and_get(self) -> None:
        cache = FileCache()
        cache.set("test_key", "test_value")

        assert cache.get("test_key") == "test_value"
        assert cache.size() == 1

    def test_get_nonexistent_key(self) -> None:
        cache = FileCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self) -> None:
        cache = FileCache(ttl=0.1)
        cache.set("test_key", "test_value")

        assert cache.get("test_key") == "test_value"

        time.sleep(0.2)

        assert cache.get("test_key") is None
        assert cache.size() == 0

    def test_clear(self) -> None:
        cache = FileCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert cache.size() == 2

        cache.clear()

        assert cache.size() == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_overwrite_key(self) -> None:
        cache = FileCache()
        cache.set("test_key", "old_value")
        cache.set("test_key", "new_value")

        assert cache.get("test_key") == "new_value"
        assert cache.size() == 1


class TestPerformanceMonitor:
    def test_init(self) -> None:
        monitor = PerformanceMonitor()
        assert monitor.console is None
        assert monitor.metrics == {}

    def test_init_with_console(self) -> None:
        mock_console = Mock()
        monitor = PerformanceMonitor(console=mock_console)
        assert monitor.console is mock_console

    def test_time_operation_decorator(self) -> None:
        monitor = PerformanceMonitor()

        @monitor.time_operation("test_op")
        def test_function(x: int) -> int:
            time.sleep(0.01)
            return x * 2

        result = test_function(5)

        assert result == 10
        assert "test_op" in monitor.metrics
        assert len(monitor.metrics["test_op"]) == 1
        assert monitor.metrics["test_op"][0] > 0

    def test_time_operation_multiple_calls(self) -> None:
        monitor = PerformanceMonitor()

        @monitor.time_operation("multi_op")
        def test_function(x: int) -> int:
            return x + 1

        for i in range(3):
            test_function(i)

        assert "multi_op" in monitor.metrics
        assert len(monitor.metrics["multi_op"]) == 3

    def test_time_operation_preserves_function_attributes(self) -> None:
        monitor = PerformanceMonitor()

        @monitor.time_operation("preserve_test")
        def test_function(x: int) -> int:
            """Test function docstring."""
            return x

        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test function docstring."

    def test_time_operation_with_exception(self) -> None:
        monitor = PerformanceMonitor()

        @monitor.time_operation("exception_test")
        def failing_function() -> Never:
            msg = "Test exception"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Test exception"):
            failing_function()

        assert "exception_test" in monitor.metrics
        assert len(monitor.metrics["exception_test"]) == 1

    def test_record_metric(self) -> None:
        monitor = PerformanceMonitor()

        monitor.record_metric("test_metric", 1.5)
        monitor.record_metric("test_metric", 2.0)

        assert "test_metric" in monitor.metrics
        assert monitor.metrics["test_metric"] == [1.5, 2.0]

    def test_get_stats_with_data(self) -> None:
        monitor = PerformanceMonitor()

        @monitor.time_operation("stats_test")
        def test_function() -> None:
            time.sleep(0.01)

        test_function()
        test_function()

        stats = monitor.get_stats("stats_test")

        assert stats["count"] == 2
        assert stats["total"] > 0
        assert stats["avg"] > 0
        assert stats["min"] > 0
        assert stats["max"] > 0

    def test_get_stats_empty(self) -> None:
        monitor = PerformanceMonitor()
        stats = monitor.get_stats("nonexistent")
        assert stats == {}

    def test_print_stats_without_console(self) -> None:
        monitor = PerformanceMonitor()
        monitor.record_metric("test", 1.0)

        monitor.print_stats("test")
        monitor.print_stats()

    def test_print_stats_with_console(self) -> None:
        mock_console = Mock()
        monitor = PerformanceMonitor(console=mock_console)
        monitor.record_metric("test", 1.0)

        monitor.print_stats("test")

        mock_console.print.assert_called_once()


class TestMemoizeWithTTL:
    def test_memoize_basic_functionality(self) -> None:
        call_count = 0

        @memoize_with_ttl(ttl=60.0)
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1

        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2

    def test_memoize_ttl_expiration(self) -> None:
        call_count = 0

        @memoize_with_ttl(ttl=0.1)
        def function_with_short_ttl(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 3

        result1 = function_with_short_ttl(5)
        assert result1 == 15
        assert call_count == 1

        result2 = function_with_short_ttl(5)
        assert result2 == 15
        assert call_count == 1

        time.sleep(0.2)

        result3 = function_with_short_ttl(5)
        assert result3 == 15
        assert call_count == 2

    def test_memoize_cache_clear(self) -> None:
        call_count = 0

        @memoize_with_ttl(ttl=60.0)
        def cached_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x + 100

        cached_function(1)
        cached_function(2)
        assert call_count == 2

        cached_function.cache_clear()

        cached_function(1)
        assert call_count == 3

    def test_memoize_cache_info(self) -> None:
        @memoize_with_ttl(ttl=30.0)
        def info_function(x: int) -> int:
            return x

        info = info_function.cache_info()
        assert info["ttl"] == 30.0
        assert info["size"] == 0

        info_function(1)
        info_function(2)

        info = info_function.cache_info()
        assert info["size"] == 2

    def test_memoize_with_kwargs(self) -> None:
        call_count = 0

        @memoize_with_ttl()
        def function_with_kwargs(x: int, multiplier: int = 2) -> int:
            nonlocal call_count
            call_count += 1
            return x * multiplier

        result1 = function_with_kwargs(5, multiplier=3)
        result2 = function_with_kwargs(5, 3)
        result3 = function_with_kwargs(x=5, multiplier=3)

        assert result1 == result2 == result3 == 15

        assert call_count >= 1


class TestBatchFileOperations:
    def test_batch_operations_basic(self) -> None:
        operations = [
            lambda: 1,
            lambda: 2,
            lambda: 3,
        ]

        results = batch_file_operations(operations, batch_size=2)

        assert results == [1, 2, 3]

    def test_batch_operations_with_exceptions(self) -> None:
        def failing_operation() -> Never:
            msg = "Test error"
            raise ValueError(msg)

        operations = [
            lambda: 1,
            failing_operation,
            lambda: 3,
        ]

        results = batch_file_operations(operations)

        assert results[0] == 1
        assert isinstance(results[1], ValueError)
        assert results[2] == 3

    def test_batch_operations_empty_list(self) -> None:
        results = batch_file_operations([])
        assert results == []

    def test_batch_operations_large_batch_size(self) -> None:
        operations = [lambda i=i: i for i in range(5)]

        results = batch_file_operations(operations, batch_size=10)

        assert results == [0, 1, 2, 3, 4]

    def test_batch_operations_single_item_batches(self) -> None:
        operations = [lambda i=i: i for i in range(3)]

        results = batch_file_operations(operations, batch_size=1)

        assert results == [0, 1, 2]
