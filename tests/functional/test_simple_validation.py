#!/usr/bin/env python3
"""Simple validation tests for test infrastructure."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from session_mgmt_mcp.reflection_tools import ReflectionDatabase


class TestInfrastructureValidation:
    """Simple tests to validate test infrastructure works."""

    def test_basic_imports(self):
        """Test that basic imports work."""
        from session_mgmt_mcp.reflection_tools import ReflectionDatabase
        from tests.helpers import AsyncTestHelper, DatabaseTestHelper, TestDataFactory

        assert ReflectionDatabase is not None
        assert TestDataFactory is not None
        assert AsyncTestHelper is not None
        assert DatabaseTestHelper is not None

    def test_test_data_factory(self):
        """Test TestDataFactory generates valid data."""
        from tests.helpers import TestDataFactory

        # Test conversation generation
        conv_data = TestDataFactory.conversation("Test content", "test-project")
        assert conv_data["content"] == "Test content"
        assert conv_data["project"] == "test-project"
        assert "id" in conv_data
        assert "timestamp" in conv_data

        # Test reflection generation
        refl_data = TestDataFactory.reflection("Test reflection", ["tag1", "tag2"])
        assert refl_data["content"] == "Test reflection"
        assert refl_data["tags"] == ["tag1", "tag2"]
        assert "id" in refl_data

        # Test bulk generation
        bulk_convs = TestDataFactory.bulk_conversations(5, "bulk-project")
        assert len(bulk_convs) == 5
        assert all(conv["project"] == "bulk-project" for conv in bulk_convs)

    def test_temp_database_creation(self):
        """Test temporary database creation works."""
        # Use a temporary directory and create a proper path
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.duckdb"

            # Test database can be created
            db = ReflectionDatabase(db_path=str(db_path))
            assert db.db_path == str(db_path)
            assert Path(db_path).parent.exists()

    @pytest.mark.asyncio
    async def test_async_database_initialization(self):
        """Test async database initialization works."""
        # Use a temporary directory and create a proper path
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.duckdb"

            db = ReflectionDatabase(db_path=str(db_path))

            # Test initialization
            await db.initialize()
            assert db.conn is not None

            # Test basic functionality
            conv_id = await db.store_conversation(
                "Test async conversation", {"project": "test-project"}
            )
            assert conv_id is not None
            assert len(conv_id) > 10  # Should be a UUID-like string

            # Test cleanup
            db.close()
            assert db.conn is None

    @pytest.mark.asyncio
    async def test_async_helpers_work(self):
        """Test async helper functions work."""
        from tests.helpers import AsyncTestHelper

        # Test wait_for_condition
        counter = [0]

        def increment_condition():
            counter[0] += 1
            return counter[0] >= 3

        result = await AsyncTestHelper.wait_for_condition(
            increment_condition, timeout=1.0, interval=0.1
        )
        assert result is True
        assert counter[0] >= 3

        # Test async generator collection
        async def test_async_gen():
            for i in range(5):
                yield f"item_{i}"

        results = await AsyncTestHelper.collect_async_results(test_async_gen(), limit=3)
        assert len(results) == 3
        assert results == ["item_0", "item_1", "item_2"]

    def test_helper_mocking_utilities(self):
        """Test mocking helper utilities work."""
        from tests.helpers import MockingHelper

        # Test embedding system mock
        embedding_mocks = MockingHelper.mock_embedding_system()
        assert "onnx_session" in embedding_mocks
        assert "tokenizer" in embedding_mocks

        # Test ONNX mock returns expected shape
        onnx_mock = embedding_mocks["onnx_session"]
        result = onnx_mock.run.return_value
        assert len(result) == 1  # Should return list with one array
        assert result[0].shape == (1, 384)  # Should be 384-dimensional

    def test_assertion_helpers(self):
        """Test assertion helper utilities work."""
        import uuid
        from datetime import UTC, datetime

        import numpy as np
        from tests.helpers import AssertionHelper

        # Test UUID validation
        valid_uuid = str(uuid.uuid4())
        AssertionHelper.assert_valid_uuid(valid_uuid)

        with pytest.raises((ValueError, AssertionError)):  # Should fail on invalid UUID
            AssertionHelper.assert_valid_uuid("not-a-uuid")

        # Test timestamp validation
        valid_timestamp = datetime.now(UTC).isoformat()
        AssertionHelper.assert_valid_timestamp(valid_timestamp)

        # Test embedding shape validation
        rng = np.random.default_rng(42)
        valid_embedding = rng.random((384,)).astype(np.float32)
        AssertionHelper.assert_embedding_shape(valid_embedding)

        # Test similarity score validation
        AssertionHelper.assert_similarity_score(0.5)
        AssertionHelper.assert_similarity_score(0.0)
        AssertionHelper.assert_similarity_score(1.0)

        with pytest.raises(AssertionError):
            AssertionHelper.assert_similarity_score(1.5)  # Should fail

    @pytest.mark.asyncio
    async def test_database_helper_temp_db(self):
        """Test DatabaseTestHelper temporary database creation."""
        from tests.helpers import DatabaseTestHelper

        async with DatabaseTestHelper.temp_reflection_db() as db:
            # Should be initialized
            assert db.conn is not None

            # Should be able to store data
            conv_id = await db.store_conversation(
                "Helper test", {"project": "helper-project"}
            )
            assert conv_id is not None

            # Should be able to populate test data
            data_ids = await DatabaseTestHelper.populate_test_data(db, 3, 2)
            assert "conversations" in data_ids
            assert "reflections" in data_ids
            assert len(data_ids["conversations"]) == 3
            assert len(data_ids["reflections"]) == 2

    def test_performance_helper(self):
        """Test PerformanceHelper utilities work."""
        from tests.helpers import PerformanceHelper

        # Test assertion helper
        PerformanceHelper.assert_performance_threshold(0.001, 0.1, "fast operation")

        with pytest.raises(AssertionError):
            PerformanceHelper.assert_performance_threshold(0.2, 0.1, "slow operation")

    @pytest.mark.asyncio
    async def test_performance_measurement(self):
        """Test performance measurement utilities."""
        from tests.helpers import PerformanceHelper

        # Test time measurement context manager
        async with PerformanceHelper.measure_time() as measurements:
            await asyncio.sleep(0.01)  # 10ms delay

        assert "start_time" in measurements
        assert "end_time" in measurements
        assert "duration" in measurements
        assert measurements["duration"] > 0.005  # Should be at least 5ms

    def test_fixture_availability(self):
        """Test that pytest fixtures are available and work."""
        # This test mainly checks that imports and basic setup work
        # The actual fixture testing happens in the async tests above

        # Test that all helper classes are importable
        from tests.helpers import (
            AssertionHelper,
            AsyncTestHelper,
            DatabaseTestHelper,
            MockingHelper,
            PerformanceHelper,
            TestDataFactory,
        )

        # Test that all classes can be instantiated
        assert TestDataFactory() is not None
        assert AsyncTestHelper() is not None
        assert DatabaseTestHelper() is not None
        assert MockingHelper() is not None
        assert AssertionHelper() is not None
        assert PerformanceHelper() is not None
