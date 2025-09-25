"""Semantic search and vector store MCP tools for AI agent integration."""

import json
import typing as t
from pathlib import Path

from crackerjack.models.semantic_models import SearchQuery, SemanticConfig
from crackerjack.services.embeddings import EmbeddingService
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
                return json.dumps({
                    "success": False,
                    "error": f"Invalid file path: {path_result.error_message}",
                    "validation_type": path_result.validation_type,
                })

            file_path_obj = Path(path_result.sanitized_value or file_path)

            # Parse configuration
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Initialize vector store with persistent database
            vector_store = VectorStore(config, db_path=_get_persistent_db_path())

            # Index the file
            embeddings = vector_store.index_file(file_path_obj)

            return json.dumps({
                "success": True,
                "chunks_processed": len(embeddings),
                "file_path": str(file_path_obj),
                "embedding_dimension": config.embedding_dimension,
                "message": f"Successfully indexed {len(embeddings)} chunks from {file_path_obj.name}"
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to index file: {str(e)}",
                "file_path": file_path,
            })


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
            validator = get_input_validator()

            # Validate query
            query_result = validator.validate_command_args(query)
            if not query_result.valid:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid query: {query_result.error_message}",
                    "validation_type": query_result.validation_type,
                })

            sanitized_query = query_result.sanitized_value or query

            # Validate parameters
            if not (1 <= max_results <= 100):
                return json.dumps({
                    "success": False,
                    "error": "max_results must be between 1 and 100",
                })

            if not (0.0 <= min_similarity <= 1.0):
                return json.dumps({
                    "success": False,
                    "error": "min_similarity must be between 0.0 and 1.0",
                })

            # Parse file types
            file_types_list = []
            if file_types.strip():
                file_types_list = [ft.strip() for ft in file_types.split(",")]

            # Parse configuration
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Create search query
            search_query = SearchQuery(
                query=sanitized_query,
                max_results=max_results,
                min_similarity=min_similarity,
                file_types=file_types_list,
            )

            # Initialize vector store and search
            vector_store = VectorStore(config, db_path=_get_persistent_db_path())
            results = vector_store.search(search_query)

            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "file_path": str(result.file_path),
                    "content": result.content,
                    "similarity_score": round(result.similarity_score, 4),
                    "start_line": result.start_line,
                    "end_line": result.end_line,
                    "file_type": result.file_type,
                    "chunk_id": result.chunk_id,
                })

            return json.dumps({
                "success": True,
                "query": sanitized_query,
                "results_count": len(results),
                "max_results": max_results,
                "min_similarity": min_similarity,
                "results": formatted_results,
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to perform semantic search: {str(e)}",
                "query": query,
            })


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

            return json.dumps({
                "success": True,
                "total_files": stats.total_files,
                "total_chunks": stats.total_chunks,
                "index_size_mb": stats.index_size_mb,
                "average_chunks_per_file": round(stats.total_chunks / stats.total_files, 2) if stats.total_files > 0 else 0.0,
                "embedding_model": config.embedding_model,
                "embedding_dimension": config.embedding_dimension,
                "last_updated": stats.last_updated.isoformat() if stats.last_updated else None,
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to get semantic stats: {str(e)}",
            })


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
                return json.dumps({
                    "success": False,
                    "error": f"Invalid file path: {path_result.error_message}",
                    "validation_type": path_result.validation_type,
                })

            file_path_obj = Path(path_result.sanitized_value or file_path)

            # Parse configuration
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Initialize vector store and remove file
            vector_store = VectorStore(config, db_path=_get_persistent_db_path())
            success = vector_store.remove_file(file_path_obj)

            return json.dumps({
                "success": success,
                "file_path": str(file_path_obj),
                "message": f"{'Successfully removed' if success else 'Failed to remove'} {file_path_obj.name} from index"
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to remove file: {str(e)}",
                "file_path": file_path,
            })


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
            # Parse texts
            try:
                texts_list = json.loads(texts)
                if not isinstance(texts_list, list):
                    return json.dumps({
                        "success": False,
                        "error": "texts must be a JSON array of strings",
                    })
            except json.JSONDecodeError as e:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid JSON for texts: {str(e)}",
                })

            # Parse configuration
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Generate embeddings
            embedding_service = EmbeddingService(config)

            if len(texts_list) == 1:
                embeddings = [embedding_service.generate_embedding(texts_list[0])]
            else:
                embeddings = embedding_service.generate_embeddings_batch(texts_list)

            return json.dumps({
                "success": True,
                "texts_count": len(texts_list),
                "embedding_dimension": len(embeddings[0]) if embeddings else 0,
                "embeddings": embeddings,
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to generate embeddings: {str(e)}",
            })


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
                    return json.dumps({
                        "success": False,
                        "error": "Both embeddings must be JSON arrays",
                    })
            except json.JSONDecodeError as e:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid JSON for embeddings: {str(e)}",
                })

            # Parse configuration
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):  # Error occurred
                return config

            # Calculate similarity
            embedding_service = EmbeddingService(config)
            similarity = embedding_service.calculate_similarity(emb1, emb2)

            return json.dumps({
                "success": True,
                "similarity_score": round(similarity, 6),
                "embedding1_dimension": len(emb1),
                "embedding2_dimension": len(emb2),
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to calculate similarity: {str(e)}",
            })


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
            embedding_dimension=384
        )

    try:
        config_dict = json.loads(config_json)
        return SemanticConfig(**config_dict)
    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid JSON configuration: {str(e)}",
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid configuration: {str(e)}",
        })