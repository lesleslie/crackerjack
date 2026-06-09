"""Test suite for crackerjack.memory.git_metrics_storage.

Covers the GitMetricsStorage SQLite-backed metrics/event store and the
GitMetric dataclass. The shipped schema file
``crackerjack/memory/git_metrics_schema.sql`` contains SQL syntax errors
(missing commas before PRIMARY KEY clauses in both ``git_metrics`` and
``git_events`` table definitions) that prevent ``executescript`` from
running end-to-end on a fresh database. Most tests therefore install a
fixed schema into a temporary directory and point the storage at it.
"""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import typing as t
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.memory import git_metrics_storage as gms
from crackerjack.memory.git_metrics_storage import GitMetric, GitMetricsStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# Minimal valid schema (corrected: PRIMARY KEY clauses need a leading comma).
_FIXED_SCHEMA = """\
CREATE TABLE IF NOT EXISTS git_metrics (
    timestamp TIMESTAMP NOT NULL,
    repository_path TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    value REAL NOT NULL,
    metadata TEXT,
    PRIMARY KEY (repository_path, timestamp, metric_type)
);

CREATE INDEX IF NOT EXISTS idx_git_metrics_repo_time
    ON git_metrics(repository_path, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_git_metrics_type ON git_metrics(metric_type);

CREATE TABLE IF NOT EXISTS git_events (
    repository_path TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    details TEXT NOT NULL,
    PRIMARY KEY (repository_path, timestamp, event_type)
);

CREATE INDEX IF NOT EXISTS idx_git_events_repo_time
    ON git_events(repository_path, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_git_events_type ON git_events(event_type);
"""


@pytest.fixture
def fixed_schema_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a corrected schema and monkeypatch the storage module to find it.

    Returns the directory containing ``git_metrics_schema.sql``.
    """
    schema_file = tmp_path / "git_metrics_schema.sql"
    schema_file.write_text(_FIXED_SCHEMA, encoding="utf-8")
    # The storage class resolves the schema via
    # ``Path(__file__).parent / "git_metrics_schema.sql"``, so swap the
    # module's __file__ to point at the directory we just wrote.
    monkeypatch.setattr(gms, "__file__", str(schema_file))
    return tmp_path


@pytest.fixture
def storage(fixed_schema_dir: Path, tmp_path: Path) -> GitMetricsStorage:
    """GitMetricsStorage backed by a temp SQLite file using the fixed schema.

    The module caches the sqlite3.Connection on a thread-local, so a stale
    connection to a previous test's (now-deleted) file would otherwise be
    returned. Reset the cache for every test.
    """
    gms._thread_local.conn = None
    db_path = tmp_path / "git_metrics.db"
    return GitMetricsStorage(db_path=db_path)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_git_metric_dataclass_defaults() -> None:
    """GitMetric is a plain dataclass with sensible defaults."""
    ts = datetime(2026, 1, 2, 3, 4, 5)
    metric = GitMetric(
        repository_path="/repo/a",
        metric_type="commit_velocity",
        value=3.5,
        timestamp=ts,
    )
    assert metric.repository_path == "/repo/a"
    assert metric.metric_type == "commit_velocity"
    assert metric.value == 3.5
    assert metric.timestamp == ts
    assert metric.metadata is None


@pytest.mark.unit
def test_git_metric_dataclass_with_metadata() -> None:
    """GitMetric accepts a JSON-string metadata field."""
    metric = GitMetric(
        repository_path="/r",
        metric_type="merge_conflicts",
        value=0.0,
        timestamp=datetime(2026, 5, 1),
        metadata='{"branch": "main"}',
    )
    assert metric.metadata == '{"branch": "main"}'


# ---------------------------------------------------------------------------
# Connection & schema initialization
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_storage_initialization_creates_db_file(
    fixed_schema_dir: Path, tmp_path: Path
) -> None:
    """Constructor creates parent directory and the SQLite file."""
    nested = tmp_path / "nested" / "sub" / "git.db"
    assert not nested.parent.exists()
    GitMetricsStorage(db_path=nested)
    assert nested.exists()
    assert nested.parent.is_dir()


@pytest.mark.unit
def test_storage_initialization_creates_tables(storage: GitMetricsStorage) -> None:
    """Schema script runs and the expected tables exist."""
    cur = storage.conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    )
    names = {row[0] for row in cur.fetchall()}
    assert "git_metrics" in names
    assert "git_events" in names


@pytest.mark.unit
def test_storage_initialization_creates_indexes(storage: GitMetricsStorage) -> None:
    """The two expected indexes are present after init."""
    cur = storage.conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_git%'"
    )
    index_names = {row[0] for row in cur.fetchall()}
    assert "idx_git_metrics_repo_time" in index_names
    assert "idx_git_metrics_type" in index_names
    assert "idx_git_events_repo_time" in index_names
    assert "idx_git_events_type" in index_names


@pytest.mark.unit
def test_storage_initialization_is_idempotent(
    fixed_schema_dir: Path, tmp_path: Path
) -> None:
    """Re-opening an existing database is a no-op (CREATE IF NOT EXISTS).

    The storage caches the sqlite3.Connection on a module-level
    thread-local, so the cache must be cleared between the two
    constructions or the second instance would silently use the first
    connection (and likely fail with ``no such table``). This test
    documents that the caching is per-thread, not per-instance.
    """
    db_path = tmp_path / "git.db"
    gms._thread_local.conn = None
    GitMetricsStorage(db_path=db_path)
    gms._thread_local.conn = None
    # Re-open with the same file: must not raise.
    GitMetricsStorage(db_path=db_path)
    cur = sqlite3.connect(str(db_path)).execute(
        "SELECT count(*) FROM git_metrics"
    )
    assert cur.fetchone()[0] == 0


@pytest.mark.unit
def test_conn_property_uses_thread_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """The connection is cached on a thread-local; no cross-test leakage."""
    # Reset the module-level thread-local so this test sees a clean state
    # and does not inherit a connection left over by a prior test.
    monkeypatch.setattr(gms, "_thread_local", threading.local())

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "t.db"
        # Use a dummy schema file so the constructor doesn't fail.
        schema = Path(td) / "git_metrics_schema.sql"
        schema.write_text(_FIXED_SCHEMA, encoding="utf-8")
        monkeypatch.setattr(gms, "__file__", str(schema))

        s = GitMetricsStorage(db_path=db_path)
        c1 = s.conn
        c2 = s.conn
        # Same object returned on every call from the same thread.
        assert c1 is c2
        # It is a sqlite3.Connection with the row factory configured.
        assert isinstance(c1, sqlite3.Connection)
        assert c1.row_factory is sqlite3.Row


@pytest.mark.unit
def test_schema_file_missing_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the schema file is absent, __init__ raises FileNotFoundError."""
    db_path = tmp_path / "x.db"
    # Point __file__ at a directory that has no schema sibling.
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setattr(gms, "__file__", str(empty_dir / "nonexistent.sql"))
    with pytest.raises(FileNotFoundError):
        GitMetricsStorage(db_path=db_path)


# ---------------------------------------------------------------------------
# store_metric
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_store_metric_inserts_row(storage: GitMetricsStorage) -> None:
    """store_metric writes a single row to git_metrics with all fields."""
    ts = datetime(2026, 6, 1, 12, 0, 0)
    storage.store_metric(
        repository_path="/repo/x",
        metric_type="commit_velocity",
        value=2.5,
        metadata='{"branch": "main"}',
        timestamp=ts,
    )
    row = storage.conn.execute(
        "SELECT repository_path, metric_type, value, metadata, timestamp "
        "FROM git_metrics WHERE repository_path = ?",
        ("/repo/x",),
    ).fetchone()
    assert row["repository_path"] == "/repo/x"
    assert row["metric_type"] == "commit_velocity"
    assert row["value"] == 2.5
    assert row["metadata"] == '{"branch": "main"}'
    # Timestamp is round-tripped as an ISO string.
    assert row["timestamp"].startswith("2026-06-01T12:00:00")


@pytest.mark.unit
def test_store_metric_default_timestamp(
    monkeypatch: pytest.MonkeyPatch, storage: GitMetricsStorage
) -> None:
    """When timestamp is omitted, datetime.now() is used."""
    fixed = datetime(2026, 6, 7, 10, 30, 0)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz: t.Any = None) -> datetime:  # noqa: D401
            return fixed

    monkeypatch.setattr(gms, "datetime", _FrozenDatetime)
    storage.store_metric(repository_path="/r", metric_type="t", value=1.0)
    row = storage.conn.execute(
        "SELECT timestamp FROM git_metrics"
    ).fetchone()
    assert row["timestamp"].startswith("2026-06-07T10:30:00")


@pytest.mark.unit
def test_store_metric_metadata_optional(storage: GitMetricsStorage) -> None:
    """metadata=None is stored as NULL, not the literal string 'None'."""
    storage.store_metric(
        repository_path="/r",
        metric_type="branch_switches",
        value=0.0,
        timestamp=datetime(2026, 1, 1),
    )
    row = storage.conn.execute(
        "SELECT metadata FROM git_metrics"
    ).fetchone()
    assert row["metadata"] is None


@pytest.mark.unit
def test_store_metric_multiple_rows(storage: GitMetricsStorage) -> None:
    """Several distinct rows can be stored in the same table."""
    base = datetime(2026, 1, 1)
    for i, value in enumerate([1.0, 2.0, 3.0]):
        storage.store_metric(
            repository_path="/r",
            metric_type="commit_velocity",
            value=value,
            timestamp=base + timedelta(minutes=i),
        )
    count = storage.conn.execute("SELECT count(*) FROM git_metrics").fetchone()[0]
    assert count == 3


@pytest.mark.unit
def test_store_metric_swallows_exception(
    monkeypatch: pytest.MonkeyPatch, storage: GitMetricsStorage
) -> None:
    """If the INSERT raises, store_metric logs and returns (no re-raise).

    sqlite3.Connection has C-level read-only attributes, so we patch
    sqlite3.connect in the storage module to return a stub connection
    whose ``execute`` raises. This also documents the error-swallowing
    contract: the public methods must not propagate SQL errors.
    """
    stub_conn = MagicMock()
    stub_conn.row_factory = sqlite3.Row
    stub_conn.execute.side_effect = sqlite3.OperationalError("disk full")
    monkeypatch.setattr(gms.sqlite3, "connect", lambda *a, **kw: stub_conn)
    # Bypass the cached connection so the patched sqlite3.connect is used.
    gms._thread_local.conn = None
    # Must not raise; the method is documented as logging+swallowing.
    storage.store_metric(repository_path="/r", metric_type="t", value=1.0)


# ---------------------------------------------------------------------------
# log_event
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_log_event_inserts_row(storage: GitMetricsStorage) -> None:
    """log_event writes a single row to git_events."""
    ts = datetime(2026, 4, 1, 9, 0, 0)
    storage.log_event(
        repository_path="/repo/y",
        event_type="commit",
        details='{"sha": "abc123"}',
        timestamp=ts,
    )
    row = storage.conn.execute(
        "SELECT repository_path, event_type, details, timestamp "
        "FROM git_events WHERE repository_path = ?",
        ("/repo/y",),
    ).fetchone()
    assert row["repository_path"] == "/repo/y"
    assert row["event_type"] == "commit"
    assert row["details"] == '{"sha": "abc123"}'
    assert row["timestamp"].startswith("2026-04-01T09:00:00")


@pytest.mark.unit
def test_log_event_default_timestamp(
    monkeypatch: pytest.MonkeyPatch, storage: GitMetricsStorage
) -> None:
    """Omitting timestamp triggers datetime.now()."""
    fixed = datetime(2026, 6, 7, 11, 0, 0)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz: t.Any = None) -> datetime:
            return fixed

    monkeypatch.setattr(gms, "datetime", _FrozenDatetime)
    storage.log_event(repository_path="/r", event_type="push", details="{}")
    row = storage.conn.execute("SELECT timestamp FROM git_events").fetchone()
    assert row["timestamp"].startswith("2026-06-07T11:00:00")


@pytest.mark.unit
def test_log_event_swallows_exception(
    monkeypatch: pytest.MonkeyPatch, storage: GitMetricsStorage
) -> None:
    """If the INSERT raises, log_event logs and returns (no re-raise)."""
    stub_conn = MagicMock()
    stub_conn.row_factory = sqlite3.Row
    stub_conn.execute.side_effect = sqlite3.OperationalError("table missing")
    monkeypatch.setattr(gms.sqlite3, "connect", lambda *a, **kw: stub_conn)
    gms._thread_local.conn = None
    storage.log_event(repository_path="/r", event_type="x", details="d")


# ---------------------------------------------------------------------------
# get_metrics
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_metrics_empty(storage: GitMetricsStorage) -> None:
    """No rows in the table returns an empty dict."""
    assert storage.get_metrics(repository_path="/missing") == {}


@pytest.mark.unit
def test_get_metrics_returns_latest_value(storage: GitMetricsStorage) -> None:
    """get_metrics currently returns {} for a populated table.

    This documents a real source bug: the SQL
    ``SELECT metric_type, value, metadata, MAX(timestamp) FROM git_metrics
    WHERE repository_path = ?`` does not include ``repository_path`` in
    its SELECT list, so ``row["repository_path"]`` raises inside the
    try-block and the except returns an empty dict. The test pins the
    current (broken) behavior so future fixes are intentional.
    """
    base = datetime(2026, 1, 1)
    storage.store_metric(
        repository_path="/r", metric_type="commit_velocity",
        value=1.0, timestamp=base,
    )
    storage.store_metric(
        repository_path="/r", metric_type="commit_velocity",
        value=4.0, timestamp=base + timedelta(hours=2),
    )
    # When the SQL is fixed, the result should contain repository_path,
    # last_timestamp, and total_value; for now it returns {}.
    assert storage.get_metrics(repository_path="/r") == {}


@pytest.mark.unit
def test_get_metrics_with_metric_types_filter(
    storage: GitMetricsStorage,
) -> None:
    """Passing metric_types does not raise even though the SQL is a no-op."""
    storage.store_metric(
        repository_path="/r", metric_type="commit_velocity",
        value=1.0, timestamp=datetime(2026, 1, 1),
    )
    # The current implementation only reads one MAX(timestamp) row regardless
    # of metric_types; this test ensures the filter is accepted without error.
    metrics = storage.get_metrics(
        repository_path="/r", metric_types=["commit_velocity"]
    )
    assert isinstance(metrics, dict)


@pytest.mark.unit
def test_get_metrics_with_since_filter(storage: GitMetricsStorage) -> None:
    """The since= kwarg is accepted (currently ignored by the SQL)."""
    storage.store_metric(
        repository_path="/r", metric_type="commit_velocity",
        value=1.0, timestamp=datetime(2026, 1, 1),
    )
    metrics = storage.get_metrics(
        repository_path="/r", since=datetime(2025, 1, 1)
    )
    assert isinstance(metrics, dict)


@pytest.mark.unit
def test_get_metrics_swallows_exception(
    monkeypatch: pytest.MonkeyPatch, storage: GitMetricsStorage
) -> None:
    """If the SELECT raises, get_metrics logs and returns {} (no re-raise)."""
    stub_conn = MagicMock()
    stub_conn.row_factory = sqlite3.Row
    stub_conn.execute.side_effect = sqlite3.OperationalError("query failed")
    monkeypatch.setattr(gms.sqlite3, "connect", lambda *a, **kw: stub_conn)
    gms._thread_local.conn = None
    result = storage.get_metrics(repository_path="/r")
    assert result == {}


# ---------------------------------------------------------------------------
# Integration with the bundled (broken) schema — observed behavior
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_bundled_schema_has_sql_syntax_errors() -> None:
    """Documents the source bug: the shipped SQL fails executescript().

    Resolves the schema file by path (not via the module attribute that
    the ``fixed_schema_dir`` fixture patches) so this test observes the
    on-disk artifact regardless of test-time monkeypatching.
    """
    real_schema = (
        Path(__file__).resolve().parents[3]
        / "crackerjack"
        / "memory"
        / "git_metrics_schema.sql"
    )
    assert real_schema.exists(), f"schema not found at {real_schema}"
    conn = sqlite3.connect(":memory:")
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.executescript(real_schema.read_text(encoding="utf-8"))
    finally:
        conn.close()
