"""Tests for semantic_models module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from crackerjack.models.semantic_models import (
    EmbeddingVector,
    FileChangeEvent,
    IndexStats,
    IndexingProgress,
    SearchQuery,
    SearchResult,
    SemanticConfig,
    SemanticContext,
)


class TestEmbeddingVector:
    """Tests for EmbeddingVector model."""

    def test_minimal_embedding_vector(self) -> None:
        """Verify minimal EmbeddingVector creation."""
        embedding = EmbeddingVector(
            file_path=Path("test.py"),
            chunk_id="chunk-1",
            content="def hello():",
            embedding=[0.1, 0.2, 0.3],
            file_hash="abc123",
            start_line=1,
            end_line=1,
            file_type="py",
        )
        assert embedding.file_path == Path("test.py")
        assert embedding.chunk_id == "chunk-1"
        assert embedding.content == "def hello():"
        assert embedding.embedding == [0.1, 0.2, 0.3]
        assert embedding.file_hash == "abc123"
        assert embedding.start_line == 1
        assert embedding.end_line == 1
        assert embedding.file_type == "py"
        assert isinstance(embedding.created_at, datetime)

    def test_embedding_vector_serialization(self) -> None:
        """Verify EmbeddingVector serialization with Path."""
        embedding = EmbeddingVector(
            file_path=Path("src/test.py"),
            chunk_id="chunk-1",
            content="code",
            embedding=[0.1, 0.2],
            file_hash="hash",
            start_line=1,
            end_line=2,
            file_type="py",
        )
        data = embedding.model_dump(mode="json")

        assert data["file_path"] == "src/test.py"
        assert isinstance(data["created_at"], str)


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_minimal_search_result(self) -> None:
        """Verify minimal SearchResult creation."""
        result = SearchResult(
            file_path=Path("code.py"),
            chunk_id="chunk-1",
            content="search match",
            similarity_score=0.85,
            start_line=10,
            end_line=15,
            file_type="py",
        )
        assert result.file_path == Path("code.py")
        assert result.chunk_id == "chunk-1"
        assert result.content == "search match"
        assert result.similarity_score == 0.85
        assert result.context_lines == []

    def test_search_result_with_context(self) -> None:
        """Verify SearchResult with context lines."""
        result = SearchResult(
            file_path=Path("test.py"),
            chunk_id="chunk-1",
            content="match",
            similarity_score=0.9,
            start_line=5,
            end_line=6,
            file_type="py",
            context_lines=["# line before", "def func():", "# line after"],
        )
        assert len(result.context_lines) == 3
        assert result.context_lines[0] == "# line before"

    def test_search_result_similarity_bounds(self) -> None:
        """Verify similarity_score validation (0-1)."""
        # Valid boundaries
        SearchResult(
            file_path=Path("test.py"),
            chunk_id="c1",
            content="test",
            similarity_score=0.0,
            start_line=1,
            end_line=1,
            file_type="py",
        )
        SearchResult(
            file_path=Path("test.py"),
            chunk_id="c1",
            content="test",
            similarity_score=1.0,
            start_line=1,
            end_line=1,
            file_type="py",
        )

        # Invalid boundaries
        with pytest.raises(ValidationError):
            SearchResult(
                file_path=Path("test.py"),
                chunk_id="c1",
                content="test",
                similarity_score=1.5,
                start_line=1,
                end_line=1,
                file_type="py",
            )

    def test_search_result_serialization(self) -> None:
        """Verify SearchResult path serialization."""
        result = SearchResult(
            file_path=Path("src/code.py"),
            chunk_id="c1",
            content="test",
            similarity_score=0.8,
            start_line=1,
            end_line=2,
            file_type="py",
        )
        data = result.model_dump(mode="json")
        assert data["file_path"] == "src/code.py"


class TestIndexStats:
    """Tests for IndexStats model."""

    def test_minimal_index_stats(self) -> None:
        """Verify minimal IndexStats creation."""
        now = datetime.now()
        stats = IndexStats(
            total_files=100,
            total_chunks=5000,
            index_size_mb=50.5,
            last_updated=now,
            embedding_model="all-MiniLM-L6-v2",
            avg_chunk_size=250.0,
        )
        assert stats.total_files == 100
        assert stats.total_chunks == 5000
        assert stats.index_size_mb == 50.5
        assert stats.last_updated == now
        assert stats.file_types == {}

    def test_index_stats_with_file_types(self) -> None:
        """Verify IndexStats with file type counts."""
        stats = IndexStats(
            total_files=100,
            total_chunks=5000,
            index_size_mb=50.0,
            last_updated=datetime.now(),
            embedding_model="model",
            avg_chunk_size=250.0,
            file_types={".py": 60, ".md": 30, ".txt": 10},
        )
        assert stats.file_types[".py"] == 60
        assert stats.file_types[".md"] == 30

    def test_index_stats_datetime_serialization(self) -> None:
        """Verify datetime serialization in IndexStats."""
        now = datetime.now()
        stats = IndexStats(
            total_files=10,
            total_chunks=100,
            index_size_mb=5.0,
            last_updated=now,
            embedding_model="model",
            avg_chunk_size=100.0,
        )
        data = stats.model_dump(mode="json")
        assert isinstance(data["last_updated"], str)
        assert data["last_updated"] == now.isoformat()


class TestSearchQuery:
    """Tests for SearchQuery model."""

    def test_minimal_search_query(self) -> None:
        """Verify minimal SearchQuery creation."""
        query = SearchQuery(query="find bugs")
        assert query.query == "find bugs"
        assert query.max_results == 10
        assert query.min_similarity == 0.3
        assert query.file_types == []
        assert query.include_context is True
        assert query.context_lines == 3

    def test_search_query_with_options(self) -> None:
        """Verify SearchQuery with custom options."""
        query = SearchQuery(
            query="test query",
            max_results=20,
            min_similarity=0.5,
            file_types=[".py", ".md"],
            include_context=False,
            context_lines=5,
        )
        assert query.max_results == 20
        assert query.min_similarity == 0.5
        assert ".py" in query.file_types
        assert query.include_context is False
        assert query.context_lines == 5

    def test_search_query_empty_query_invalid(self) -> None:
        """Verify empty query is invalid."""
        with pytest.raises(ValidationError):
            SearchQuery(query="")

    def test_search_query_max_results_bounds(self) -> None:
        """Verify max_results validation (1-100)."""
        # Valid
        SearchQuery(query="test", max_results=1)
        SearchQuery(query="test", max_results=100)

        # Invalid
        with pytest.raises(ValidationError):
            SearchQuery(query="test", max_results=0)
        with pytest.raises(ValidationError):
            SearchQuery(query="test", max_results=101)

    def test_search_query_similarity_bounds(self) -> None:
        """Verify min_similarity validation (0-1)."""
        SearchQuery(query="test", min_similarity=0.0)
        SearchQuery(query="test", min_similarity=1.0)

        with pytest.raises(ValidationError):
            SearchQuery(query="test", min_similarity=-0.1)
        with pytest.raises(ValidationError):
            SearchQuery(query="test", min_similarity=1.1)

    def test_search_query_context_lines_bounds(self) -> None:
        """Verify context_lines validation (0-10)."""
        SearchQuery(query="test", context_lines=0)
        SearchQuery(query="test", context_lines=10)

        with pytest.raises(ValidationError):
            SearchQuery(query="test", context_lines=11)


class TestIndexingProgress:
    """Tests for IndexingProgress model."""

    def test_minimal_indexing_progress(self) -> None:
        """Verify minimal IndexingProgress creation."""
        progress = IndexingProgress(
            current_file=Path("file.py"),
            files_processed=5,
            total_files=100,
            chunks_created=500,
            elapsed_time=5.0,
        )
        assert progress.files_processed == 5
        assert progress.total_files == 100
        assert progress.estimated_remaining is None

    def test_indexing_progress_with_estimate(self) -> None:
        """Verify IndexingProgress with time estimate."""
        progress = IndexingProgress(
            current_file=Path("file.py"),
            files_processed=10,
            total_files=100,
            chunks_created=1000,
            elapsed_time=10.0,
            estimated_remaining=90.0,
        )
        assert progress.estimated_remaining == 90.0

    def test_progress_percentage_calculation(self) -> None:
        """Verify progress_percentage property."""
        # 50% progress
        progress = IndexingProgress(
            current_file=Path("file.py"),
            files_processed=50,
            total_files=100,
            chunks_created=5000,
            elapsed_time=10.0,
        )
        assert progress.progress_percentage == 50.0

        # 0 total files
        progress = IndexingProgress(
            current_file=Path("file.py"),
            files_processed=0,
            total_files=0,
            chunks_created=0,
            elapsed_time=0.0,
        )
        assert progress.progress_percentage == 0.0

    def test_progress_percentage_capped(self) -> None:
        """Verify progress_percentage caps at 100%."""
        progress = IndexingProgress(
            current_file=Path("file.py"),
            files_processed=101,
            total_files=100,
            chunks_created=1000,
            elapsed_time=10.0,
        )
        assert progress.progress_percentage == 100.0

    def test_indexing_progress_path_serialization(self) -> None:
        """Verify Path serialization in IndexingProgress."""
        progress = IndexingProgress(
            current_file=Path("src/file.py"),
            files_processed=1,
            total_files=10,
            chunks_created=100,
            elapsed_time=1.0,
        )
        data = progress.model_dump(mode="json")
        assert data["current_file"] == "src/file.py"


class TestSemanticConfig:
    """Tests for SemanticConfig model."""

    def test_default_semantic_config(self) -> None:
        """Verify default SemanticConfig values."""
        config = SemanticConfig()
        assert config.embedding_backend == "auto"
        assert config.embedding_model == "all-MiniLM-L6-v2"
        assert config.chunk_size == 500
        assert config.chunk_overlap == 50
        assert config.max_search_results == 10
        assert config.similarity_threshold == 0.7
        assert config.embedding_dimension == 384
        assert config.cache_ttl_hours == 24

    def test_custom_semantic_config(self) -> None:
        """Verify custom SemanticConfig."""
        config = SemanticConfig(
            embedding_backend="ollama",
            embedding_model="nomic-embed-text",
            chunk_size=1000,
            similarity_threshold=0.5,
        )
        assert config.embedding_backend == "ollama"
        assert config.embedding_model == "nomic-embed-text"
        assert config.chunk_size == 1000
        assert config.similarity_threshold == 0.5

    def test_semantic_config_excluded_patterns_default(self) -> None:
        """Verify default excluded patterns."""
        config = SemanticConfig()
        assert "*.pyc" in config.excluded_patterns
        assert "__pycache__/*" in config.excluded_patterns
        assert ".git/*" in config.excluded_patterns

    def test_semantic_config_included_extensions_default(self) -> None:
        """Verify default included extensions."""
        config = SemanticConfig()
        assert ".py" in config.included_extensions
        assert ".md" in config.included_extensions
        assert ".json" in config.included_extensions

    def test_semantic_config_embedding_backend_literal(self) -> None:
        """Verify embedding_backend is literal type."""
        SemanticConfig(embedding_backend="auto")
        SemanticConfig(embedding_backend="onnxruntime")
        SemanticConfig(embedding_backend="ollama")
        SemanticConfig(embedding_backend="fallback")

        with pytest.raises(ValidationError):
            SemanticConfig(embedding_backend="invalid")

    def test_semantic_config_chunk_size_bounds(self) -> None:
        """Verify chunk_size validation (100-2000)."""
        SemanticConfig(chunk_size=100)
        SemanticConfig(chunk_size=2000)

        with pytest.raises(ValidationError):
            SemanticConfig(chunk_size=99)
        with pytest.raises(ValidationError):
            SemanticConfig(chunk_size=2001)

    def test_semantic_config_cache_ttl_bounds(self) -> None:
        """Verify cache_ttl_hours validation (1-168)."""
        SemanticConfig(cache_ttl_hours=1)
        SemanticConfig(cache_ttl_hours=168)

        with pytest.raises(ValidationError):
            SemanticConfig(cache_ttl_hours=0)
        with pytest.raises(ValidationError):
            SemanticConfig(cache_ttl_hours=169)


class TestFileChangeEvent:
    """Tests for FileChangeEvent model."""

    def test_file_created_event(self) -> None:
        """Verify file created event."""
        event = FileChangeEvent(
            file_path=Path("new_file.py"),
            event_type="created",
            file_hash="newhash123",
        )
        assert event.file_path == Path("new_file.py")
        assert event.event_type == "created"
        assert event.file_hash == "newhash123"
        assert isinstance(event.timestamp, datetime)

    def test_file_modified_event(self) -> None:
        """Verify file modified event."""
        event = FileChangeEvent(
            file_path=Path("existing.py"),
            event_type="modified",
            file_hash="modedhash456",
        )
        assert event.event_type == "modified"
        assert event.file_hash == "modedhash456"

    def test_file_deleted_event(self) -> None:
        """Verify file deleted event."""
        event = FileChangeEvent(
            file_path=Path("old_file.py"),
            event_type="deleted",
        )
        assert event.event_type == "deleted"
        assert event.file_hash is None

    def test_file_change_event_invalid_type(self) -> None:
        """Verify invalid event_type is rejected."""
        with pytest.raises(ValidationError):
            FileChangeEvent(
                file_path=Path("test.py"),
                event_type="renamed",
            )

    def test_file_change_event_serialization(self) -> None:
        """Verify FileChangeEvent serialization."""
        now = datetime.now()
        event = FileChangeEvent(
            file_path=Path("src/file.py"),
            event_type="modified",
            timestamp=now,
            file_hash="hash123",
        )
        data = event.model_dump(mode="json")
        assert data["file_path"] == "src/file.py"
        assert isinstance(data["timestamp"], str)
        assert data["timestamp"] == now.isoformat()


class TestSemanticContext:
    """Tests for SemanticContext model."""

    def test_minimal_semantic_context(self) -> None:
        """Verify minimal SemanticContext creation."""
        context = SemanticContext(
            query="find patterns",
            related_files=[],
            confidence=0.95,
        )
        assert context.query == "find patterns"
        assert context.related_files == []
        assert context.patterns == []
        assert context.suggestions == []
        assert context.confidence == 0.95

    def test_semantic_context_with_results(self) -> None:
        """Verify SemanticContext with search results."""
        results = [
            SearchResult(
                file_path=Path("file1.py"),
                chunk_id="c1",
                content="match1",
                similarity_score=0.9,
                start_line=1,
                end_line=2,
                file_type="py",
            ),
            SearchResult(
                file_path=Path("file2.py"),
                chunk_id="c2",
                content="match2",
                similarity_score=0.8,
                start_line=10,
                end_line=11,
                file_type="py",
            ),
        ]
        context = SemanticContext(
            query="find bugs",
            related_files=results,
            patterns=["pattern1", "pattern2"],
            suggestions=["Use async", "Add type hints"],
            confidence=0.88,
        )
        assert len(context.related_files) == 2
        assert len(context.patterns) == 2
        assert len(context.suggestions) == 2

    def test_semantic_context_confidence_bounds(self) -> None:
        """Verify confidence validation (0-1)."""
        SemanticContext(
            query="test",
            related_files=[],
            confidence=0.0,
        )
        SemanticContext(
            query="test",
            related_files=[],
            confidence=1.0,
        )

        with pytest.raises(ValidationError):
            SemanticContext(
                query="test",
                related_files=[],
                confidence=1.5,
            )
