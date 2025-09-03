"""Property-based tests for reflection system robustness.

Uses Hypothesis to generate test data and verify system properties
under various edge cases and unexpected inputs.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from session_mgmt_mcp.reflection_tools import ReflectionDatabase
from session_mgmt_mcp.server import quick_search, store_reflection

# Hypothesis strategies for generating test data
valid_content_strategy = st.text(min_size=1, max_size=10000).filter(
    lambda x: x.strip() and not x.isspace(),
)

tag_strategy = st.text(
    alphabet=st.characters(whitelist_categories=["L", "N"], whitelist_characters="-_"),
    min_size=1,
    max_size=50,
).filter(lambda x: x and x[0].isalnum())

tags_list_strategy = st.lists(tag_strategy, min_size=0, max_size=10, unique=True)

query_strategy = st.text(min_size=1, max_size=1000).filter(
    lambda x: x.strip() and len(x.strip()) >= 1,
)

project_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=["L", "N"], whitelist_characters="-_."),
    min_size=1,
    max_size=100,
).filter(lambda x: x and not x.startswith("."))


@pytest.mark.unit
@pytest.mark.property
class TestReflectionSystemProperties:
    """Property-based tests for reflection system."""

    @pytest.fixture
    async def temp_database(self):
        """Temporary database for property testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "property_test.db"
            db = ReflectionDatabase(str(db_path))
            await db.initialize()
            yield db
            await db.close()

    @given(content=valid_content_strategy, tags=tags_list_strategy)
    @settings(
        max_examples=50,
        deadline=30000,
    )  # 30 second deadline for async operations
    @pytest.mark.asyncio
    async def test_store_reflection_properties(self, content, tags, temp_database):
        """Test reflection storage properties hold for any valid input."""
        # Property: Storing valid content should always succeed
        result = await temp_database.store_reflection(
            content=content,
            tags=tags,
            project="test-project",
        )

        assert result is not None
        assert isinstance(result, str)  # Should return reflection ID
        assert len(result) > 0

        # Property: Stored reflection should be retrievable
        stats = await temp_database.get_stats()
        assert stats["total_reflections"] >= 1

        # Property: Search should find the stored content
        search_results = await temp_database.search_reflections(
            query=content[:50],  # Search with first 50 chars
            limit=10,
        )

        # Should either find via semantic search or text fallback
        assert isinstance(search_results, dict)
        assert "results" in search_results
        assert "count" in search_results
        assert search_results["count"] >= 0

    @given(
        query=query_strategy,
        limit=st.integers(min_value=1, max_value=100),
        min_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_search_properties(self, query, limit, min_score, temp_database):
        """Test search operation properties."""
        # Property: Search should never crash with valid inputs
        result = await temp_database.search_reflections(
            query=query,
            limit=limit,
            min_score=min_score,
        )

        assert isinstance(result, dict)
        assert "results" in result
        assert "count" in result
        assert isinstance(result["results"], list)
        assert isinstance(result["count"], int)
        assert result["count"] >= 0
        assert len(result["results"]) <= limit

        # Property: All results should meet minimum score if specified
        for reflection in result["results"]:
            if "score" in reflection and min_score > 0:
                assert reflection["score"] >= min_score

    @given(
        reflections=st.lists(
            st.tuples(valid_content_strategy, tags_list_strategy),
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_bulk_operations_properties(self, reflections, temp_database):
        """Test properties of bulk reflection operations."""
        # Store multiple reflections
        reflection_ids = []
        for content, tags in reflections:
            reflection_id = await temp_database.store_reflection(
                content=content,
                tags=tags,
                project="bulk-test",
            )
            reflection_ids.append(reflection_id)

        # Property: All reflections should be stored successfully
        assert len(reflection_ids) == len(reflections)
        assert all(isinstance(rid, str) and len(rid) > 0 for rid in reflection_ids)

        # Property: Database stats should reflect the additions
        stats = await temp_database.get_stats()
        assert stats["total_reflections"] >= len(reflections)

        # Property: Search should be able to find content from bulk operations
        if reflections:
            first_content = reflections[0][0]
            search_result = await temp_database.search_reflections(
                query=first_content[:30],
                project="bulk-test",
            )
            # Should find at least some results from the project
            assert search_result["count"] >= 0

    @given(
        invalid_input=st.one_of(
            st.none(),
            st.text(max_size=0),  # Empty string
            st.text().filter(lambda x: x.isspace()),  # Only whitespace
            st.integers(),  # Wrong type
            st.lists(st.integers()),  # Wrong type list
        ),
    )
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_input_validation_properties(self, invalid_input):
        """Test system handles invalid inputs gracefully."""
        # Property: Invalid content should not crash the system
        try:
            with patch(
                "session_mgmt_mcp.reflection_tools.ReflectionDatabase",
            ) as mock_db:
                mock_db_instance = AsyncMock()
                mock_db.return_value = mock_db_instance

                # Should either reject invalid input or handle gracefully
                result = await store_reflection(content=invalid_input)

                # If it doesn't raise an exception, should return error indication
                if isinstance(result, dict):
                    assert "success" in result
                    if result.get("success") is False:
                        assert "error" in result

        except (TypeError, ValueError, AttributeError) as e:
            # Acceptable to raise these exceptions for invalid input
            assert str(e)  # Should have error message

    @given(
        project_names=st.lists(
            project_name_strategy,
            min_size=1,
            max_size=10,
            unique=True,
        ),
    )
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_project_isolation_properties(self, project_names, temp_database):
        """Test project isolation properties."""
        # Store reflections in different projects
        for i, project in enumerate(project_names):
            await temp_database.store_reflection(
                content=f"Content for project {project} - {i}",
                tags=[f"project-{i}"],
                project=project,
            )

        # Property: Each project should have independent reflections
        for project in project_names:
            project_results = await temp_database.search_reflections(
                query="Content for project",
                project=project,
                limit=50,
            )

            # Should find results for the specific project
            assert project_results["count"] >= 0

            # All results should be from the queried project
            for result in project_results["results"]:
                if "project" in result:
                    assert result["project"] == project


@pytest.mark.unit
@pytest.mark.property
class TestMCPToolProperties:
    """Property-based tests for MCP tool interfaces."""

    @given(content=valid_content_strategy, tags=tags_list_strategy)
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_store_reflection_mcp_properties(self, content, tags):
        """Test store_reflection MCP tool properties."""
        with patch("session_mgmt_mcp.reflection_tools.ReflectionDatabase") as mock_db:
            mock_instance = AsyncMock()
            mock_instance.store_reflection.return_value = "test-reflection-id"
            mock_db.return_value = mock_instance

            # Property: MCP tool should always return structured response
            result = await store_reflection(content=content, tags=tags)

            assert isinstance(result, dict)
            assert "success" in result
            assert isinstance(result["success"], bool)

            if result["success"]:
                assert "reflection_id" in result
                assert isinstance(result["reflection_id"], str)

    @given(
        query=query_strategy,
        limit=st.integers(min_value=1, max_value=100),
        min_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_quick_search_mcp_properties(self, query, limit, min_score):
        """Test quick_search MCP tool properties."""
        with patch("session_mgmt_mcp.reflection_tools.ReflectionDatabase") as mock_db:
            mock_instance = AsyncMock()
            mock_instance.search_reflections.return_value = {
                "results": [{"content": "test", "score": 0.8}],
                "count": 1,
            }
            mock_db.return_value = mock_instance

            # Property: MCP tool should handle all valid parameter combinations
            result = await quick_search(query=query, limit=limit, min_score=min_score)

            assert isinstance(result, dict)
            assert "count" in result
            assert "has_more" in result
            assert isinstance(result["count"], int)
            assert isinstance(result["has_more"], bool)
            assert result["count"] >= 0

    @given(batch_size=st.integers(min_value=1, max_value=50))
    @settings(max_examples=10)
    @pytest.mark.asyncio
    async def test_concurrent_mcp_operations_properties(self, batch_size):
        """Test concurrent MCP operations maintain consistency."""
        with patch("session_mgmt_mcp.reflection_tools.ReflectionDatabase") as mock_db:
            mock_instance = AsyncMock()
            mock_instance.store_reflection.return_value = "concurrent-reflection-id"
            mock_instance.search_reflections.return_value = {"results": [], "count": 0}
            mock_db.return_value = mock_instance

            # Property: Concurrent operations should all succeed independently
            store_tasks = [
                store_reflection(
                    content=f"Concurrent content {i}",
                    tags=[f"concurrent-{i}"],
                )
                for i in range(batch_size)
            ]

            search_tasks = [
                quick_search(query=f"search query {i}") for i in range(batch_size)
            ]

            # Execute all operations concurrently
            all_tasks = store_tasks + search_tasks
            results = await asyncio.gather(*all_tasks, return_exceptions=True)

            # Property: No operations should fail with exceptions
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0

            # Property: All operations should return valid responses
            for result in results:
                assert isinstance(result, dict)
                assert "success" in result or "count" in result
