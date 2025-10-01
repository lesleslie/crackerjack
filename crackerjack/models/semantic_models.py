"""Semantic search data models for crackerjack vector store functionality."""

import typing as t
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class EmbeddingVector(BaseModel):
    """Represents a single embedding vector with metadata."""

    file_path: Path = Field(..., description="Path to the source file")
    chunk_id: str = Field(..., description="Unique identifier for this chunk")
    content: str = Field(..., description="The text content that was embedded")
    embedding: list[float] = Field(
        ..., description="The numerical vector representation"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    file_hash: str = Field(
        ..., description="Hash of the source file for change detection"
    )
    start_line: int = Field(..., description="Starting line number in the source file")
    end_line: int = Field(..., description="Ending line number in the source file")
    file_type: str = Field(..., description="File extension or type identifier")

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    @field_serializer("file_path")
    def serialize_path(self, value: Path) -> str:
        """Serialize Path to string."""
        return str(value)

    @field_serializer("created_at")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime to ISO format."""
        return value.isoformat()


class SearchResult(BaseModel):
    """Represents a semantic search result with similarity score."""

    file_path: Path = Field(..., description="Path to the matching file")
    chunk_id: str = Field(..., description="Identifier of the matching chunk")
    content: str = Field(..., description="The matching text content")
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity score (0-1)"
    )
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    file_type: str = Field(..., description="File type identifier")
    context_lines: list[str] = Field(
        default_factory=list, description="Surrounding context lines"
    )

    @field_serializer("file_path")
    def serialize_path(self, value: Path) -> str:
        """Serialize Path to string."""
        return str(value)


class IndexStats(BaseModel):
    """Statistics about the semantic index."""

    total_files: int = Field(..., description="Total number of indexed files")
    total_chunks: int = Field(..., description="Total number of text chunks")
    index_size_mb: float = Field(..., description="Index size in megabytes")
    last_updated: datetime = Field(..., description="Last index update timestamp")
    file_types: dict[str, int] = Field(
        default_factory=dict, description="Count by file type"
    )
    embedding_model: str = Field(..., description="Name of the embedding model used")
    avg_chunk_size: float = Field(..., description="Average chunk size in characters")

    @field_serializer("last_updated")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime to ISO format."""
        return value.isoformat()


class SearchQuery(BaseModel):
    """Represents a semantic search query with parameters."""

    query: str = Field(..., min_length=1, description="The search query text")
    max_results: int = Field(
        default=10, ge=1, le=100, description="Maximum number of results"
    )
    min_similarity: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Minimum similarity threshold"
    )
    file_types: list[str] = Field(
        default_factory=list, description="Filter by file types"
    )
    include_context: bool = Field(
        default=True, description="Include surrounding context lines"
    )
    context_lines: int = Field(
        default=3, ge=0, le=10, description="Number of context lines"
    )

    model_config = ConfigDict(validate_assignment=True)


class IndexingProgress(BaseModel):
    """Progress information for indexing operations."""

    current_file: Path = Field(..., description="Currently processing file")
    files_processed: int = Field(..., ge=0, description="Number of files processed")
    total_files: int = Field(..., ge=0, description="Total files to process")
    chunks_created: int = Field(..., ge=0, description="Number of chunks created")
    elapsed_time: float = Field(..., ge=0.0, description="Elapsed time in seconds")
    estimated_remaining: float | None = Field(
        default=None, description="Estimated remaining time in seconds"
    )

    @property
    def progress_percentage(self) -> float:
        """Calculate progress as a percentage."""
        if self.total_files == 0:
            return 0.0
        return min(100.0, (self.files_processed / self.total_files) * 100.0)

    @field_serializer("current_file")
    def serialize_path(self, value: Path) -> str:
        """Serialize Path to string."""
        return str(value)


class SemanticConfig(BaseModel):
    """Configuration for semantic search functionality."""

    embedding_model: str = Field(
        default="all-MiniLM-L6-v2", description="Sentence transformer model name"
    )
    chunk_size: int = Field(
        default=500, ge=100, le=2000, description="Maximum characters per chunk"
    )
    chunk_overlap: int = Field(
        default=50, ge=0, le=500, description="Overlap between chunks"
    )
    max_search_results: int = Field(
        default=10, ge=1, le=100, description="Maximum number of search results"
    )
    similarity_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum similarity threshold"
    )
    embedding_dimension: int = Field(
        default=384, ge=128, le=1024, description="Embedding vector dimension"
    )
    max_file_size_mb: int = Field(
        default=10, ge=1, le=100, description="Maximum file size to process"
    )
    excluded_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.pyc",
            "*.pyo",
            "*.pyd",
            "__pycache__/*",
            ".git/*",
            ".venv/*",
            "*.log",
            "*.tmp",
        ],
        description="File patterns to exclude from indexing",
    )
    included_extensions: list[str] = Field(
        default_factory=lambda: [
            ".py",
            ".md",
            ".txt",
            ".yml",
            ".yaml",
            ".json",
            ".toml",
            ".ini",
            ".cfg",
            ".sh",
            ".js",
            ".ts",
            ".html",
            ".css",
            ".sql",
        ],
        description="File extensions to include in indexing",
    )
    cache_embeddings: bool = Field(default=True, description="Cache embeddings to disk")
    cache_ttl_hours: int = Field(
        default=24, ge=1, le=168, description="Cache time-to-live in hours"
    )

    model_config = ConfigDict(validate_assignment=True)


class FileChangeEvent(BaseModel):
    """Represents a file system change event for incremental indexing."""

    file_path: Path = Field(..., description="Path to the changed file")
    event_type: t.Literal["created", "modified", "deleted"] = Field(
        ..., description="Type of change"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the change occurred"
    )
    file_hash: str | None = Field(
        default=None, description="New file hash if available"
    )

    @field_serializer("file_path")
    def serialize_path(self, value: Path) -> str:
        """Serialize Path to string."""
        return str(value)

    @field_serializer("timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime to ISO format."""
        return value.isoformat()


class SemanticContext(BaseModel):
    """Context information for AI agents using semantic search."""

    query: str = Field(..., description="The query that generated this context")
    related_files: list[SearchResult] = Field(
        ..., description="Semantically related files"
    )
    patterns: list[str] = Field(
        default_factory=list, description="Identified code patterns"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="AI-generated suggestions"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the context relevance"
    )


# Type aliases for better code readability
EmbeddingMatrix = list[list[float]]
SimilarityMatrix = list[list[float]]
FilePathSet = set[Path]
ChunkMapping = dict[str, EmbeddingVector]

__all__ = [
    "EmbeddingVector",
    "SearchResult",
    "IndexStats",
    "SearchQuery",
    "IndexingProgress",
    "SemanticConfig",
    "FileChangeEvent",
    "SemanticContext",
    "EmbeddingMatrix",
    "SimilarityMatrix",
    "FilePathSet",
    "ChunkMapping",
]
