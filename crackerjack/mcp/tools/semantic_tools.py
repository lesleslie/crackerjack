"""Semantic search and vector store MCP tools for AI agent integration."""

import json
import typing as t
from pathlib import Path

from crackerjack.models.semantic_models import SearchQuery, SemanticConfig
from crackerjack.services.ai.embeddings import EmbeddingService
from crackerjack.services.input_validator import get_input_validator
from crackerjack.services.vector_store import VectorStore


def _get_persistent_db_path() -> Path:
    """Get the path to the persistent semantic search database."""
    db_path = Path.cwd() / ".crackerjack" / "semantic_index.db"
    db_path.parent.mkdir(exist_ok=True)
    return db_path


def register_semantic_tools(mcp_app: t.Any) -> None:
    """Register all semantic search tools with the MCP server."""
    _register_index_file_tool(mcp_app)
    _register_search_semantic_tool(mcp_app)
    _register_get_semantic_stats_tool(mcp_app)
    _register_remove_file_from_index_tool(mcp_app)
    _register_get_embeddings_tool(mcp_app)
    _register_calculate_similarity_tool(mcp_app)


def _register_index_file_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def index_file_semantic(
        file_path: str,
        config_json: str = "",
    ) -> str:
        """Index a file for semantic search.

        Args:
            file_path: Path to the file to index
            config_json: Optional JSON configuration for semantic search settings

        Returns:
            JSON string with indexing results
        """
        try:
            validator = get_input_validator()

            # Validate file path
            path_result = validator.validate_file_path(file_path)
            if not path_result.valid:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid file path: {path_result.error_message}",
                        "validation_type": path_result.validation_type,
                    }
                )

            file_path_obj = Path(path_result.sanitized_value or file_path)

            # Parse configuration
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Initialize vector store with persistent database
            vector_store = VectorStore(config, db_path=_get_persistent_db_path())

            # Index the file
            embeddings = vector_store.index_file(file_path_obj)

            return json.dumps(
                {
                    "success": True,
                    "chunks_processed": len(embeddings),
                    "file_path": str(file_path_obj),
                    "embedding_dimension": config.embedding_dimension,
                    "message": f"Successfully indexed {len(embeddings)} chunks from {file_path_obj.name}",
                }
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to index file: {e}",
                    "file_path": file_path,
                }
            )


def _register_search_semantic_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def search_semantic(
        query: str,
        max_results: int = 10,
        min_similarity: float = 0.7,
        file_types: str = "",
        config_json: str = "",
    ) -> str:
        """Perform semantic search across indexed files.

        Args:
            query: The search query text
            max_results: Maximum number of results to return (1-100)
            min_similarity: Minimum similarity threshold (0.0-1.0)
            file_types: Comma-separated list of file types to filter by
            config_json: Optional JSON configuration for semantic search settings

        Returns:
            JSON string with search results
        """
        try:
            # Validate query
            sanitized_query, query_error = _validate_search_query(query)
            if query_error:
                return _create_error_response(
                    query_error,
                    validation_type="query_validation",
                )

            # Validate parameters
            param_error = _validate_search_parameters(max_results, min_similarity)
            if param_error:
                return _create_error_response(param_error)

            # Parse file types and configuration
            file_types_list = _parse_file_types(file_types)
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Create search query and execute search
            search_query = SearchQuery(
                query=sanitized_query,
                max_results=max_results,
                min_similarity=min_similarity,
                file_types=file_types_list,
            )

            vector_store = VectorStore(config, db_path=_get_persistent_db_path())
            results = vector_store.search(search_query)

            # Format and return results
            response_data = _format_search_results(
                results, sanitized_query, max_results, min_similarity
            )
            return json.dumps(response_data)

        except Exception as e:
            return _create_error_response(
                f"Failed to perform semantic search: {e}",
                query=query,
            )


def _register_get_semantic_stats_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def get_semantic_stats(config_json: str = "") -> str:
        """Get statistics about the semantic search index.

        Args:
            config_json: Optional JSON configuration for semantic search settings

        Returns:
            JSON string with index statistics
        """
        try:
            # Parse configuration
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Initialize vector store and get stats
            vector_store = VectorStore(config, db_path=_get_persistent_db_path())
            stats = vector_store.get_stats()

            return json.dumps(
                {
                    "success": True,
                    "total_files": stats.total_files,
                    "total_chunks": stats.total_chunks,
                    "index_size_mb": stats.index_size_mb,
                    "average_chunks_per_file": round(
                        stats.total_chunks / stats.total_files, 2
                    )
                    if stats.total_files > 0
                    else 0.0,
                    "embedding_model": config.embedding_model,
                    "embedding_dimension": config.embedding_dimension,
                    "last_updated": stats.last_updated.isoformat()
                    if stats.last_updated
                    else None,
                }
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to get semantic stats: {e}",
                }
            )


def _register_remove_file_from_index_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def remove_file_from_semantic_index(
        file_path: str,
        config_json: str = "",
    ) -> str:
        """Remove a file from the semantic search index.

        Args:
            file_path: Path to the file to remove
            config_json: Optional JSON configuration for semantic search settings

        Returns:
            JSON string with removal results
        """
        try:
            validator = get_input_validator()

            # Validate file path
            path_result = validator.validate_file_path(file_path)
            if not path_result.valid:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid file path: {path_result.error_message}",
                        "validation_type": path_result.validation_type,
                    }
                )

            file_path_obj = Path(path_result.sanitized_value or file_path)

            # Parse configuration
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Initialize vector store and remove file
            vector_store = VectorStore(config, db_path=_get_persistent_db_path())
            success = vector_store.remove_file(file_path_obj)

            return json.dumps(
                {
                    "success": success,
                    "file_path": str(file_path_obj),
                    "message": f"{'Successfully removed' if success else 'Failed to remove'} {file_path_obj.name} from index",
                }
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to remove file: {e}",
                    "file_path": file_path,
                }
            )


def _register_get_embeddings_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def get_embeddings(
        texts: str,
        config_json: str = "",
    ) -> str:
        """Generate embeddings for given texts.

        Args:
            texts: JSON array of texts to generate embeddings for
            config_json: Optional JSON configuration for semantic search settings

        Returns:
            JSON string with embeddings
        """
        try:
            # Parse and validate input texts
            texts_list, parse_error = _parse_texts_input(texts)
            if parse_error:
                return parse_error

            # Parse configuration
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Generate embeddings
            embeddings = _generate_embeddings_for_texts(texts_list, config)

            return _format_embeddings_response(texts_list, embeddings)

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to generate embeddings: {e}",
                }
            )


def _register_calculate_similarity_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def calculate_similarity_semantic(
        embedding1: str,
        embedding2: str,
        config_json: str = "",
    ) -> str:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: JSON array representing first embedding vector
            embedding2: JSON array representing second embedding vector
            config_json: Optional JSON configuration for semantic search settings

        Returns:
            JSON string with similarity score
        """
        try:
            # Parse embeddings
            try:
                emb1 = json.loads(embedding1)
                emb2 = json.loads(embedding2)

                if not (isinstance(emb1, list) and isinstance(emb2, list)):
                    return json.dumps(
                        {
                            "success": False,
                            "error": "Both embeddings must be JSON arrays",
                        }
                    )
            except json.JSONDecodeError as e:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid JSON for embeddings: {e}",
                    }
                )

            # Parse configuration
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Calculate similarity
            embedding_service = EmbeddingService(config)
            similarity = embedding_service.calculate_similarity(emb1, emb2)

            return json.dumps(
                {
                    "success": True,
                    "similarity_score": round(similarity, 6),
                    "embedding1_dimension": len(emb1),
                    "embedding2_dimension": len(emb2),
                }
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to calculate similarity: {e}",
                }
            )


def _create_error_response(error: str, **kwargs) -> str:
    """Create standardized error response JSON.

    Args:
        error: Error message
        **kwargs: Additional fields to include in response

    Returns:
        JSON string with error response
    """
    response = {
        "success": False,
        "error": error,
    }
    response.update(kwargs)
    return json.dumps(response)


def _validate_search_query(query: str) -> tuple[str, str | None]:
    """Validate and sanitize search query.

    Args:
        query: Raw search query

    Returns:
        Tuple of (sanitized_query, error_message)
    """
    validator = get_input_validator()
    query_result = validator.validate_command_args(query)

    if not query_result.valid:
        error_msg = f"Invalid query: {query_result.error_message}"
        return "", error_msg

    return query_result.sanitized_value or query, None


def _validate_search_parameters(max_results: int, min_similarity: float) -> str | None:
    """Validate search parameters.

    Args:
        max_results: Maximum results to return
        min_similarity: Minimum similarity threshold

    Returns:
        Error message if invalid, None if valid
    """
    if not (1 <= max_results <= 100):
        return "max_results must be between 1 and 100"

    if not (0.0 <= min_similarity <= 1.0):
        return "min_similarity must be between 0.0 and 1.0"

    return None


def _parse_file_types(file_types: str) -> list[str]:
    """Parse comma-separated file types string.

    Args:
        file_types: Comma-separated file types

    Returns:
        List of file type strings
    """
    if not file_types.strip():
        return []
    return [ft.strip() for ft in file_types.split(",")]


def _format_search_results(
    results: list,
    sanitized_query: str,
    max_results: int,
    min_similarity: float,
) -> dict:
    """Format search results for JSON response.

    Args:
        results: Search results from vector store
        sanitized_query: Sanitized search query
        max_results: Maximum results requested
        min_similarity: Minimum similarity threshold

    Returns:
        Dictionary with formatted results
    """
    formatted_results = [
        {
            "file_path": str(result.file_path),
            "content": result.content,
            "similarity_score": round(result.similarity_score, 4),
            "start_line": result.start_line,
            "end_line": result.end_line,
            "file_type": result.file_type,
            "chunk_id": result.chunk_id,
        }
        for result in results
    ]

    return {
        "success": True,
        "query": sanitized_query,
        "results_count": len(results),
        "max_results": max_results,
        "min_similarity": min_similarity,
        "results": formatted_results,
    }


def _parse_texts_input(texts: str) -> tuple[list[str], str | None]:
    """Parse and validate texts input.

    Args:
        texts: JSON string containing array of texts

    Returns:
        Tuple of (texts_list, error_message)
    """
    try:
        texts_list = json.loads(texts)
        if not isinstance(texts_list, list):
            error = json.dumps(
                {
                    "success": False,
                    "error": "texts must be a JSON array of strings",
                }
            )
            return [], error
        return texts_list, None
    except json.JSONDecodeError as e:
        error = json.dumps(
            {
                "success": False,
                "error": f"Invalid JSON for texts: {e}",
            }
        )
        return [], error


def _generate_embeddings_for_texts(
    texts_list: list[str], config: SemanticConfig
) -> list:
    """Generate embeddings for a list of texts.

    Args:
        texts_list: List of texts to generate embeddings for
        config: Semantic search configuration

    Returns:
        List of embedding vectors
    """
    embedding_service = EmbeddingService(config)

    if len(texts_list) == 1:
        return [embedding_service.generate_embedding(texts_list[0])]
    return embedding_service.generate_embeddings_batch(texts_list)


def _format_embeddings_response(texts_list: list[str], embeddings: list) -> str:
    """Format embeddings response as JSON.

    Args:
        texts_list: Original list of texts
        embeddings: Generated embeddings

    Returns:
        JSON string with formatted response
    """
    return json.dumps(
        {
            "success": True,
            "texts_count": len(texts_list),
            "embedding_dimension": len(embeddings[0]) if embeddings else 0,
            "embeddings": embeddings,
        }
    )


def _parse_semantic_config(config_json: str) -> SemanticConfig | str:
    """Parse semantic configuration from JSON string.

    Args:
        config_json: JSON configuration string

    Returns:
        SemanticConfig object or error string
    """
    if not config_json.strip():
        # Use default configuration
        return SemanticConfig(
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            chunk_size=512,
            chunk_overlap=50,
            max_search_results=10,
            similarity_threshold=0.7,
            embedding_dimension=384,
        )

    try:
        config_dict = json.loads(config_json)
        return SemanticConfig(**config_dict)
    except json.JSONDecodeError as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid JSON configuration: {e}",
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid configuration: {e}",
            }
        )
