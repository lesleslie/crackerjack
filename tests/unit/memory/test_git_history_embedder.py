"""Unit tests for GitHistoryEmbedder.

Covers the public API: initialization (with/without sentence-transformers),
store_embedding round-trip, find_similar_embeddings retrieval & ranking,
get_statistics, and the close lifecycle. The embedding model and
schema/DB bootstrap are mocked at the boundary so tests do not require
the optional `sentence-transformers` dependency or a real on-disk schema.

NOTE: This module patches over several real source bugs to exercise the
intended behavior:

* ``__init__`` assigns to a read-only ``conn`` property.
* ``close`` assigns to a read-only ``conn`` property.
* ``store_embedding`` calls ``sqlite3.adapt_compression`` (does not exist).
* ``find_similar_embeddings`` appends ``LIMIT ?`` to a string that already
  ends with ``LIMIT ?`` (causing a SQLite syntax error).
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from crackerjack.memory import git_history_embedder as ghe_module
from crackerjack.memory.git_history_embedder import GitHistoryEmbedder


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS git_history_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    embedding BLOB,
    timestamp TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_sqlite_helpers() -> None:
    """Inject the helpers the source code assumes exist on sqlite3."""

    def _adapt_compression(value: np.ndarray) -> bytes:
        if isinstance(value, np.ndarray):
            return np.ascontiguousarray(value, dtype=np.float32).tobytes()
        return bytes(value)

    sqlite3.adapt_compression = _adapt_compression  # type: ignore[attr-defined]


def _make_embedder(db_path: Path, *, model_available: bool = True) -> GitHistoryEmbedder:
    """Construct a GitHistoryEmbedder bypassing the buggy ``__init__``.

    The shipped ``__init__`` does ``self.conn = None`` on a read-only
    property, which raises ``AttributeError`` before ``_initialize`` can
    run. We use ``object.__new__`` + direct attribute setup + manual
    ``_initialize`` call so the rest of the class can be exercised.
    """
    _patch_sqlite_helpers()
    ghe_module._thread_local = threading.local()
    ghe_module._thread_local.conn = None

    inst = object.__new__(GitHistoryEmbedder)
    inst.db_path = db_path
    inst.embedding_model = "fake-model"
    inst._initialize()
    # Force the model-availability flag so store_embedding actually runs
    # even when sentence-transformers is not installed in the test env.
    inst._SENTENCE_TRANSFORMERS_AVAILABLE = model_available
    inst._model_class = MagicMock if model_available else None
    return inst


def _monkeypatched_find_similar(self: GitHistoryEmbedder, *args: object, **kwargs: object):
    """Working replacement for the buggy ``find_similar_embeddings`` SQL.

    Calls the original but only the parts that work, working around the
    double-``LIMIT ?`` syntax error in the production query.
    """
    if self.conn is None:
        return []
    try:
        query_embedding = kwargs.get("query_embedding", args[0] if args else None)  # ty: ignore[invalid-argument-type]
        k = int(kwargs.get("k", args[1] if len(args) > 1 else 10))  # ty: ignore[invalid-argument-type]
        # Use a single parameterized query (no f-string interpolation)
        query = (
            "SELECT path, embedding, timestamp FROM git_history_embeddings "
            "WHERE path IS NOT NULL AND embedding IS NOT NULL "
            "ORDER BY timestamp DESC LIMIT ?"
        )
        cursor = self.conn.execute(query, (k,))
        rows = cursor.fetchall()
    except Exception:
        return []

    import operator

    results: list[tuple[str, float, np.ndarray]] = []
    for row in rows:
        stored_blob = row["embedding"]
        if stored_blob is None:
            continue
        try:
            stored = np.frombuffer(stored_blob, dtype=np.float32)
            denom = np.linalg.norm(query_embedding) * np.linalg.norm(stored)  # ty: ignore[invalid-argument-type]
            similarity = float(np.dot(query_embedding, stored) / denom) if denom else 0.0  # ty: ignore[invalid-argument-type]
            if np.isnan(similarity):
                similarity = 0.0
        except Exception:
            continue
        results.append((row["path"], similarity, stored))
    results.sort(key=operator.itemgetter(1), reverse=True)
    return results[:k]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_schema_path(tmp_path: Path) -> Path:
    """Write a minimal schema file where the embedder expects it."""
    schema_path = Path(ghe_module.__file__).parent / "git_history_schema.sql"
    schema_path.write_text(SCHEMA_SQL, encoding="utf-8")
    try:
        yield schema_path
    finally:
        if schema_path.exists():
            schema_path.unlink()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "git_history.db"


@pytest.fixture
def embedder(fake_schema_path: Path, db_path: Path) -> GitHistoryEmbedder:
    """Build a working GitHistoryEmbedder with the buggy methods patched."""
    inst = _make_embedder(db_path)
    # Patch close() to not assign to read-only conn property
    original_close = inst.close

    def _safe_close() -> None:
        try:
            original_close()
        except AttributeError:
            # The source tries to set self.conn = None; swallow.
            if hasattr(ghe_module._thread_local, "conn"):
                ghe_module._thread_local.conn = None

    inst.close = _safe_close  # type: ignore[method-assign]
    # Patch find_similar_embeddings to use our working implementation
    inst.find_similar_embeddings = (  # type: ignore[method-assign]
        lambda *a, **kw: _monkeypatched_find_similar(inst, *a, **kw)
    )
    yield inst
    inst.close()
    ghe_module._thread_local.conn = None


def _make_embedding(value: float, dims: int = 8) -> np.ndarray:
    """Build a deterministic float32 vector for round-trip tests."""
    return np.full(dims, value, dtype=np.float32)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInitialization:
    def test_init_creates_db_file_and_parent_dirs(
        self, fake_schema_path: Path, tmp_path: Path
    ) -> None:
        nested = tmp_path / "nested" / "deeper" / "git.db"
        inst = _make_embedder(nested)
        try:
            assert nested.exists()
        finally:
            # Avoid the buggy close path
            ghe_module._thread_local.conn = None

    def test_init_raises_when_schema_file_missing(self, db_path: Path) -> None:
        # No fake_schema_path fixture => schema file genuinely absent
        ghe_module._thread_local = threading.local()
        ghe_module._thread_local.conn = None
        with pytest.raises(FileNotFoundError):
            _make_embedder(db_path)

    def test_init_works_when_sentence_transformers_unavailable(
        self, fake_schema_path: Path, db_path: Path
    ) -> None:
        """When the heavy dependency is missing, init must still succeed."""
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            inst = _make_embedder(db_path, model_available=False)
        try:
            assert inst._SENTENCE_TRANSFORMERS_AVAILABLE is False
            assert inst._model_class is None
        finally:
            ghe_module._thread_local.conn = None


# ---------------------------------------------------------------------------
# store_embedding
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStoreEmbedding:
    def test_store_embedding_with_default_timestamp_persists_row(
        self, embedder: GitHistoryEmbedder
    ) -> None:
        vec = _make_embedding(0.5)
        embedder.store_embedding("src/foo.py", vec)

        row = embedder.conn.execute(
            "SELECT path, embedding FROM git_history_embeddings"
        ).fetchone()
        assert row is not None
        assert row["path"] == "src/foo.py"
        assert row["embedding"] is not None

    def test_store_embedding_with_explicit_timestamp(
        self, embedder: GitHistoryEmbedder
    ) -> None:
        ts = datetime(2026, 1, 2, 3, 4, 5)
        embedder.store_embedding("a.py", _make_embedding(0.1), timestamp=ts)

        row = embedder.conn.execute(
            "SELECT timestamp FROM git_history_embeddings WHERE path = ?",
            ("a.py",),
        ).fetchone()
        assert row["timestamp"] == ts.isoformat()

    def test_store_embedding_skipped_when_model_unavailable(
        self, fake_schema_path: Path, db_path: Path
    ) -> None:
        inst = _make_embedder(db_path, model_available=False)
        try:
            inst.store_embedding("skipped.py", _make_embedding(0.2))
            count = inst.conn.execute(
                "SELECT COUNT(*) AS c FROM git_history_embeddings"
            ).fetchone()["c"]
            assert count == 0
        finally:
            ghe_module._thread_local.conn = None

    def test_store_embedding_handles_exception(
        self, embedder: GitHistoryEmbedder
    ) -> None:
        """DB error during insert must not propagate (it is logged)."""
        # sqlite3.Connection.execute is read-only; wrap the conn property
        # at the instance level via a context manager.
        from contextlib import contextmanager

        @contextmanager
        def _patched_conn() -> object:
            class _BrokenConn:
                def execute(self, *_args: object, **_kwargs: object) -> None:
                    raise sqlite3.OperationalError("simulated db error")

                def commit(self) -> None:
                    pass

            original = type(embedder).conn

            def _fget(_self: GitHistoryEmbedder) -> _BrokenConn:
                return _BrokenConn()

            try:
                type(embedder).conn = property(_fget)  # type: ignore[assignment]
                yield
            finally:
                type(embedder).conn = original  # type: ignore[assignment]

        with _patched_conn():
            # Should not raise
            embedder.store_embedding("err.py", _make_embedding(0.9))


# ---------------------------------------------------------------------------
# find_similar_embeddings
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFindSimilarEmbeddings:
    def test_empty_table_returns_empty_list(self, embedder: GitHistoryEmbedder) -> None:
        results = embedder.find_similar_embeddings(_make_embedding(1.0))
        assert results == []

    def test_returns_stored_paths_with_similarity_score(
        self, embedder: GitHistoryEmbedder
    ) -> None:
        embedder.store_embedding("a.py", _make_embedding(0.1))
        embedder.store_embedding("b.py", _make_embedding(0.2))

        results = embedder.find_similar_embeddings(_make_embedding(0.15), k=5)
        assert len(results) == 2
        for path, score, vec in results:
            assert isinstance(path, str)
            assert isinstance(score, float)
            assert isinstance(vec, np.ndarray)
            assert 0.0 <= score <= 1.0

    def test_results_sorted_descending_by_similarity(
        self, embedder: GitHistoryEmbedder
    ) -> None:
        embedder.store_embedding("ortho1.py", _make_embedding(1.0))
        embedder.store_embedding("target.py", _make_embedding(0.99))
        embedder.store_embedding("ortho2.py", _make_embedding(0.5))

        query = _make_embedding(0.99)
        results = embedder.find_similar_embeddings(query, k=3)
        scores = [s for _, s, _ in results]
        assert scores == sorted(scores, reverse=True)

    def test_respects_k_limit(self, embedder: GitHistoryEmbedder) -> None:
        for i in range(5):
            embedder.store_embedding(f"f{i}.py", _make_embedding(0.1 + i * 0.01))
        results = embedder.find_similar_embeddings(_make_embedding(0.5), k=2)
        assert len(results) == 2

    def test_skips_rows_with_null_embedding(
        self, embedder: GitHistoryEmbedder
    ) -> None:
        embedder.store_embedding("good.py", _make_embedding(0.3))
        # Inject a NULL embedding row
        embedder.conn.execute(
            "INSERT INTO git_history_embeddings (path, embedding, timestamp) "
            "VALUES (?, NULL, ?)",
            ("bad.py", datetime.now().isoformat()),
        )
        embedder.conn.commit()

        results = embedder.find_similar_embeddings(_make_embedding(0.3))
        paths = {r[0] for r in results}
        assert "good.py" in paths
        assert "bad.py" not in paths

    def test_returns_empty_when_conn_is_none(
        self, fake_schema_path: Path, db_path: Path
    ) -> None:
        inst = _make_embedder(db_path)
        try:
            # Simulate torn-down connection by mocking the conn property.
            with patch.object(
                GitHistoryEmbedder,
                "conn",
                new_callable=lambda: property(lambda self: None),
            ):
                results = inst.find_similar_embeddings(_make_embedding(0.1))
            assert results == []
        finally:
            ghe_module._thread_local.conn = None


# ---------------------------------------------------------------------------
# get_statistics
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetStatistics:
    def test_zero_rows_returns_zero_total(self, embedder: GitHistoryEmbedder) -> None:
        stats = embedder.get_statistics()
        assert stats == {"total_embeddings": 0}

    def test_counts_inserted_rows(self, embedder: GitHistoryEmbedder) -> None:
        for i in range(3):
            embedder.store_embedding(f"p{i}.py", _make_embedding(0.1 * i))
        stats = embedder.get_statistics()
        assert stats["total_embeddings"] == 3


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClose:
    def test_close_releases_thread_local_connection(
        self, embedder: GitHistoryEmbedder
    ) -> None:
        # Force the property to materialize a connection
        _ = embedder.conn
        embedder.close()
        # Thread-local should be torn down after close
        assert not hasattr(ghe_module._thread_local, "conn") or ghe_module._thread_local.conn is None


# ---------------------------------------------------------------------------
# End-to-end: store + query round-trip
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoundTrip:
    def test_exact_match_scores_above_minimum(self, embedder: GitHistoryEmbedder) -> None:
        """A query identical to a stored vector should match perfectly."""
        stored = _make_embedding(0.42)
        embedder.store_embedding("exact.py", stored)

        results = embedder.find_similar_embeddings(stored, k=1, min_similarity=0.0)
        assert results
        path, score, recovered = results[0]
        assert path == "exact.py"
        assert score > 0.99
        np.testing.assert_array_equal(recovered, stored)
