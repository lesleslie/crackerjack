"""Tests for Dhara adapter learning integration."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from crackerjack.integration import (
    AdapterAttemptRecord,
    AdapterEffectiveness,
    AdapterLearnerProtocol,
    DharaLearningIntegration,
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
            adapter_name="ruff", file_type=".py", file_size=100,
            project_context={}, success=True, execution_time_ms=50,
            error_type=None, timestamp=datetime.now(),
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
        learner = create_adapter_learner(enabled=True, db_path=db_path)
        assert isinstance(learner, SQLiteAdapterLearner)
        assert learner.is_enabled()

    def test_enabled_creates_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_adapter_learning.db"
        create_adapter_learner(enabled=True, db_path=db_path)
        assert db_path.exists()


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


class TestDharaLearningIntegration:
    """Test DharaLearningIntegration wrapper."""

    def test_tracks_via_learner(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path)
        integration = DharaLearningIntegration(adapter_learner=learner)

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
        integration = DharaLearningIntegration(adapter_learner=learner)

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
        integration = DharaLearningIntegration(adapter_learner=learner)

        integration.track_adapter_execution(
            adapter_name="ruff",
            file_path="test.py",
            file_size=100,
            project_context={},
            success=True,
            execution_time_ms=50,
        )

        assert integration.get_adapter_stats("ruff", ".py") is None
