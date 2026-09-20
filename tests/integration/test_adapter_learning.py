"""Tests for the SQLite adapter learner and its factory.

The Dhara backend was decommissioned on 2026-09-20, so the only learner
backends covered here are SQLite and NoOp. Tests that previously exercised
the Dhara backend (and the in-process Dhara MCP factory selection) lived in
files that were removed when the backend was retired:

- ``tests/integration/dhara_mcp_client_test.py``
- ``tests/integration/dhara_mcp_adapter_learner_test.py``
- ``tests/integration/test_aio_thread_leak_regression.py``
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from crackerjack.integration import (
    AdapterAttemptRecord,
    AdapterLearningIntegration,
    NoOpAdapterLearner,
    SQLiteAdapterLearner,
    create_adapter_learner,
)


class TestAdapterAttemptRecord:
    """Test AdapterAttemptRecord data model."""

    def test_create_record(self) -> None:
        record = AdapterAttemptRecord(
            adapter_name="ruff",
            file_type=".py",
            file_size=1024,
            project_context={"phase": "fast"},
            success=True,
            execution_time_ms=150,
            error_type=None,
            timestamp=datetime.now(),
        )
        assert record.adapter_name == "ruff"
        assert record.success is True

    def test_roundtrip(self) -> None:
        record = AdapterAttemptRecord(
            adapter_name="bandit",
            file_type=".py",
            file_size=2048,
            project_context={},
            success=False,
            execution_time_ms=300,
            error_type="SecurityError",
            timestamp=datetime.now(),
        )
        restored = AdapterAttemptRecord.from_dict(record.to_dict())
        assert restored.adapter_name == record.adapter_name
        assert restored.file_type == record.file_type
        assert restored.success == record.success
        assert restored.error_type == record.error_type


class TestNoOpAdapterLearner:
    """Test NoOpAdapterLearner does nothing."""

    def test_is_noop(self) -> None:
        learner = NoOpAdapterLearner()
        assert not learner.is_enabled()

    def test_record_is_noop(self) -> None:
        learner = NoOpAdapterLearner()
        record = AdapterAttemptRecord(
            adapter_name="ruff",
            file_type=".py",
            file_size=100,
            project_context={},
            success=True,
            execution_time_ms=50,
            error_type=None,
            timestamp=datetime.now(),
        )
        # Should not raise
        learner.record_adapter_attempt(record)

    def test_recommend_returns_none(self) -> None:
        learner = NoOpAdapterLearner()
        assert learner.recommend_adapter("test.py", {}, ["ruff"]) is None

    def test_get_effectiveness_returns_none(self) -> None:
        learner = NoOpAdapterLearner()
        assert learner.get_adapter_effectiveness("ruff", ".py") is None

    def test_get_best_adapters_returns_empty(self) -> None:
        learner = NoOpAdapterLearner()
        assert learner.get_best_adapters_for_file_type(".py") == []


class TestCreateAdapterLearner:
    """Test factory function."""

    def test_disabled_returns_noop(self) -> None:
        learner = create_adapter_learner(enabled=False)
        assert isinstance(learner, NoOpAdapterLearner)

    def test_enabled_returns_sqlite(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_adapter_learning.db"
        learner = create_adapter_learner(
            enabled=True, db_path=db_path, backend="sqlite"
        )
        assert isinstance(learner, SQLiteAdapterLearner)
        assert learner.is_enabled()

    def test_enabled_creates_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_adapter_learning.db"
        create_adapter_learner(enabled=True, db_path=db_path, backend="sqlite")
        assert db_path.exists()

    def test_legacy_non_sqlite_file_is_quarantined_then_replaced(
        self, tmp_path: Path
    ) -> None:
        """Garbage at the configured path → quarantined + fresh SQLite at same path.

        Regression test for the ``file is not a database`` error that
        surfaced on every ``crackerjack run`` in repos whose
        ``.crackerjack/adapter_learning.db`` predated the Dhara→SQLite
        switch (the Dhara backend wrote ``PersistentDict`` shelves to that
        filename). The factory must detect the mismatch, move the legacy
        file aside, and create a fresh SQLite db in place.
        """
        from crackerjack.integration.adapter_learning import _is_valid_sqlite_file

        db_path = tmp_path / "adapter_learning.db"
        db_path.write_bytes(b"some legacy content not a db")
        assert db_path.exists()

        learner = create_adapter_learner(
            enabled=True, db_path=db_path, backend="sqlite"
        )

        # Fresh SQLite learner at the same path.
        assert isinstance(learner, SQLiteAdapterLearner)
        assert learner.is_enabled()
        # Original path now holds a valid SQLite database.
        assert db_path.exists()
        assert _is_valid_sqlite_file(db_path)
        # And the original bytes were preserved under a timestamped sibling.
        siblings = list(tmp_path.glob("adapter_learning.db.legacy-*"))
        assert len(siblings) == 1
        assert siblings[0].read_bytes() == b"some legacy content not a db"

    def test_legacy_pickle_is_quarantined_then_replaced(
        self, tmp_path: Path
    ) -> None:
        """Realistic Dhara ``PersistentDict`` SHELF file → same quarantine flow.

        Mirrors the actual bytes observed at
        ``/Users/les/Projects/mahavishnu/.crackerjack/adapter_learning.db``
        on 2026-09-20: ``SHELF-1\\n`` header followed by pickle opcodes
        referencing ``dhara.collections.dict.PersistentDict``.
        """
        from crackerjack.integration.adapter_learning import _is_valid_sqlite_file

        db_path = tmp_path / "adapter_learning.db"
        db_path.write_bytes(
            b"SHELF-1\n\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x01"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00c"
            b"\x00\x00\x00\x00\x00[\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00G\x80\x02cdhara.collections"
        )

        learner = create_adapter_learner(
            enabled=True, db_path=db_path, backend="sqlite"
        )

        assert isinstance(learner, SQLiteAdapterLearner)
        assert _is_valid_sqlite_file(db_path)
        siblings = list(tmp_path.glob("adapter_learning.db.legacy-*"))
        assert len(siblings) == 1
        assert siblings[0].read_bytes().startswith(b"SHELF-1\n")

    def test_valid_sqlite_db_is_not_quarantined(self, tmp_path: Path) -> None:
        """Pre-existing valid SQLite db must not be touched by the factory."""
        import sqlite3

        from crackerjack.integration.adapter_learning import _is_valid_sqlite_file

        db_path = tmp_path / "adapter_learning.db"
        # Seed a recognizable SQLite db with a user table.
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE user_data (x INTEGER)")
        conn.execute("INSERT INTO user_data VALUES (42)")
        conn.commit()
        conn.close()

        learner = create_adapter_learner(
            enabled=True, db_path=db_path, backend="sqlite"
        )

        assert isinstance(learner, SQLiteAdapterLearner)
        # No quarantine sibling should exist.
        assert list(tmp_path.glob("adapter_learning.db.legacy-*")) == []
        # Original db is intact and still contains the seeded row.
        assert _is_valid_sqlite_file(db_path)
        conn = sqlite3.connect(str(db_path))
        (value,) = conn.execute("SELECT x FROM user_data").fetchone()
        conn.close()
        assert value == 42

    def test_missing_path_is_not_quarantined_and_factory_succeeds(
        self, tmp_path: Path
    ) -> None:
        """No file at the path → no quarantine, fresh SQLite created."""
        from crackerjack.integration.adapter_learning import _is_valid_sqlite_file

        db_path = tmp_path / "adapter_learning.db"
        assert not db_path.exists()

        learner = create_adapter_learner(
            enabled=True, db_path=db_path, backend="sqlite"
        )

        assert isinstance(learner, SQLiteAdapterLearner)
        assert db_path.exists()
        assert _is_valid_sqlite_file(db_path)
        assert list(tmp_path.glob("adapter_learning.db.legacy-*")) == []


class TestSQLiteAdapterLearner:
    """Test SQLite adapter learner with real database."""

    def test_record_and_get_effectiveness(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path)

        record = AdapterAttemptRecord(
            adapter_name="ruff",
            file_type=".py",
            file_size=500,
            project_context={},
            success=True,
            execution_time_ms=100,
            error_type=None,
            timestamp=datetime.now(),
        )
        learner.record_adapter_attempt(record)

        effectiveness = learner.get_adapter_effectiveness("ruff", ".py")
        assert effectiveness is not None
        assert effectiveness.adapter_name == "ruff"
        assert effectiveness.total_attempts == 1
        assert effectiveness.successful_attempts == 1
        assert effectiveness.success_rate == 1.0

    def test_get_best_adapters(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path, min_attempts=1)

        for i in range(3):
            record = AdapterAttemptRecord(
                adapter_name="ruff",
                file_type=".py",
                file_size=500,
                project_context={},
                success=True,
                execution_time_ms=100,
                error_type=None,
                timestamp=datetime.now(),
            )
            learner.record_adapter_attempt(record)

        best = learner.get_best_adapters_for_file_type(".py")
        assert len(best) >= 1
        assert best[0][0] == "ruff"

    def test_recommend_after_enough_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path, min_attempts=3)

        for _ in range(5):
            record = AdapterAttemptRecord(
                adapter_name="ruff",
                file_type=".py",
                file_size=500,
                project_context={},
                success=True,
                execution_time_ms=100,
                error_type=None,
                timestamp=datetime.now(),
            )
            learner.record_adapter_attempt(record)

        rec = learner.recommend_adapter("test.py", {}, ["ruff", "bandit"])
        assert rec == "ruff"


class TestAdapterLearningIntegration:
    """Test AdapterLearningIntegration wrapper."""

    def test_tracks_via_learner(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path)
        integration = AdapterLearningIntegration(adapter_learner=learner)

        integration.track_adapter_execution(
            adapter_name="ruff",
            file_path="test.py",
            file_size=1024,
            project_context={},
            success=True,
            execution_time_ms=200,
        )

        effectiveness = integration.get_adapter_stats("ruff", ".py")
        assert effectiveness is not None
        assert effectiveness.total_attempts == 1

    def test_get_recommendation(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path, min_attempts=2)
        integration = AdapterLearningIntegration(adapter_learner=learner)

        for _ in range(3):
            integration.track_adapter_execution(
                adapter_name="bandit",
                file_path="test.py",
                file_size=500,
                project_context={},
                success=True,
                execution_time_ms=300,
            )

        rec = integration.get_adapter_recommendation(
            file_path="test.py",
            project_context={},
            available_adapters=["bandit", "ruff"],
        )
        assert rec == "bandit"

    def test_noop_integration_does_nothing(self) -> None:
        learner = NoOpAdapterLearner()
        integration = AdapterLearningIntegration(adapter_learner=learner)

        integration.track_adapter_execution(
            adapter_name="ruff",
            file_path="test.py",
            file_size=100,
            project_context={},
            success=True,
            execution_time_ms=50,
        )

        assert integration.get_adapter_stats("ruff", ".py") is None

class TestFactoryBackendSelection:
    """Test SQLite backend selection logic."""

    def test_sqlite_backend_explicit(self, tmp_path: Path) -> None:
        db_path = tmp_path / "sqlite_test.db"
        learner = create_adapter_learner(
            enabled=True,
            backend="sqlite",
            db_path=db_path,
        )
        assert isinstance(learner, SQLiteAdapterLearner)
