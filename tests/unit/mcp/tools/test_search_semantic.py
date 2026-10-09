"""Wire-envelope regression tests for ``mcp__crackerjack__search_semantic``.

Per REQ-004 + REQ-012 of
``mahavishnu/docs/plans/2026-10-09-bodai-search-infrastructure-fix.md``,
the tool must:

- Return ``status="ok"`` with ``results_count >= 1`` for a known-embedded
  phrase at ``min_similarity=0.3``.
- Return ``status="degraded"`` (never silent empty) when the index is
  empty — alongside a hint that points operators at the reindex
  procedure documented in ``crackerjack/docs/operations/reindex.md``.
- Always return a JSON envelope with ``status`` field — assertions parse
  ``result.content[0].text`` via ``_extract_payload``.

The tests index test fixtures into a temporary SQLite DB and assert the
envelope shape both before- and after-index population.
"""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path
from unittest.mock import patch

import pytest
from fastmcp import Client, FastMCP

from crackerjack.mcp.context import (
    MCPServerConfig,
    MCPServerContext,
    set_context,
)
from crackerjack.mcp.tools import semantic_tools
from crackerjack.models.semantic_models import SemanticConfig
from crackerjack.services.vector_store import VectorStore
from tests.unit.mcp.tools import _extract_payload  # noqa: TID


KNOWN_PHRASE_TEXT = (
    "The semantic reindex procedure walks the directory tree, "
    "computes embeddings for each chunk, and stores them in the "
    "SQLite vector table for fast similarity search."
)


def _make_app_with_empty_index(tmp_path: Path) -> FastMCP:
    """Build a FastMCP app where ``search_semantic`` reads from an empty
    SQLite DB at ``<tmp>/.crackerjack/semantic_index.db``.

    Mirrors ``crackerjack/mcp/server_core.py:_setup_server_context`` —
    ``set_context`` populates the singleton that ``semantic_tools``
    consumers may also read.
    """
    set_context(
        MCPServerContext(MCPServerConfig(project_path=tmp_path.resolve())),
    )
    app = FastMCP("crackerjack-search-semantic-test")
    semantic_tools.register_semantic_tools(app)
    return app


def _make_config() -> SemanticConfig:
    """Build the default config used by the search_semantic handler."""
    return SemanticConfig(
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        chunk_size=512,
        chunk_overlap=50,
        max_search_results=10,
        similarity_threshold=0.7,
        embedding_dimension=384,
    )


def _patch_persistent_db(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    """Force ``semantic_tools._get_persistent_db_path()`` to ``db_path``."""
    monkeypatch.setattr(
        "crackerjack.mcp.tools.semantic_tools._get_persistent_db_path",
        lambda: db_path,
    )


def _index_known_text(db_path: Path, text: str) -> int:
    """Write ``text`` to a temp file and index it. Returns chunk count."""
    config = _make_config()
    store = VectorStore(config, db_path=db_path)
    target = db_path.parent / "indexable_snippet.py"
    target.write_text(text, encoding="utf-8")
    chunks = store.index_file(target)
    store.close()
    return len(chunks)


class TestSearchSemanticWireEnvelope:
    """REQ-004 + REQ-012: wire-envelope assertions via FastMCP Client."""

    @pytest.mark.anyio
    async def test_search_semantic_empty_index_returns_degraded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty DB → ``status="degraded"`` with a hint pointing at the
        reindex procedure. This is the fix for the silent-zero bug."""
        db_path = tmp_path / ".crackerjack" / "semantic_index.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _patch_persistent_db(monkeypatch, db_path)

        app = _make_app_with_empty_index(tmp_path)
        async with Client(app) as client:
            result = await client.call_tool(
                "search_semantic",
                {"query": "python", "min_similarity": 0.3},
            )

        payload = _extract_payload(result)
        assert payload["success"] is True
        assert payload["status"] == "degraded"
        assert payload["results_count"] == 0
        assert "hint" in payload
        assert "reindex" in payload["hint"]

    @pytest.mark.anyio
    async def test_search_semantic_finds_indexed_phrase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After indexing a known snippet, ``search_semantic`` returns
        ``results_count >= 1`` for the phrase at ``min_similarity=0.3``
        and ``status="ok"``."""
        db_path = tmp_path / ".crackerjack" / "semantic_index.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _patch_persistent_db(monkeypatch, db_path)

        chunk_count = _index_known_text(db_path, KNOWN_PHRASE_TEXT)
        assert chunk_count >= 1, "the test fixture must produce ≥1 chunk"

        app = _make_app_with_empty_index(tmp_path)
        async with Client(app) as client:
            result = await client.call_tool(
                "search_semantic",
                {
                    "query": "embeddings chunk similarity search",
                    "min_similarity": 0.3,
                },
            )

        payload = _extract_payload(result)
        assert payload["success"] is True
        assert payload["status"] == "ok"
        assert payload["results_count"] >= 1, (
            f"expected ≥1 hit for the indexed phrase, got "
            f"results_count={payload['results_count']}"
        )

    @pytest.mark.anyio
    async def test_search_semantic_envelope_shape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Envelope always carries a ``status`` key (the new contract per
        the Phase-2 fix)."""
        db_path = tmp_path / ".crackerjack" / "semantic_index.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _patch_persistent_db(monkeypatch, db_path)

        app = _make_app_with_empty_index(tmp_path)
        async with Client(app) as client:
            result = await client.call_tool(
                "search_semantic",
                {"query": "python", "min_similarity": 0.3},
            )

        payload = _extract_payload(result)
        assert "status" in payload
        assert payload["status"] in {"ok", "degraded"}
