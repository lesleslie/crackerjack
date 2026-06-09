"""Tests for ``crackerjack.mcp.tools.semantic_tools``.

We exercise the public tool functions and helpers by mocking ``VectorStore`` and
``EmbeddingService`` at the module boundary. The MCP `@mcp_app.tool()`
registration is verified via a mock app.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.mcp.tools import semantic_tools
from crackerjack.mcp.tools.semantic_tools import (
    register_semantic_tools,
)
from crackerjack.models.semantic_models import IndexStats, SearchResult


# ─── helpers ────────────────────────────────────────────────────────────────


def _result(
    path: str = "/p/file.py",
    chunk_id: str = "c1",
    content: str = "match content",
    score: float = 0.85,
    start: int = 1,
    end: int = 5,
    ftype: str = "python",
) -> SearchResult:
    return SearchResult(
        file_path=Path(path),
        chunk_id=chunk_id,
        content=content,
        similarity_score=score,
        start_line=start,
        end_line=end,
        file_type=ftype,
    )


def _stats(
    total_files: int = 3,
    total_chunks: int = 12,
    size_mb: float = 1.5,
    last: datetime | None = None,
) -> IndexStats:
    return IndexStats(
        total_files=total_files,
        total_chunks=total_chunks,
        index_size_mb=size_mb,
        last_updated=last or datetime(2026, 1, 1),
        file_types={"python": 3},
        embedding_model="all-MiniLM-L6-v2",
        avg_chunk_size=120.0,
    )


def _validate_result(
    valid: bool = True,
    sanitized: str = "x",
    error: str = "",
    vtype: str = "command_args",
) -> MagicMock:
    res = MagicMock()
    res.valid = valid
    res.sanitized_value = sanitized
    res.error_message = error
    res.validation_type = vtype
    return res


# ─── register_semantic_tools ────────────────────────────────────────────────


@pytest.mark.unit
class TestRegisterSemanticTools:
    def test_registers_all_six_tools(self) -> None:
        mock_app = MagicMock()
        register_semantic_tools(mock_app)
        # 6 tools registered
        assert mock_app.tool.call_count == 6

    def test_registers_expected_tool_names(self) -> None:
        mock_app = MagicMock()
        registered: list[str] = []

        def tool_decorator() -> t.Any:  # type: ignore[name-defined]
            def decorator(func: t.Any) -> t.Any:  # type: ignore[name-defined]
                registered.append(func.__name__)
                return func
            return decorator

        mock_app.tool = tool_decorator  # type: ignore[method-assign]
        register_semantic_tools(mock_app)

        for name in (
            "index_file_semantic",
            "search_semantic",
            "get_semantic_stats",
            "remove_file_from_semantic_index",
            "get_embeddings",
            "calculate_similarity_semantic",
        ):
            assert name in registered


# ─── _get_persistent_db_path ────────────────────────────────────────────────


@pytest.mark.unit
class TestPersistentDbPath:
    def test_returns_cwd_dot_crackerjack(self, tmp_path: Path) -> None:
        with patch.object(Path, "cwd", return_value=tmp_path):
            db_path = semantic_tools._get_persistent_db_path()
        assert db_path == tmp_path / ".crackerjack" / "semantic_index.db"
        assert (tmp_path / ".crackerjack").exists()


# ─── _parse_semantic_config ─────────────────────────────────────────────────


@pytest.mark.unit
class TestParseSemanticConfig:
    def test_empty_returns_default(self) -> None:
        cfg = semantic_tools._parse_semantic_config("")
        assert not isinstance(cfg, str)
        assert cfg.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert cfg.embedding_dimension == 384
        assert cfg.chunk_size == 512

    def test_whitespace_only_returns_default(self) -> None:
        cfg = semantic_tools._parse_semantic_config("   ")
        assert not isinstance(cfg, str)
        assert cfg.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"

    def test_valid_json_creates_config(self) -> None:
        cfg = semantic_tools._parse_semantic_config(
            json.dumps(
                {
                    "embedding_model": "all-MiniLM-L6-v2",
                    "chunk_size": 256,
                    "chunk_overlap": 25,
                    "max_search_results": 5,
                    "similarity_threshold": 0.5,
                    "embedding_dimension": 384,
                },
            ),
        )
        assert not isinstance(cfg, str)
        assert cfg.chunk_size == 256
        assert cfg.chunk_overlap == 25
        assert cfg.max_search_results == 5

    def test_invalid_json_returns_error_string(self) -> None:
        result = semantic_tools._parse_semantic_config("{not valid")
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "Invalid JSON" in parsed["error"]

    def test_invalid_config_returns_error_string(self) -> None:
        # chunk_size has ge=100, le=2000, so 5 should fail validation
        result = semantic_tools._parse_semantic_config(
            json.dumps({"chunk_size": 5}),
        )
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "Invalid configuration" in parsed["error"]


# ─── _parse_texts_input ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestParseTextsInput:
    def test_valid_list(self) -> None:
        texts, err = semantic_tools._parse_texts_input(json.dumps(["a", "b"]))
        assert err is None
        assert texts == ["a", "b"]

    def test_non_list_returns_error(self) -> None:
        texts, err = semantic_tools._parse_texts_input(json.dumps({"a": 1}))
        assert texts == []
        assert err is not None
        parsed = json.loads(err)
        assert parsed["success"] is False
        assert "texts must be a JSON array" in parsed["error"]

    def test_invalid_json(self) -> None:
        texts, err = semantic_tools._parse_texts_input("[bad")
        assert texts == []
        assert err is not None
        parsed = json.loads(err)
        assert "Invalid JSON" in parsed["error"]


# ─── _parse_file_types / _validate_search_parameters / _validate_search_query


@pytest.mark.unit
class TestParseFileTypes:
    def test_empty_string_returns_empty(self) -> None:
        assert semantic_tools._parse_file_types("") == []

    def test_whitespace_only_returns_empty(self) -> None:
        assert semantic_tools._parse_file_types("   ") == []

    def test_splits_on_comma(self) -> None:
        assert semantic_tools._parse_file_types("python, rust, go") == [
            "python",
            "rust",
            "go",
        ]


@pytest.mark.unit
class TestValidateSearchParameters:
    def test_valid(self) -> None:
        assert semantic_tools._validate_search_parameters(10, 0.5) is None

    def test_max_results_too_low(self) -> None:
        msg = semantic_tools._validate_search_parameters(0, 0.5)
        assert msg is not None
        assert "max_results" in msg

    def test_max_results_too_high(self) -> None:
        msg = semantic_tools._validate_search_parameters(101, 0.5)
        assert msg is not None
        assert "max_results" in msg

    def test_min_similarity_below_zero(self) -> None:
        msg = semantic_tools._validate_search_parameters(10, -0.1)
        assert msg is not None
        assert "min_similarity" in msg

    def test_min_similarity_above_one(self) -> None:
        msg = semantic_tools._validate_search_parameters(10, 1.1)
        assert msg is not None
        assert "min_similarity" in msg

    def test_boundary_values(self) -> None:
        assert semantic_tools._validate_search_parameters(1, 0.0) is None
        assert semantic_tools._validate_search_parameters(100, 1.0) is None


@pytest.mark.unit
class TestValidateSearchQuery:
    def test_valid(self) -> None:
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv:
            mock_giv.return_value.validate_command_args = MagicMock(
                return_value=_validate_result(valid=True, sanitized="hello"),
            )
            sanitized, err = semantic_tools._validate_search_query("hello")
        assert err is None
        assert sanitized == "hello"

    def test_invalid_returns_error(self) -> None:
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv:
            mock_giv.return_value.validate_command_args = MagicMock(
                return_value=_validate_result(
                    valid=False, error="bad chars",
                ),
            )
            sanitized, err = semantic_tools._validate_search_query("rm -rf")
        assert err is not None
        assert "Invalid query" in err
        assert sanitized == ""


# ─── _format_search_results / _format_embeddings_response ───────────────────


@pytest.mark.unit
class TestFormatSearchResults:
    def test_empty_results(self) -> None:
        out = semantic_tools._format_search_results([], "q", 10, 0.5)
        assert out["success"] is True
        assert out["query"] == "q"
        assert out["results_count"] == 0
        assert out["max_results"] == 10
        assert out["min_similarity"] == 0.5
        assert out["results"] == []

    def test_round_similarity(self) -> None:
        out = semantic_tools._format_search_results(
            [_result(score=0.123456789)],
            "q",
            1,
            0.5,
        )
        assert out["results"][0]["similarity_score"] == 0.1235
        assert out["results"][0]["file_type"] == "python"


@pytest.mark.unit
class TestFormatEmbeddingsResponse:
    def test_with_embeddings(self) -> None:
        out = json.loads(
            semantic_tools._format_embeddings_response(
                ["a", "b"],
                [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            ),
        )
        assert out["success"] is True
        assert out["texts_count"] == 2
        assert out["embedding_dimension"] == 3

    def test_empty_embeddings(self) -> None:
        out = json.loads(
            semantic_tools._format_embeddings_response([], []),
        )
        assert out["texts_count"] == 0
        assert out["embedding_dimension"] == 0


# ─── _create_error_response ─────────────────────────────────────────────────


@pytest.mark.unit
class TestCreateErrorResponse:
    def test_minimal(self) -> None:
        out = json.loads(semantic_tools._create_error_response("oops"))
        assert out == {"success": False, "error": "oops"}

    def test_with_kwargs(self) -> None:
        out = json.loads(
            semantic_tools._create_error_response(
                "bad", query="q", validation_type="x",
            ),
        )
        assert out["query"] == "q"
        assert out["validation_type"] == "x"


# ─── _generate_embeddings_for_texts ─────────────────────────────────────────


@pytest.mark.unit
class TestGenerateEmbeddingsForTexts:
    def test_single_text_uses_generate_embedding(self) -> None:
        cfg = semantic_tools._parse_semantic_config("")
        assert not isinstance(cfg, str)
        with patch(
            "crackerjack.mcp.tools.semantic_tools.EmbeddingService",
        ) as mock_cls:
            mock_svc = MagicMock()
            mock_svc.generate_embedding.return_value = [0.1, 0.2]
            mock_cls.return_value = mock_svc
            out = semantic_tools._generate_embeddings_for_texts(["x"], cfg)
        assert out == [[0.1, 0.2]]
        mock_svc.generate_embedding.assert_called_once_with("x")
        mock_svc.generate_embeddings_batch.assert_not_called()

    def test_multiple_texts_uses_batch(self) -> None:
        cfg = semantic_tools._parse_semantic_config("")
        assert not isinstance(cfg, str)
        with patch(
            "crackerjack.mcp.tools.semantic_tools.EmbeddingService",
        ) as mock_cls:
            mock_svc = MagicMock()
            mock_svc.generate_embeddings_batch.return_value = [
                [0.1], [0.2],
            ]
            mock_cls.return_value = mock_svc
            out = semantic_tools._generate_embeddings_for_texts(["x", "y"], cfg)
        assert out == [[0.1], [0.2]]
        mock_svc.generate_embeddings_batch.assert_called_once()
        mock_svc.generate_embedding.assert_not_called()


# ─── tool: index_file_semantic (via register) ──────────────────────────────


@pytest.mark.unit
class TestIndexFileSemantic:
    def _tool(self) -> t.Any:  # type: ignore[name-defined]
        mock_app = MagicMock()
        captured: list[t.Any] = []

        def decorator() -> t.Any:  # type: ignore[name-defined]
            def wrap(func: t.Any) -> t.Any:  # type: ignore[name-defined]
                captured.append(func)
                return func
            return wrap

        mock_app.tool = decorator  # type: ignore[method-assign]
        register_semantic_tools(mock_app)
        for fn in captured:
            if fn.__name__ == "index_file_semantic":
                return fn
        raise AssertionError("index_file_semantic not registered")

    def test_invalid_path(self, tmp_path: Path) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv:
            mock_giv.return_value.validate_file_path = MagicMock(
                return_value=_validate_result(
                    valid=False, error="bad path", vtype="path",
                ),
            )
            out = json.loads(asyncio_run(tool("not-valid", "")))
        assert out["success"] is False
        assert out["validation_type"] == "path"
        assert "Invalid file path" in out["error"]

    def test_success(self, tmp_path: Path) -> None:
        tool = self._tool()
        target = tmp_path / "x.py"
        target.write_text("print('hi')")
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv, patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_giv.return_value.validate_file_path = MagicMock(
                return_value=_validate_result(
                    valid=True, sanitized=str(target),
                ),
            )
            mock_vs.return_value.index_file.return_value = [
                [0.1], [0.2],
            ]
            out = json.loads(asyncio_run(tool(str(target), "")))
        assert out["success"] is True
        assert out["chunks_processed"] == 2
        assert out["embedding_dimension"] == 384
        assert "Successfully indexed" in out["message"]

    def test_exception_returns_error(self, tmp_path: Path) -> None:
        tool = self._tool()
        target = tmp_path / "x.py"
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv, patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_giv.return_value.validate_file_path = MagicMock(
                return_value=_validate_result(
                    valid=True, sanitized=str(target),
                ),
            )
            mock_vs.return_value.index_file.side_effect = RuntimeError(
                "db down",
            )
            out = json.loads(asyncio_run(tool(str(target), "")))
        assert out["success"] is False
        assert "db down" in out["error"]


# ─── tool: search_semantic ─────────────────────────────────────────────────


@pytest.mark.unit
class TestSearchSemantic:
    def _tool(self) -> t.Any:  # type: ignore[name-defined]
        mock_app = MagicMock()
        captured: list[t.Any] = []

        def decorator() -> t.Any:  # type: ignore[name-defined]
            def wrap(func: t.Any) -> t.Any:  # type: ignore[name-defined]
                captured.append(func)
                return func
            return wrap

        mock_app.tool = decorator  # type: ignore[method-assign]
        register_semantic_tools(mock_app)
        for fn in captured:
            if fn.__name__ == "search_semantic":
                return fn
        raise AssertionError("search_semantic not registered")

    def test_invalid_query(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv:
            mock_giv.return_value.validate_command_args = MagicMock(
                return_value=_validate_result(valid=False, error="bad"),
            )
            out = json.loads(asyncio_run(tool("rm -rf", 5, 0.5, "", "")))
        assert out["success"] is False
        assert "query_validation" in out.get("validation_type", "")

    def test_invalid_max_results(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv:
            mock_giv.return_value.validate_command_args = MagicMock(
                return_value=_validate_result(valid=True, sanitized="q"),
            )
            out = json.loads(asyncio_run(tool("q", 0, 0.5, "", "")))
        assert out["success"] is False
        assert "max_results" in out["error"]

    def test_invalid_min_similarity(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv:
            mock_giv.return_value.validate_command_args = MagicMock(
                return_value=_validate_result(valid=True, sanitized="q"),
            )
            out = json.loads(asyncio_run(tool("q", 5, 1.5, "", "")))
        assert out["success"] is False
        assert "min_similarity" in out["error"]

    def test_success(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv, patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_giv.return_value.validate_command_args = MagicMock(
                return_value=_validate_result(valid=True, sanitized="q"),
            )
            mock_vs.return_value.search.return_value = [_result()]
            out = json.loads(
                asyncio_run(tool("q", 5, 0.5, "python", "")),
            )
        assert out["success"] is True
        assert out["query"] == "q"
        assert out["max_results"] == 5
        assert out["min_similarity"] == 0.5
        assert out["results_count"] == 1
        assert out["results"][0]["file_type"] == "python"

    def test_exception_returns_error(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv, patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_giv.return_value.validate_command_args = MagicMock(
                return_value=_validate_result(valid=True, sanitized="q"),
            )
            mock_vs.return_value.search.side_effect = RuntimeError("boom")
            out = json.loads(asyncio_run(tool("q", 5, 0.5, "", "")))
        assert out["success"] is False
        assert "boom" in out["error"]


# ─── tool: get_semantic_stats ──────────────────────────────────────────────


@pytest.mark.unit
class TestGetSemanticStats:
    def _tool(self) -> t.Any:  # type: ignore[name-defined]
        mock_app = MagicMock()
        captured: list[t.Any] = []

        def decorator() -> t.Any:  # type: ignore[name-defined]
            def wrap(func: t.Any) -> t.Any:  # type: ignore[name-defined]
                captured.append(func)
                return func
            return wrap

        mock_app.tool = decorator  # type: ignore[method-assign]
        register_semantic_tools(mock_app)
        for fn in captured:
            if fn.__name__ == "get_semantic_stats":
                return fn
        raise AssertionError("get_semantic_stats not registered")

    def test_success(self) -> None:
        tool = self._tool()
        last = datetime(2026, 1, 1, 12, 0, 0)
        with patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_vs.return_value.get_stats.return_value = _stats(
                total_files=4,
                total_chunks=20,
                size_mb=2.5,
                last=last,
            )
            out = json.loads(asyncio_run(tool("")))
        assert out["success"] is True
        assert out["total_files"] == 4
        assert out["total_chunks"] == 20
        assert out["index_size_mb"] == 2.5
        # 20 / 4 = 5.0
        assert out["average_chunks_per_file"] == 5.0
        assert out["last_updated"] == "2026-01-01T12:00:00"

    def test_zero_files_average_is_zero(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_vs.return_value.get_stats.return_value = _stats(
                total_files=0, total_chunks=0,
            )
            out = json.loads(asyncio_run(tool("")))
        assert out["success"] is True
        assert out["average_chunks_per_file"] == 0.0

    def test_no_last_updated(self) -> None:
        tool = self._tool()
        stats = _stats()
        stats.last_updated = None
        with patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_vs.return_value.get_stats.return_value = stats
            out = json.loads(asyncio_run(tool("")))
        assert out["last_updated"] is None

    def test_exception(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_vs.return_value.get_stats.side_effect = RuntimeError("x")
            out = json.loads(asyncio_run(tool("")))
        assert out["success"] is False
        assert "x" in out["error"]


# ─── tool: remove_file_from_semantic_index ─────────────────────────────────


@pytest.mark.unit
class TestRemoveFileFromIndex:
    def _tool(self) -> t.Any:  # type: ignore[name-defined]
        mock_app = MagicMock()
        captured: list[t.Any] = []

        def decorator() -> t.Any:  # type: ignore[name-defined]
            def wrap(func: t.Any) -> t.Any:  # type: ignore[name-defined]
                captured.append(func)
                return func
            return wrap

        mock_app.tool = decorator  # type: ignore[method-assign]
        register_semantic_tools(mock_app)
        for fn in captured:
            if fn.__name__ == "remove_file_from_semantic_index":
                return fn
        raise AssertionError("remove_file_from_semantic_index not registered")

    def test_invalid_path(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv:
            mock_giv.return_value.validate_file_path = MagicMock(
                return_value=_validate_result(
                    valid=False, error="bad", vtype="path",
                ),
            )
            out = json.loads(asyncio_run(tool("bad", "")))
        assert out["success"] is False
        assert out["validation_type"] == "path"

    def test_success(self, tmp_path: Path) -> None:
        tool = self._tool()
        target = tmp_path / "x.py"
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv, patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_giv.return_value.validate_file_path = MagicMock(
                return_value=_validate_result(
                    valid=True, sanitized=str(target),
                ),
            )
            mock_vs.return_value.remove_file.return_value = True
            out = json.loads(asyncio_run(tool(str(target), "")))
        assert out["success"] is True
        assert "Successfully removed" in out["message"]

    def test_remove_returns_false(self, tmp_path: Path) -> None:
        tool = self._tool()
        target = tmp_path / "x.py"
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv, patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_giv.return_value.validate_file_path = MagicMock(
                return_value=_validate_result(
                    valid=True, sanitized=str(target),
                ),
            )
            mock_vs.return_value.remove_file.return_value = False
            out = json.loads(asyncio_run(tool(str(target), "")))
        assert out["success"] is False
        assert "Failed to remove" in out["message"]

    def test_exception(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.get_input_validator",
        ) as mock_giv, patch(
            "crackerjack.mcp.tools.semantic_tools.VectorStore",
        ) as mock_vs:
            mock_giv.return_value.validate_file_path = MagicMock(
                return_value=_validate_result(valid=True, sanitized="/p"),
            )
            mock_vs.return_value.remove_file.side_effect = RuntimeError("x")
            out = json.loads(asyncio_run(tool("/p", "")))
        assert out["success"] is False
        assert "x" in out["error"]


# ─── tool: get_embeddings ──────────────────────────────────────────────────


@pytest.mark.unit
class TestGetEmbeddings:
    def _tool(self) -> t.Any:  # type: ignore[name-defined]
        mock_app = MagicMock()
        captured: list[t.Any] = []

        def decorator() -> t.Any:  # type: ignore[name-defined]
            def wrap(func: t.Any) -> t.Any:  # type: ignore[name-defined]
                captured.append(func)
                return func
            return wrap

        mock_app.tool = decorator  # type: ignore[method-assign]
        register_semantic_tools(mock_app)
        for fn in captured:
            if fn.__name__ == "get_embeddings":
                return fn
        raise AssertionError("get_embeddings not registered")

    def test_invalid_texts_json(self) -> None:
        tool = self._tool()
        out = json.loads(asyncio_run(tool("[bad", "")))
        assert out["success"] is False
        assert "Invalid JSON" in out["error"]

    def test_non_list_texts(self) -> None:
        tool = self._tool()
        out = json.loads(asyncio_run(tool(json.dumps({"a": 1}), "")))
        assert out["success"] is False
        assert "texts must be a JSON array" in out["error"]

    def test_success_single(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.EmbeddingService",
        ) as mock_cls:
            mock_svc = MagicMock()
            mock_svc.generate_embedding.return_value = [0.1, 0.2]
            mock_cls.return_value = mock_svc
            out = json.loads(asyncio_run(tool(json.dumps(["hi"]), "")))
        assert out["success"] is True
        assert out["texts_count"] == 1
        assert out["embeddings"] == [[0.1, 0.2]]

    def test_success_batch(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.EmbeddingService",
        ) as mock_cls:
            mock_svc = MagicMock()
            mock_svc.generate_embeddings_batch.return_value = [
                [0.1], [0.2],
            ]
            mock_cls.return_value = mock_svc
            out = json.loads(
                asyncio_run(tool(json.dumps(["a", "b"]), "")),
            )
        assert out["success"] is True
        assert out["texts_count"] == 2

    def test_exception(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.EmbeddingService",
        ) as mock_cls:
            mock_cls.side_effect = RuntimeError("x")
            out = json.loads(asyncio_run(tool(json.dumps(["a"]), "")))
        assert out["success"] is False
        assert "x" in out["error"]


# ─── tool: calculate_similarity_semantic ───────────────────────────────────


@pytest.mark.unit
class TestCalculateSimilarity:
    def _tool(self) -> t.Any:  # type: ignore[name-defined]
        mock_app = MagicMock()
        captured: list[t.Any] = []

        def decorator() -> t.Any:  # type: ignore[name-defined]
            def wrap(func: t.Any) -> t.Any:  # type: ignore[name-defined]
                captured.append(func)
                return func
            return wrap

        mock_app.tool = decorator  # type: ignore[method-assign]
        register_semantic_tools(mock_app)
        for fn in captured:
            if fn.__name__ == "calculate_similarity_semantic":
                return fn
        raise AssertionError("calculate_similarity_semantic not registered")

    def test_invalid_json(self) -> None:
        tool = self._tool()
        out = json.loads(
            asyncio_run(tool("not json", json.dumps([1, 2]), "")),
        )
        assert out["success"] is False
        assert "Invalid JSON" in out["error"]

    def test_not_arrays(self) -> None:
        tool = self._tool()
        out = json.loads(
            asyncio_run(
                tool(json.dumps({"a": 1}), json.dumps([1, 2]), ""),
            ),
        )
        assert out["success"] is False
        assert "must be JSON arrays" in out["error"]

    def test_success(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.EmbeddingService",
        ) as mock_cls:
            mock_svc = MagicMock()
            mock_svc.calculate_similarity.return_value = 0.876543210
            mock_cls.return_value = mock_svc
            out = json.loads(
                asyncio_run(
                    tool(
                        json.dumps([0.1, 0.2, 0.3]),
                        json.dumps([0.4, 0.5, 0.6]),
                        "",
                    ),
                ),
            )
        assert out["success"] is True
        assert out["similarity_score"] == 0.876543
        assert out["embedding1_dimension"] == 3
        assert out["embedding2_dimension"] == 3

    def test_exception(self) -> None:
        tool = self._tool()
        with patch(
            "crackerjack.mcp.tools.semantic_tools.EmbeddingService",
        ) as mock_cls:
            mock_cls.side_effect = RuntimeError("x")
            out = json.loads(
                asyncio_run(
                    tool(json.dumps([1, 2]), json.dumps([3, 4]), ""),
                ),
            )
        assert out["success"] is False
        assert "x" in out["error"]


# ─── async helper ──────────────────────────────────────────────────────────


def asyncio_run(coro: t.Any) -> t.Any:  # type: ignore[name-defined]
    import asyncio

    return asyncio.get_event_loop().run_until_complete(coro)
