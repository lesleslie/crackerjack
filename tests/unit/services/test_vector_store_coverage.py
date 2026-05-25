"""Focused coverage tests for VectorStore branch handling."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import crackerjack.services.vector_store as vector_store_module
from crackerjack.models.semantic_models import (
    EmbeddingVector,
    SearchQuery,
    SemanticConfig,
)
from crackerjack.services.vector_store import VectorStore


class DummyEmbeddingService:
    def __init__(
        self,
        *,
        file_hash: str = "hash123",
        chunks: list[str] | None = None,
        embeddings: list[list[float] | list[float] | list[None]] | None = None,
        query_embedding: list[float] | None = None,
        similarities: list[float] | None = None,
    ) -> None:
        self.file_hash = file_hash
        self.chunks = chunks if chunks is not None else ["alpha\nbeta", "gamma"]
        self.embeddings = embeddings if embeddings is not None else [[0.1, 0.2], [0.3, 0.4]]
        self.query_embedding = query_embedding if query_embedding is not None else [0.5, 0.6]
        self.similarities = similarities if similarities is not None else [0.95, 0.2]

    def get_file_hash(self, _file_path: Path) -> str:
        return self.file_hash

    def chunk_text(self, _content: str) -> list[str]:
        return list(self.chunks)

    def generate_embeddings_batch(self, chunk_texts: list[str]) -> list[list[float] | list[None]]:
        return list(self.embeddings)[: len(chunk_texts)]

    def generate_embedding(self, _query: str) -> list[float]:
        return list(self.query_embedding)

    def calculate_similarities_batch(
        self,
        _query_embedding: list[float],
        embeddings: list[list[float]],
    ) -> list[float]:
        return list(self.similarities)[: len(embeddings)]


@pytest.fixture
def temp_db_path() -> Path:
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as handle:
        db_path = Path(handle.name)
    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.fixture
def mock_config() -> SemanticConfig:
    return SemanticConfig(
        embedding_model="text-embedding-3-small",
        chunk_size=100,
        chunk_overlap=20,
        max_file_size_mb=1,
        included_extensions=[".py"],
        excluded_patterns=["*.tmp"],
    )


def make_store(
    monkeypatch: pytest.MonkeyPatch,
    config: SemanticConfig,
    db_path: Path,
    service: DummyEmbeddingService | None = None,
) -> tuple[VectorStore, DummyEmbeddingService]:
    embedding_service = service or DummyEmbeddingService()
    monkeypatch.setattr(
        vector_store_module,
        "EmbeddingService",
        lambda _config: embedding_service,
    )
    store = VectorStore(config, db_path=db_path)
    store.embedding_service = embedding_service
    return store, embedding_service


def insert_embedding_row(
    db_path: Path,
    *,
    file_path: str,
    chunk_id: str = "chunk-1",
    content: str = "content",
    embedding: list[float] | None = None,
    created_at: str | None = None,
    file_hash: str = "hash123",
    start_line: int = 1,
    end_line: int = 2,
    file_type: str = ".py",
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO embeddings
            (chunk_id, file_path, content, embedding, created_at, file_hash, start_line, end_line, file_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                file_path,
                content,
                json.dumps(embedding or [0.1, 0.2]),
                created_at or datetime.now().isoformat(),
                file_hash,
                start_line,
                end_line,
                file_type,
            ),
        )
        conn.commit()


def insert_tracking_row(
    db_path: Path,
    *,
    file_path: str,
    file_hash: str,
    chunk_count: int = 1,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO file_tracking (file_path, file_hash, last_indexed, chunk_count)
            VALUES (?, ?, datetime('now'), ?)
            """,
            (file_path, file_hash, chunk_count),
        )
        conn.commit()


def test_get_connection_rolls_back_on_error(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)

    with pytest.raises(RuntimeError, match="boom"):
        with store._get_connection() as conn:
            assert conn is not None
            raise RuntimeError("boom")

    store.close()


def test_prepare_file_for_indexing_returns_none_when_up_to_date(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, service = make_store(monkeypatch, mock_config, temp_db_path)
    file_path = temp_db_path.with_suffix(".py")
    file_path.write_text("print('hello')", encoding="utf-8")

    service.file_hash = "abc123"
    monkeypatch.setattr(store, "_needs_reindexing", lambda _path, _hash: False)

    assert store._prepare_file_for_indexing(file_path) is None

    store.close()


def test_index_file_returns_existing_embeddings_when_already_indexed(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    sentinel = [Mock()]
    file_path = temp_db_path.with_suffix(".py")

    monkeypatch.setattr(store, "_prepare_file_for_indexing", lambda _path: None)
    monkeypatch.setattr(store, "_get_existing_embeddings", lambda _path: sentinel)

    assert store.index_file(file_path) is sentinel

    store.close()


def test_index_file_returns_empty_list_when_no_chunks(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    file_path = temp_db_path.with_suffix(".py")
    file_path.write_text("print('hello')", encoding="utf-8")

    monkeypatch.setattr(store, "_prepare_file_for_indexing", lambda _path: "hash123")
    monkeypatch.setattr(
        store,
        "_process_file_content",
        lambda _path, _hash: {"chunks": [], "chunk_texts": [], "chunk_metadata": []},
    )

    assert store.index_file(file_path) == []

    store.close()


def test_index_file_propagates_processing_error(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    file_path = temp_db_path.with_suffix(".py")
    file_path.write_text("print('hello')", encoding="utf-8")

    monkeypatch.setattr(store, "_prepare_file_for_indexing", lambda _path: "hash123")
    monkeypatch.setattr(store, "_process_file_content", lambda *_args: (_ for _ in ()).throw(RuntimeError("broken")))

    with pytest.raises(RuntimeError, match="broken"):
        store.index_file(file_path)

    store.close()


def test_create_embedding_vectors_skips_empty_entries_and_calls_progress(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, service = make_store(
        monkeypatch,
        mock_config,
        temp_db_path,
        DummyEmbeddingService(embeddings=[[], [0.9, 0.8]]),
    )
    progress = Mock()
    file_path = temp_db_path.with_suffix(".py")
    chunk_data = {
        "chunk_texts": ["first chunk", "second chunk"],
        "chunk_metadata": [
            {"chunk_id": "chunk-1", "start_line": 1, "end_line": 2},
            {"chunk_id": "chunk-2", "start_line": 3, "end_line": 4},
        ],
    }

    embeddings = store._create_embedding_vectors(file_path, "hash123", chunk_data, progress)

    assert len(embeddings) == 1
    assert embeddings[0].chunk_id == "chunk-2"
    assert progress.call_count == 1

    store.close()


def test_create_embedding_vectors_without_progress_callback(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(
        monkeypatch,
        mock_config,
        temp_db_path,
        DummyEmbeddingService(embeddings=[[0.1, 0.2]]),
    )
    file_path = temp_db_path.with_suffix(".py")
    chunk_data = {
        "chunk_texts": ["only chunk"],
        "chunk_metadata": [
            {"chunk_id": "chunk-1", "start_line": 1, "end_line": 1},
        ],
    }

    embeddings = store._create_embedding_vectors(file_path, "hash123", chunk_data)

    assert len(embeddings) == 1
    assert embeddings[0].chunk_id == "chunk-1"

    store.close()


def test_validate_file_for_indexing_rejects_missing_file(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)

    with pytest.raises(OSError, match="File does not exist"):
        store._validate_file_for_indexing(Path("/tmp/missing.py"))

    store.close()


def test_validate_file_for_indexing_rejects_non_file(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    directory = temp_db_path.parent

    with pytest.raises(ValueError, match="Path is not a file"):
        store._validate_file_for_indexing(directory)

    store.close()


def test_validate_file_for_indexing_rejects_large_file(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    file_path = temp_db_path.with_suffix(".py")
    file_path.write_bytes(b"x" * (2 * 1024 * 1024))

    with pytest.raises(ValueError, match="File too large"):
        store._validate_file_for_indexing(file_path)

    store.close()


def test_validate_file_for_indexing_rejects_extension_and_pattern(
    monkeypatch: pytest.MonkeyPatch,
    temp_db_path: Path,
) -> None:
    config = SemanticConfig(
        embedding_model="text-embedding-3-small",
        chunk_size=100,
        chunk_overlap=20,
        max_file_size_mb=1,
        included_extensions=[".py"],
        excluded_patterns=["*.tmp"],
    )
    store, _service = make_store(monkeypatch, config, temp_db_path)
    txt_file = temp_db_path.with_suffix(".txt")
    txt_file.write_text("print('hello')", encoding="utf-8")
    tmp_file = temp_db_path.with_suffix(".tmp")
    tmp_file.write_text("print('hello')", encoding="utf-8")

    with pytest.raises(ValueError, match="File extension not included"):
        store._validate_file_for_indexing(txt_file)

    pattern_config = SemanticConfig(
        embedding_model="text-embedding-3-small",
        chunk_size=100,
        chunk_overlap=20,
        max_file_size_mb=1,
        included_extensions=[".tmp"],
        excluded_patterns=["*.tmp"],
    )
    pattern_store, _service = make_store(monkeypatch, pattern_config, temp_db_path.with_suffix(".pattern.db"))

    with pytest.raises(ValueError, match="File matches exclusion pattern"):
        pattern_store._validate_file_for_indexing(tmp_file)

    store.close()
    pattern_store.close()


def test_get_existing_embeddings_round_trips_rows(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    file_path = temp_db_path.with_suffix(".py")
    insert_embedding_row(
        temp_db_path,
        file_path=str(file_path),
        chunk_id="chunk-1",
        content="hello",
        embedding=[0.4, 0.5],
        created_at=datetime.now().isoformat(),
        file_hash="hash123",
        start_line=2,
        end_line=3,
        file_type=".py",
    )

    embeddings = store._get_existing_embeddings(file_path)

    assert len(embeddings) == 1
    assert embeddings[0].chunk_id == "chunk-1"
    assert embeddings[0].embedding == [0.4, 0.5]

    store.close()


def test_store_embeddings_handles_empty_and_persists_rows(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    file_path = temp_db_path.with_suffix(".py")
    embedding = EmbeddingVector(
        file_path=file_path,
        chunk_id="chunk-1",
        content="hello",
        embedding=[0.4, 0.5],
        created_at=datetime.now(),
        file_hash="hash123",
        start_line=1,
        end_line=2,
        file_type=".py",
    )

    store._store_embeddings([])
    store._store_embeddings([embedding])

    with sqlite3.connect(temp_db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]

    assert count == 1

    store.close()


def test_index_file_stores_embeddings_and_tracking(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, service = make_store(
        monkeypatch,
        mock_config,
        temp_db_path,
        DummyEmbeddingService(
            file_hash="hash-abc",
            chunks=["alpha\nbeta", "gamma"],
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
        ),
    )
    file_path = temp_db_path.with_suffix(".py")
    file_path.write_text("alpha\nbeta\ngamma", encoding="utf-8")
    progress = Mock()

    embeddings = store.index_file(file_path, progress_callback=progress)

    with sqlite3.connect(temp_db_path) as conn:
        embedding_count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        tracking_row = conn.execute(
            "SELECT file_hash, chunk_count FROM file_tracking WHERE file_path = ?",
            (str(file_path),),
        ).fetchone()

    assert len(embeddings) == 2
    assert embedding_count == 2
    assert tracking_row[0] == "hash-abc"
    assert tracking_row[1] == 2
    assert progress.call_count == 2

    store.close()


def test_search_returns_empty_without_embeddings(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, service = make_store(monkeypatch, mock_config, temp_db_path)
    service.similarities = []
    query = SearchQuery(query="needle", max_results=5, min_similarity=0.2)

    assert store.search(query) == []

    store.close()


def test_search_filters_results_and_includes_context(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, service = make_store(monkeypatch, mock_config, temp_db_path)
    file_path = temp_db_path.with_suffix(".py")
    rows = [
        {
            "chunk_id": "chunk-1",
            "file_path": str(file_path),
            "content": "hello",
            "embedding": [0.1, 0.2],
            "start_line": 1,
            "end_line": 2,
            "file_type": ".py",
        },
        {
            "chunk_id": "chunk-2",
            "file_path": str(file_path),
            "content": "world",
            "embedding": [0.2, 0.3],
            "start_line": 3,
            "end_line": 4,
            "file_type": ".py",
        },
    ]

    monkeypatch.setattr(store, "_get_all_embeddings", lambda _types=None: rows)
    monkeypatch.setattr(store, "_get_context_lines", lambda *_args, **_kwargs: ["ctx-1", "ctx-2"])
    service.similarities = [0.1, 0.9]

    query = SearchQuery(
        query="needle",
        max_results=1,
        min_similarity=0.2,
        include_context=True,
        context_lines=2,
    )

    results = store.search(query)

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-2"
    assert results[0].context_lines == ["ctx-1", "ctx-2"]

    store.close()


def test_search_skips_context_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, service = make_store(monkeypatch, mock_config, temp_db_path)
    file_path = temp_db_path.with_suffix(".py")
    rows = [
        {
            "chunk_id": "chunk-1",
            "file_path": str(file_path),
            "content": "hello",
            "embedding": [0.1, 0.2],
            "start_line": 1,
            "end_line": 2,
            "file_type": ".py",
        }
    ]

    monkeypatch.setattr(store, "_get_all_embeddings", lambda _types=None: rows)
    monkeypatch.setattr(store, "_get_context_lines", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("context should not be requested")))
    service.similarities = [0.9]

    query = SearchQuery(
        query="needle",
        max_results=1,
        min_similarity=0.2,
        include_context=False,
        context_lines=2,
    )

    results = store.search(query)

    assert len(results) == 1
    assert results[0].context_lines == []

    store.close()


def test_get_all_embeddings_filters_file_types(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    insert_embedding_row(temp_db_path, file_path="/tmp/a.py", file_type=".py")
    insert_embedding_row(temp_db_path, file_path="/tmp/b.md", file_type=".md", chunk_id="chunk-2")

    embeddings = store._get_all_embeddings([".py"])

    assert len(embeddings) == 1
    assert embeddings[0]["file_type"] == ".py"

    store.close()


def test_get_all_embeddings_without_file_type_filter(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    insert_embedding_row(temp_db_path, file_path="/tmp/a.py", file_type=".py")
    insert_embedding_row(temp_db_path, file_path="/tmp/b.md", file_type=".md", chunk_id="chunk-2")

    embeddings = store._get_all_embeddings()

    assert len(embeddings) == 2

    store.close()


def test_get_context_lines_handles_missing_and_read_errors(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    missing = temp_db_path.with_suffix(".missing")
    assert store._get_context_lines(missing, 1, 2, 2) == []

    existing = temp_db_path.with_suffix(".py")
    existing.write_text("one\ntwo\nthree", encoding="utf-8")

    monkeypatch.setattr(Path, "read_text", lambda _self, encoding="utf-8": (_ for _ in ()).throw(RuntimeError("read failed")))
    assert store._get_context_lines(existing, 1, 2, 1) == []

    store.close()


def test_get_context_lines_returns_context(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    file_path = temp_db_path.with_suffix(".py")
    file_path.write_text("one\ntwo\nthree\nfour\nfive", encoding="utf-8")

    assert store._get_context_lines(file_path, 2, 3, 1) == ["one", "two", "three", "four"]

    store.close()


def test_get_stats_and_remove_file(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
    temp_db_path: Path,
) -> None:
    store, _service = make_store(monkeypatch, mock_config, temp_db_path)
    file_path = temp_db_path.with_suffix(".py")
    insert_embedding_row(
        temp_db_path,
        file_path=str(file_path),
        chunk_id="chunk-1",
        content="hello",
        embedding=[0.4, 0.5],
        file_hash="hash123",
        start_line=1,
        end_line=2,
        file_type=".py",
    )
    insert_tracking_row(temp_db_path, file_path=str(file_path), file_hash="hash123", chunk_count=1)

    stats = store.get_stats()
    removed = store.remove_file(file_path)

    assert stats.total_files == 1
    assert stats.total_chunks == 1
    assert stats.file_types == {".py": 1}
    assert removed is True

    store.close()


def test_close_cleans_up_temp_database(monkeypatch: pytest.MonkeyPatch, mock_config: SemanticConfig) -> None:
    with patch.object(VectorStore, "_initialize_database"):
        store = VectorStore(mock_config)
        temp_db = store.db_path
        temp_db.write_text("placeholder", encoding="utf-8")
        store.close()

    assert not temp_db.exists()


def test_close_skips_unlink_when_database_missing(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: SemanticConfig,
) -> None:
    with patch.object(VectorStore, "_initialize_database"):
        store = VectorStore(mock_config)
        temp_db = store.db_path
        temp_db.write_text("placeholder", encoding="utf-8")
        temp_db.unlink()
        store.close()

    assert not temp_db.exists()
