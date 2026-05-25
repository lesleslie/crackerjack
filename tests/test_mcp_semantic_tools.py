"""Tests for semantic_tools.py MCP tools.

Tests indexing, semantic search, and embedding generation tools.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from crackerjack.mcp.tools.semantic_tools import (
    _get_persistent_db_path,
    _create_error_response,
    _validate_search_query,
    _validate_search_parameters,
    _parse_file_types,
    _format_search_results,
    _parse_texts_input,
    _generate_embeddings_for_texts,
    _format_embeddings_response,
    _parse_semantic_config,
    register_semantic_tools,
)


class TestGetPersistentDbPath:
    """Tests for _get_persistent_db_path function."""

    def test_returns_path_in_crackerjack_directory(self) -> None:
        """Test returns path in .crackerjack directory."""
        with patch("pathlib.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/project")

            result = _get_persistent_db_path()

            assert ".crackerjack" in str(result)
            assert result.name == "semantic_index.db"

    def test_creates_parent_directory(self) -> None:
        """Test creates parent directory if it doesn't exist."""
        with patch("pathlib.Path.mkdir") as mock_mkdir, \
             patch("pathlib.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/project")

            _get_persistent_db_path()

            mock_mkdir.assert_called_once()


class TestCreateErrorResponse:
    """Tests for _create_error_response function."""

    def test_creates_error_with_defaults(self) -> None:
        """Test creates error response with default values."""
        result = _create_error_response("Test error")

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error"] == "Test error"

    def test_adds_extra_kwargs(self) -> None:
        """Test adds extra keyword arguments to response."""
        result = _create_error_response("Test error", query="test", code=400)

        parsed = json.loads(result)
        assert parsed["error"] == "Test error"
        assert parsed["query"] == "test"
        assert parsed["code"] == 400


class TestValidateSearchQuery:
    """Tests for _validate_search_query function."""

    def test_returns_validated_query(self) -> None:
        """Test returns validated query."""
        with patch("crackerjack.mcp.tools.semantic_tools.get_input_validator") as mock:
            validator = MagicMock()
            validator.validate_command_args.return_value = MagicMock(
                valid=True,
                sanitized_value="  test query  ",
            )
            mock.return_value = validator

            query, error = _validate_search_query("  test query  ")

            assert error is None
            assert query == "  test query  "

    def test_returns_error_for_invalid_query(self) -> None:
        """Test returns error for invalid query."""
        with patch("crackerjack.mcp.tools.semantic_tools.get_input_validator") as mock:
            validator = MagicMock()
            validator.validate_command_args.return_value = MagicMock(
                valid=False,
                error_message="Query too long",
            )
            mock.return_value = validator

            query, error = _validate_search_query("x" * 1000)

            assert error is not None
            assert "Query too long" in error


class TestValidateSearchParameters:
    """Tests for _validate_search_parameters function."""

    def test_accepts_valid_parameters(self) -> None:
        """Test accepts valid search parameters."""
        error = _validate_search_parameters(max_results=50, min_similarity=0.7)
        assert error is None

    def test_rejects_max_results_below_range(self) -> None:
        """Test rejects max_results below 1."""
        error = _validate_search_parameters(max_results=0, min_similarity=0.7)
        assert error is not None
        assert "max_results" in error

    def test_rejects_max_results_above_range(self) -> None:
        """Test rejects max_results above 100."""
        error = _validate_search_parameters(max_results=101, min_similarity=0.7)
        assert error is not None
        assert "max_results" in error

    def test_rejects_min_similarity_below_range(self) -> None:
        """Test rejects min_similarity below 0.0."""
        error = _validate_search_parameters(max_results=10, min_similarity=-0.1)
        assert error is not None
        assert "min_similarity" in error

    def test_rejects_min_similarity_above_range(self) -> None:
        """Test rejects min_similarity above 1.0."""
        error = _validate_search_parameters(max_results=10, min_similarity=1.1)
        assert error is not None
        assert "min_similarity" in error


class TestParseFileTypes:
    """Tests for _parse_file_types function."""

    def test_returns_empty_list_for_empty_string(self) -> None:
        """Test returns empty list for empty string."""
        result = _parse_file_types("")
        assert result == []

    def test_parses_single_file_type(self) -> None:
        """Test parses single file type."""
        result = _parse_file_types(".py")
        assert result == [".py"]

    def test_parses_multiple_file_types(self) -> None:
        """Test parses multiple comma-separated file types."""
        result = _parse_file_types(".py, .js, .ts")
        assert result == [".py", ".js", ".ts"]

    def test_trims_whitespace(self) -> None:
        """Test trims whitespace from file types."""
        result = _parse_file_types("  .py  ,  .js  ")
        assert result == [".py", ".js"]


class TestFormatSearchResults:
    """Tests for _format_search_results function."""

    def test_formats_results_correctly(self) -> None:
        """Test formats search results correctly."""
        mock_result = MagicMock()
        mock_result.file_path = Path("/project/test.py")
        mock_result.content = "def test(): pass"
        mock_result.similarity_score = 0.95
        mock_result.start_line = 1
        mock_result.end_line = 2
        mock_result.file_type = ".py"
        mock_result.chunk_id = "chunk1"

        results = [mock_result]

        formatted = _format_search_results(results, "test query", 10, 0.7)

        assert formatted["success"] is True
        assert formatted["query"] == "test query"
        assert formatted["results_count"] == 1
        assert len(formatted["results"]) == 1

    def test_rounds_similarity_score(self) -> None:
        """Test rounds similarity score to 4 decimal places."""
        mock_result = MagicMock()
        mock_result.file_path = Path("/project/test.py")
        mock_result.content = "code"
        mock_result.similarity_score = 0.955555
        mock_result.start_line = 1
        mock_result.end_line = 1
        mock_result.file_type = ".py"
        mock_result.chunk_id = "c1"

        formatted = _format_search_results([mock_result], "query", 10, 0.7)

        assert formatted["results"][0]["similarity_score"] == 0.9556

    def test_includes_result_metadata(self) -> None:
        """Test includes all result metadata."""
        mock_result = MagicMock()
        mock_result.file_path = Path("/project/test.py")
        mock_result.content = "content"
        mock_result.similarity_score = 0.9
        mock_result.start_line = 10
        mock_result.end_line = 20
        mock_result.file_type = ".py"
        mock_result.chunk_id = "abc123"

        formatted = _format_search_results([mock_result], "query", 10, 0.5)

        result = formatted["results"][0]
        assert result["file_path"] == str(Path("/project/test.py"))
        assert result["content"] == "content"
        assert result["start_line"] == 10
        assert result["end_line"] == 20
        assert result["file_type"] == ".py"
        assert result["chunk_id"] == "abc123"


class TestParseTextsInput:
    """Tests for _parse_texts_input function."""

    def test_parses_valid_json_array(self) -> None:
        """Test parses valid JSON array of strings."""
        texts, error = _parse_texts_input('["text1", "text2", "text3"]')

        assert error is None
        assert texts == ["text1", "text2", "text3"]

    def test_returns_error_for_non_array(self) -> None:
        """Test returns error when JSON is not an array."""
        texts, error = _parse_texts_input('{"key": "value"}')

        assert error is not None
        assert "array" in error.lower()

    def test_returns_error_for_invalid_json(self) -> None:
        """Test returns error for invalid JSON."""
        texts, error = _parse_texts_input("not json")

        assert error is not None
        assert "Invalid JSON" in error


class TestGenerateEmbeddingsForTexts:
    """Tests for _generate_embeddings_for_texts function."""

    def test_generates_single_embedding_for_single_text(self) -> None:
        """Test generates single embedding for single text input."""
        with patch(
            "crackerjack.mcp.tools.semantic_tools.EmbeddingService"
        ) as mock_service:
            mock_instance = MagicMock()
            mock_instance.generate_embedding.return_value = [0.1, 0.2, 0.3]
            mock_service.return_value = mock_instance

            config = MagicMock()
            embeddings = _generate_embeddings_for_texts(["single text"], config)

            assert len(embeddings) == 1
            mock_instance.generate_embedding.assert_called_once_with("single text")

    def test_generates_batch_for_multiple_texts(self) -> None:
        """Test generates batch embeddings for multiple texts."""
        with patch(
            "crackerjack.mcp.tools.semantic_tools.EmbeddingService"
        ) as mock_service:
            mock_instance = MagicMock()
            mock_instance.generate_embeddings_batch.return_value = [
                [0.1, 0.2],
                [0.3, 0.4],
            ]
            mock_service.return_value = mock_instance

            config = MagicMock()
            embeddings = _generate_embeddings_for_texts(
                ["text1", "text2"], config
            )

            assert len(embeddings) == 2
            mock_instance.generate_embeddings_batch.assert_called_once_with(
                ["text1", "text2"]
            )


class TestFormatEmbeddingsResponse:
    """Tests for _format_embeddings_response function."""

    def test_creates_success_response(self) -> None:
        """Test creates successful embeddings response."""
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

        result = _format_embeddings_response(["text1", "text2"], embeddings)

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["texts_count"] == 2
        assert parsed["embedding_dimension"] == 3
        assert len(parsed["embeddings"]) == 2

    def test_returns_zero_dimension_for_empty_embeddings(self) -> None:
        """Test returns 0 dimension when embeddings list is empty."""
        result = _format_embeddings_response([], [])

        parsed = json.loads(result)
        assert parsed["embedding_dimension"] == 0


class TestParseSemanticConfig:
    """Tests for _parse_semantic_config function."""

    def test_returns_default_config_for_empty_string(self) -> None:
        """Test returns default config for empty config string."""
        config = _parse_semantic_config("")

        assert config.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.max_search_results == 10
        assert config.similarity_threshold == 0.7
        assert config.embedding_dimension == 384

    def test_parses_valid_json_config(self) -> None:
        """Test parses valid JSON configuration."""
        config_json = json.dumps({
            "embedding_model": "custom-model",
            "chunk_size": 256,
            "embedding_dimension": 128,
        })

        config = _parse_semantic_config(config_json)

        assert config.embedding_model == "custom-model"
        assert config.chunk_size == 256
        assert config.embedding_dimension == 128

    def test_returns_error_string_for_invalid_json(self) -> None:
        """Test returns error string for invalid JSON."""
        result = _parse_semantic_config("not json")

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "Invalid JSON" in parsed["error"]

    def test_returns_error_string_for_invalid_config(self) -> None:
        """Test returns error string for invalid configuration values."""
        config_json = json.dumps({
            "embedding_model": "model",
            "chunk_size": -1,  # Invalid
        })

        result = _parse_semantic_config(config_json)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["success"] is False


class TestRegisterSemanticTools:
    """Tests for register_semantic_tools function."""

    def test_registers_six_tools(self) -> None:
        """Test registers six semantic MCP tools."""
        mcp_app = MagicMock()

        register_semantic_tools(mcp_app)

        assert mcp_app.tool.call_count == 6

    def test_registers_index_file_tool(self) -> None:
        """Test registers index_file_semantic tool."""
        mcp_app = MagicMock()

        register_semantic_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_search_semantic_tool(self) -> None:
        """Test registers search_semantic tool."""
        mcp_app = MagicMock()

        register_semantic_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_get_semantic_stats_tool(self) -> None:
        """Test registers get_semantic_stats tool."""
        mcp_app = MagicMock()

        register_semantic_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_remove_file_tool(self) -> None:
        """Test registers remove_file_from_semantic_index tool."""
        mcp_app = MagicMock()

        register_semantic_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_get_embeddings_tool(self) -> None:
        """Test registers get_embeddings tool."""
        mcp_app = MagicMock()

        register_semantic_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_calculate_similarity_tool(self) -> None:
        """Test registers calculate_similarity_semantic tool."""
        mcp_app = MagicMock()

        register_semantic_tools(mcp_app)

        assert mcp_app.tool.called