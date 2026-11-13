import json
import typing as t
from pathlib import Path

from crackerjack.models.semantic_models import SearchQuery, SemanticConfig
from crackerjack.services.ai.embeddings import EmbeddingService
from crackerjack.services.input_validator import get_input_validator
from crackerjack.services.vector_store import VectorStore


def _get_persistent_db_path() -> Path:
    db_path = Path.cwd() / ".crackerjack" / "semantic_index.db"
    db_path.parent.mkdir(exist_ok=True)
    return db_path


def register_semantic_tools(mcp_app: t.Any) -> None:
    _register_index_file_tool(mcp_app)
    _register_search_semantic_tool(mcp_app)
    _register_get_semantic_stats_tool(mcp_app)
    _register_remove_file_from_index_tool(mcp_app)
    _register_get_embeddings_tool(mcp_app)
    _register_calculate_similarity_tool(mcp_app)


def _register_index_file_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def crackerjack_index_file_semantic(
        file_path: str,
        config_json: str = "",
    ) -> str:
        """Index a file into the semantic search index.

        Chunks the file, embeds each chunk and stores the vectors in the
        persistent index, making the file's content retrievable by
        ``crackerjack_search_semantic``.

        Parameters
        ----------
        file_path
            Path of the file to index. Validated against path traversal.
        config_json
            Optional JSON object overriding the semantic config
            (embedding model, chunk size, chunk overlap, similarity
            threshold, embedding dimension). Defaults to the standard
            MiniLM configuration.

        Returns
        -------
        str
            JSON string with ``success``, ``chunks_processed``,
            ``file_path``, ``embedding_dimension`` and a ``message``.
        """
        try:
            validator = get_input_validator()

            path_result = validator.validate_file_path(file_path)
            if not path_result.valid:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid file path: {path_result.error_message}",
                        "validation_type": path_result.validation_type,
                    },
                )

            file_path_obj = Path(path_result.sanitized_value or file_path)

            config = _parse_semantic_config(config_json)
            if isinstance(config, str):
                return config

            vector_store = VectorStore(config, db_path=_get_persistent_db_path())

            embeddings = vector_store.index_file(file_path_obj)

            return json.dumps(
                {
                    "success": True,
                    "chunks_processed": len(embeddings),
                    "file_path": file_path_obj,
                    "embedding_dimension": config.embedding_dimension,
                    "message": f"Successfully indexed {len(embeddings)} chunks from {file_path_obj.name}",
                },
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to index file: {e}",
                    "file_path": file_path,
                },
            )


def _register_search_semantic_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def crackerjack_search_semantic(
        query: str,
        max_results: int = 10,
        min_similarity: float = 0.7,
        file_types: str = "",
        config_json: str = "",
    ) -> str:
        """Search indexed code by meaning rather than by literal text.

        Embeds the query and returns the indexed chunks closest to it in
        embedding space. Use this for conceptual lookups; use
        ``crackerjack_search_code`` for literal regular expressions.

        Parameters
        ----------
        query
            Natural-language description of what to find.
        max_results
            Maximum number of results to return (1-100, default 10).
        min_similarity
            Minimum cosine similarity a chunk must reach to be returned
            (0.0-1.0, default 0.7).
        file_types
            Comma-separated file extensions to restrict results to.
            Empty means any file type.
        config_json
            Optional JSON object overriding the semantic config. It must
            match the config used when the index was built, or the
            embeddings will not compare.

        Returns
        -------
        str
            JSON string with ``success``, ``query``, ``results_count``,
            ``max_results``, ``min_similarity`` and ``results`` (file
            path, content, similarity score, start and end line, file
            type, chunk id). ``status`` is ``degraded`` when the index is
            empty, otherwise ``ok``.
        """
        try:
            sanitized_query, query_error = _validate_search_query(query)
            if query_error:
                return _create_error_response(
                    query_error,
                    validation_type="query_validation",
                )

            param_error = _validate_search_parameters(max_results, min_similarity)
            if param_error:
                return _create_error_response(param_error)

            file_types_list = _parse_file_types(file_types)
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):
                return config

            search_query = SearchQuery(
                query=sanitized_query,
                max_results=max_results,
                min_similarity=min_similarity,
                file_types=file_types_list,
            )

            vector_store = VectorStore(config, db_path=_get_persistent_db_path())
            results = vector_store.search(search_query)

            stats = vector_store.get_stats()
            index_empty = stats.total_chunks == 0

            response_data = _format_search_results(
                results,
                sanitized_query,
                max_results,
                min_similarity,
            )

            if index_empty:
                response_data["status"] = "degraded"
                response_data["hint"] = (
                    "Semantic index is empty. Run the reindex procedure "
                    "documented in crackerjack/docs/operations/reindex.md "
                    "to populate the index, or call `crackerjack_index_file_semantic` "
                    "with files you want searchable."
                )
            elif not results:
                response_data["status"] = "ok"
                response_data["hint"] = (
                    "Index is populated, but no chunk reached "
                    f"min_similarity={min_similarity}."
                )
            else:
                response_data["status"] = "ok"

            return json.dumps(response_data)

        except Exception as e:
            return _create_error_response(
                f"Failed to perform semantic search: {e}",
                query=query,
            )


def _register_get_semantic_stats_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def crackerjack_get_semantic_stats(config_json: str = "") -> str:
        """Report statistics about the semantic index.

        Summarises the indexed corpus: how many files and chunks are
        held, the on-disk size, the average chunks per file and the
        embedding configuration in use.

        Parameters
        ----------
        config_json
            Optional JSON object overriding the semantic config, so the
            stats describe the index that config points at.

        Returns
        -------
        str
            JSON string with ``success``, ``total_files``,
            ``total_chunks``, ``index_size_mb``,
            ``average_chunks_per_file``, ``embedding_model``,
            ``embedding_dimension`` and ``last_updated``.
        """
        try:
            config = _parse_semantic_config(config_json)
            if isinstance(config, str):
                return config

            vector_store = VectorStore(config, db_path=_get_persistent_db_path())
            stats = vector_store.get_stats()

            return json.dumps(
                {
                    "success": True,
                    "total_files": stats.total_files,
                    "total_chunks": stats.total_chunks,
                    "index_size_mb": stats.index_size_mb,
                    "average_chunks_per_file": round(
                        stats.total_chunks / stats.total_files,
                        2,
                    )
                    if stats.total_files > 0
                    else 0.0,
                    "embedding_model": config.embedding_model,
                    "embedding_dimension": config.embedding_dimension,
                    "last_updated": stats.last_updated.isoformat()
                    if stats.last_updated
                    else None,
                },
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to get semantic stats: {e}",
                },
            )


def _register_remove_file_from_index_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def crackerjack_remove_file_from_semantic_index(
        file_path: str,
        config_json: str = "",
    ) -> str:
        """Remove a file's content from the semantic index.

        Drops every chunk belonging to the file so it stops appearing in
        semantic search results. The file itself is not touched on disk.

        Parameters
        ----------
        file_path
            Path of the file to remove from the index. Validated against
            path traversal.
        config_json
            Optional JSON object overriding the semantic config. It must
            match the config used when the file was indexed.

        Returns
        -------
        str
            JSON string with ``success``, ``file_path`` and a
            ``message`` reporting whether the removal took effect.
        """
        try:
            validator = get_input_validator()

            path_result = validator.validate_file_path(file_path)
            if not path_result.valid:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid file path: {path_result.error_message}",
                        "validation_type": path_result.validation_type,
                    },
                )

            file_path_obj = Path(path_result.sanitized_value or file_path)

            config = _parse_semantic_config(config_json)
            if isinstance(config, str):
                return config

            vector_store = VectorStore(config, db_path=_get_persistent_db_path())
            success = vector_store.remove_file(file_path_obj)

            return json.dumps(
                {
                    "success": success,
                    "file_path": file_path_obj,
                    "message": f"{'Successfully removed' if success else 'Failed to remove'} {file_path_obj.name} from index",
                },
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to remove file: {e}",
                    "file_path": file_path,
                },
            )


def _register_get_embeddings_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def crackerjack_get_embeddings(
        texts: str,
        config_json: str = "",
    ) -> str:
        """Generate embedding vectors for a list of texts.

        Embeds each text with the configured embedding model, batching
        the work when more than one text is supplied. Use the returned
        vectors with ``crackerjack_calculate_similarity_semantic``.

        Parameters
        ----------
        texts
            JSON array of strings to embed.
        config_json
            Optional JSON object overriding the semantic config
            (embedding model and embedding dimension).

        Returns
        -------
        str
            JSON string with ``success``, ``texts_count``,
            ``embedding_dimension`` and the ``embeddings`` themselves.
        """
        try:
            texts_list, parse_error = _parse_texts_input(texts)
            if parse_error:
                return parse_error

            config = _parse_semantic_config(config_json)
            if isinstance(config, str):
                return config

            embeddings = _generate_embeddings_for_texts(texts_list, config)

            return _format_embeddings_response(texts_list, embeddings)

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to generate embeddings: {e}",
                },
            )


def _register_calculate_similarity_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def crackerjack_calculate_similarity_semantic(
        embedding1: str,
        embedding2: str,
        config_json: str = "",
    ) -> str:
        """Calculate the similarity between two embedding vectors.

        Compares two embeddings with the configured embedding service and
        returns the similarity score. Obtain the vectors from
        ``crackerjack_get_embeddings``.

        Parameters
        ----------
        embedding1
            JSON array of floats — the first embedding vector.
        embedding2
            JSON array of floats — the second embedding vector.
        config_json
            Optional JSON object overriding the semantic config, so the
            service uses the same model that produced the vectors.

        Returns
        -------
        str
            JSON string with ``success``, ``similarity_score``,
            ``embedding1_dimension`` and ``embedding2_dimension``.
        """
        try:
            try:
                emb1 = json.loads(embedding1)
                emb2 = json.loads(embedding2)

                if not (isinstance(emb1, list) and isinstance(emb2, list)):
                    return json.dumps(
                        {
                            "success": False,
                            "error": "Both embeddings must be JSON arrays",
                        },
                    )
            except json.JSONDecodeError as e:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid JSON for embeddings: {e}",
                    },
                )

            config = _parse_semantic_config(config_json)
            if isinstance(config, str):
                return config

            embedding_service = EmbeddingService(config)
            similarity = embedding_service.calculate_similarity(emb1, emb2)

            return json.dumps(
                {
                    "success": True,
                    "similarity_score": round(similarity, 6),
                    "embedding1_dimension": len(emb1),
                    "embedding2_dimension": len(emb2),
                },
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to calculate similarity: {e}",
                },
            )


def _create_error_response(error: str, **kwargs) -> str:
    response = {
        "success": False,
        "error": error,
    }
    response.update(kwargs)
    return json.dumps(response)


def _validate_search_query(query: str) -> tuple[str, str | None]:
    validator = get_input_validator()
    query_result = validator.validate_command_args(query)

    if not query_result.valid:
        error_msg = f"Invalid query: {query_result.error_message}"
        return "", error_msg

    return query_result.sanitized_value or query, None


def _validate_search_parameters(max_results: int, min_similarity: float) -> str | None:
    if not (1 <= max_results <= 100):
        return "max_results must be between 1 and 100"

    if not (0.0 <= min_similarity <= 1.0):
        return "min_similarity must be between 0.0 and 1.0"

    return None


def _parse_file_types(file_types: str) -> list[str]:
    if not file_types.strip():
        return []
    return [ft.strip() for ft in file_types.split(", ")]


def _format_search_results(
    results: list,
    sanitized_query: str,
    max_results: int,
    min_similarity: float,
) -> dict:
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
    try:
        texts_list = json.loads(texts)
        if not isinstance(texts_list, list):
            error = json.dumps(
                {
                    "success": False,
                    "error": "texts must be a JSON array of strings",
                },
            )
            return [], error
        return texts_list, None
    except json.JSONDecodeError as e:
        error = json.dumps(
            {
                "success": False,
                "error": f"Invalid JSON for texts: {e}",
            },
        )
        return [], error


def _generate_embeddings_for_texts(
    texts_list: list[str],
    config: SemanticConfig,
) -> list:
    embedding_service = EmbeddingService(config)

    if len(texts_list) == 1:
        return [embedding_service.generate_embedding(texts_list[0])]
    return embedding_service.generate_embeddings_batch(texts_list)


def _format_embeddings_response(texts_list: list[str], embeddings: list) -> str:
    return json.dumps(
        {
            "success": True,
            "texts_count": len(texts_list),
            "embedding_dimension": len(embeddings[0]) if embeddings else 0,
            "embeddings": embeddings,
        },
    )


def _parse_semantic_config(config_json: str) -> SemanticConfig | str:
    if not config_json.strip():
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
            },
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid configuration: {e}",
            },
        )
