#!/usr/bin/env python3
"""Shared test utilities and helpers for session-mgmt-mcp tests."""

import asyncio
import os
import tempfile
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import duckdb
import numpy as np
import pytest
from session_mgmt_mcp.reflection_tools import ReflectionDatabase


class TestDataFactory:
    """Factory for generating test data with realistic patterns."""

    @staticmethod
    def conversation(
        content: str | None = None,
        project: str = "test-project",
        timestamp: datetime | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate test conversation data."""
        import uuid

        return {
            "id": conversation_id or str(uuid.uuid4()),
            "content": content or f"Test conversation at {datetime.now()}",
            "project": project,
            "timestamp": timestamp or datetime.now(UTC),
        }

    @staticmethod
    def reflection(
        content: str | None = None,
        tags: list[str] | None = None,
        reflection_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate test reflection data."""
        import uuid

        return {
            "id": reflection_id or str(uuid.uuid4()),
            "content": content or f"Test reflection at {datetime.now()}",
            "tags": tags or ["test", "example"],
        }

    @staticmethod
    def search_result(
        content: str = "Test search result",
        score: float = 0.85,
        project: str = "test-project",
    ) -> dict[str, Any]:
        """Generate test search result."""
        return {
            "content": content,
            "score": score,
            "project": project,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def bulk_conversations(
        count: int = 10,
        project: str = "test-project",
    ) -> list[dict[str, Any]]:
        """Generate bulk test conversations."""
        return [
            TestDataFactory.conversation(
                content=f"Bulk conversation {i}",
                project=project,
            )
            for i in range(count)
        ]


class AsyncTestHelper:
    """Helper utilities for async testing."""

    @staticmethod
    async def wait_for_condition(
        condition_func,
        timeout: float = 5.0,
        interval: float = 0.1,
    ) -> bool:
        """Wait for a condition to become true with timeout."""
        end_time = time.time() + timeout
        while time.time() < end_time:
            if (
                await condition_func()
                if asyncio.iscoroutinefunction(condition_func)
                else condition_func()
            ):
                return True
            await asyncio.sleep(interval)
        return False

    @staticmethod
    async def collect_async_results(async_gen, limit: int = 100) -> list[Any]:
        """Collect results from async generator with limit."""
        results = []
        async for item in async_gen:
            results.append(item)
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def create_mock_coro(return_value: Any = None) -> AsyncMock:
        """Create a properly configured async mock."""
        mock = AsyncMock()
        mock.return_value = return_value
        return mock


class DatabaseTestHelper:
    """Helper utilities for database testing."""

    @staticmethod
    @asynccontextmanager
    async def temp_reflection_db() -> AsyncGenerator[ReflectionDatabase]:
        """Create temporary ReflectionDatabase for testing."""
        # Use a temporary directory and create a proper path
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.duckdb"

            db = ReflectionDatabase(db_path=str(db_path))
            try:
                await db.initialize()
                yield db
            finally:
                db.close()

    @staticmethod
    async def populate_test_data(
        db: ReflectionDatabase,
        num_conversations: int = 5,
        num_reflections: int = 3,
    ) -> dict[str, list[str]]:
        """Populate database with test data."""
        conversation_ids = []
        reflection_ids = []

        # Add conversations
        for i in range(num_conversations):
            conv_data = TestDataFactory.conversation(
                content=f"Test conversation {i}",
                project="test-project",
            )
            conv_id = await db.store_conversation(
                conv_data["content"],
                {"project": conv_data["project"]},
            )
            conversation_ids.append(conv_id)

        # Add reflections
        for i in range(num_reflections):
            refl_data = TestDataFactory.reflection(
                content=f"Test reflection {i}",
                tags=["test", f"tag{i}"],
            )
            refl_id = await db.store_reflection(
                refl_data["content"],
                refl_data["tags"],
            )
            reflection_ids.append(refl_id)

        return {
            "conversations": conversation_ids,
            "reflections": reflection_ids,
        }

    @staticmethod
    def verify_table_structure(
        conn: duckdb.DuckDBPyConnection, table_name: str
    ) -> dict[str, str]:
        """Verify table structure and return column info."""
        result = conn.execute(f"DESCRIBE {table_name}").fetchall()
        return {row[0]: row[1] for row in result}  # column_name: column_type

    @staticmethod
    async def measure_query_performance(
        db: ReflectionDatabase,
        query_func,
        *args,
        **kwargs,
    ) -> dict[str, float]:
        """Measure query performance."""
        start_time = time.perf_counter()
        result = await query_func(*args, **kwargs)
        end_time = time.perf_counter()

        return {
            "execution_time": end_time - start_time,
            "result_count": len(result) if isinstance(result, list) else 1,
        }


class MockingHelper:
    """Helper utilities for mocking in tests."""

    @staticmethod
    def mock_embedding_system():
        """Create comprehensive mock for embedding system."""
        mocks = {}

        # Mock ONNX session
        mock_onnx = Mock()
        rng = np.random.default_rng(42)
        mock_onnx.run.return_value = [rng.random((1, 384)).astype(np.float32)]
        mocks["onnx_session"] = mock_onnx

        # Mock tokenizer
        mock_tokenizer = Mock()
        mock_tokenizer.return_value = {
            "input_ids": [[1, 2, 3, 4, 5]],
            "attention_mask": [[1, 1, 1, 1, 1]],
        }
        mocks["tokenizer"] = mock_tokenizer

        return mocks

    @staticmethod
    @asynccontextmanager
    async def mock_mcp_server():
        """Create mock MCP server context manager."""
        from fastmcp import FastMCP

        server = Mock(spec=FastMCP)
        server.tool = Mock()
        server.prompt = Mock()
        server.__aenter__ = AsyncMock(return_value=server)
        server.__aexit__ = AsyncMock(return_value=None)

        yield server

    @staticmethod
    def patch_environment(**env_vars) -> patch:
        """Create environment variable patch."""
        return patch.dict(os.environ, env_vars)

    @staticmethod
    def patch_file_operations():
        """Create comprehensive file operations patch."""
        return patch.multiple(
            "pathlib.Path",
            mkdir=Mock(),
            exists=Mock(return_value=True),
            unlink=Mock(),
        )


class AssertionHelper:
    """Helper utilities for test assertions."""

    @staticmethod
    def assert_valid_uuid(value: str) -> None:
        """Assert that value is a valid UUID."""
        import uuid

        try:
            uuid.UUID(value)
        except ValueError as e:
            msg = f"Expected valid UUID, got: {value} - {e}"
            raise AssertionError(msg)

    @staticmethod
    def assert_valid_timestamp(value: str) -> None:
        """Assert that value is a valid ISO timestamp."""
        try:
            datetime.fromisoformat(value)
        except ValueError as e:
            msg = f"Expected valid timestamp, got: {value} - {e}"
            raise AssertionError(msg)

    @staticmethod
    def assert_embedding_shape(embedding: np.ndarray, expected_dim: int = 384) -> None:
        """Assert embedding has correct shape."""
        assert embedding.shape == (expected_dim,), (
            f"Expected shape ({expected_dim},), got {embedding.shape}"
        )
        assert embedding.dtype == np.float32, f"Expected float32, got {embedding.dtype}"

    @staticmethod
    def assert_similarity_score(score: float) -> None:
        """Assert similarity score is in valid range."""
        assert 0.0 <= score <= 1.0, f"Similarity score should be in [0,1], got {score}"

    @staticmethod
    def assert_database_record(
        record: dict[str, Any], expected_fields: list[str]
    ) -> None:
        """Assert database record has expected fields."""
        for field in expected_fields:
            assert field in record, f"Record missing field: {field}"
            assert record[field] is not None, f"Field {field} should not be None"


class PerformanceHelper:
    """Helper utilities for performance testing."""

    @staticmethod
    @asynccontextmanager
    async def measure_time():
        """Context manager to measure execution time."""
        start_time = time.perf_counter()
        measurements = {"start_time": start_time}

        yield measurements

        end_time = time.perf_counter()
        measurements.update(
            {
                "end_time": end_time,
                "duration": end_time - start_time,
            }
        )

    @staticmethod
    def assert_performance_threshold(
        actual_time: float,
        threshold: float,
        operation_name: str = "operation",
    ) -> None:
        """Assert operation completed within time threshold."""
        assert actual_time <= threshold, (
            f"{operation_name} took {actual_time:.3f}s, expected <= {threshold:.3f}s"
        )

    @staticmethod
    async def benchmark_async_operation(
        operation,
        iterations: int = 100,
        *args,
        **kwargs,
    ) -> dict[str, float]:
        """Benchmark async operation multiple times."""
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            await operation(*args, **kwargs)
            end = time.perf_counter()
            times.append(end - start)

        return {
            "mean": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
            "total": sum(times),
        }


# Pytest fixtures using helpers
@pytest.fixture
def test_data_factory():
    """Provide TestDataFactory instance."""
    return TestDataFactory


@pytest.fixture
def async_helper():
    """Provide AsyncTestHelper instance."""
    return AsyncTestHelper


@pytest.fixture
def db_helper():
    """Provide DatabaseTestHelper instance."""
    return DatabaseTestHelper


@pytest.fixture
def mock_helper():
    """Provide MockingHelper instance."""
    return MockingHelper


@pytest.fixture
def assert_helper():
    """Provide AssertionHelper instance."""
    return AssertionHelper


@pytest.fixture
def perf_helper():
    """Provide PerformanceHelper instance."""
    return PerformanceHelper


# Common test decorators
def requires_embeddings(test_func):
    """Decorator to skip test if embeddings not available."""
    return pytest.mark.skipif(
        not hasattr(test_func, "__module__") or "ONNX_AVAILABLE" not in dir(),
        reason="Embeddings not available",
    )(test_func)


def async_timeout(seconds: float = 30.0):
    """Decorator to add timeout to async test."""

    def decorator(test_func):
        return pytest.mark.timeout(seconds)(test_func)

    return decorator


def performance_test(baseline_key: str):
    """Decorator to mark performance test with baseline."""

    def decorator(test_func):
        return pytest.mark.performance(
            pytest.mark.parametrize("baseline_key", [baseline_key])
        )(test_func)

    return decorator
