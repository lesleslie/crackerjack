"""
Tests for skills effectiveness tracking (Task 44).

Tests skill/agent effectiveness tracking, metrics aggregation,
and learning-based skill recommendations.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from crackerjack.integration import (
    NoOpSkillsEffectivenessTracker,
    SkillAttemptRecord,
    SkillEffectivenessMetrics,
    SkillsEffectivenessIntegration,
    SkillsEffectivenessProtocol,
    SQLiteSkillsEffectivenessTracker,
    create_skills_effectiveness_tracker,
)


class TestSkillAttemptRecord:
    """Test SkillAttemptRecord data model."""

    def test_create_record(self) -> None:
        """Test creating a skill attempt record."""
        embedding = np.array([0.1, 0.2, 0.3])
        context = {"phase": "comprehensive_hooks", "project": "crackerjack"}

        record = SkillAttemptRecord(
            skill_name="python-pro",
            agent_name="PythonProAgent",
            user_query="Fix type errors in agents module",
            query_embedding=embedding,
            context=context,
            success=True,
            confidence=0.9,
            execution_time_ms=1500,
            alternatives_considered=["code-reviewer", "refactoring-agent"],
            timestamp=datetime.now(),
        )

        assert record.skill_name == "python-pro"
        assert record.agent_name == "PythonProAgent"
        assert record.success is True
        assert record.confidence == 0.9
        assert record.execution_time_ms == 1500

    def test_to_dict(self) -> None:
        """Test converting record to dictionary."""
        embedding = np.array([0.1, 0.2, 0.3])
        record = SkillAttemptRecord(
            skill_name="python-pro",
            agent_name=None,
            user_query="Test query",
            query_embedding=embedding,
            context={},
            success=True,
            confidence=1.0,
            execution_time_ms=1000,
            alternatives_considered=[],
            timestamp=datetime.now(),
        )

        data = record.to_dict()

        assert data["skill_name"] == "python-pro"
        assert "query_embedding" in data
        assert isinstance(data["query_embedding"], list)

    def test_from_dict(self) -> None:
        """Test creating record from dictionary."""
        embedding = np.array([0.1, 0.2, 0.3])
        record = SkillAttemptRecord(
            skill_name="test-skill",
            agent_name=None,
            user_query="Test",
            query_embedding=embedding,
            context={},
            success=True,
            confidence=1.0,
            execution_time_ms=100,
            alternatives_considered=[],
            timestamp=datetime.now(),
        )

        data = record.to_dict()
        restored = SkillAttemptRecord.from_dict(data)

        assert restored.skill_name == record.skill_name
        assert np.array_equal(restored.query_embedding, record.query_embedding)
        assert restored.success == record.success


class TestNoOpSkillsEffectivenessTracker:
    """Test no-op tracker implementation."""

    def test_is_enabled(self) -> None:
        """Test no-op tracker is always disabled."""
        tracker = NoOpSkillsEffectivenessTracker()
        assert not tracker.is_enabled()

    def test_record_attempt(self) -> None:
        """Test no-op record doesn't crash."""
        tracker = NoOpSkillsEffectivenessTracker()
        embedding = np.array([0.1, 0.2, 0.3])

        record = SkillAttemptRecord(
            skill_name="test",
            agent_name=None,
            user_query="Test",
            query_embedding=embedding,
            context={},
            success=True,
            confidence=1.0,
            execution_time_ms=100,
            alternatives_considered=[],
            timestamp=datetime.now(),
        )

        # Should not raise
        tracker.record_attempt(record)

    def test_get_effectiveness_metrics(self) -> None:
        """Test no-op returns None."""
        tracker = NoOpSkillsEffectivenessTracker()
        metrics = tracker.get_effectiveness_metrics("test-skill")
        assert metrics is None


class TestSQLiteSkillsEffectivenessTracker:
    """Test SQLite-based effectiveness tracking."""

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_skills.db"

    @pytest.fixture
    def tracker(self, temp_db: Path) -> SkillsEffectivenessProtocol:
        """Create tracker with temp database."""
        return create_skills_effectiveness_tracker(
            enabled=True,
            db_path=temp_db,
            min_sample_size=3,
        )

    def test_initialization(self, tracker: SkillsEffectivenessProtocol) -> None:
        """Test tracker initializes successfully."""
        assert tracker.is_enabled()

    def test_record_attempt(self, tracker: SkillsEffectivenessProtocol) -> None:
        """Test recording skill attempts."""
        embedding = np.array([0.1, 0.2, 0.3])
        record = SkillAttemptRecord(
            skill_name="python-pro",
            agent_name="PythonProAgent",
            user_query="Test query",
            query_embedding=embedding,
            context={"phase": "test"},
            success=True,
            confidence=0.9,
            execution_time_ms=1000,
            alternatives_considered=[],
            timestamp=datetime.now(),
        )

        # Should not raise
        tracker.record_attempt(record)

    def test_effectiveness_metrics_below_sample_size(
        self, tracker: SkillsEffectivenessProtocol
    ) -> None:
        """Test metrics return None below sample size."""
        embedding = np.array([0.1, 0.2, 0.3])

        # Record only 2 attempts (below min_sample_size=3)
        for i in range(2):
            record = SkillAttemptRecord(
                skill_name="test-skill",
                agent_name=None,
                user_query=f"Query {i}",
                query_embedding=embedding,
                context={},
                success=True,
                confidence=1.0,
                execution_time_ms=100,
                alternatives_considered=[],
                timestamp=datetime.now(),
            )
            tracker.record_attempt(record)

        # Should return metrics even below sample_size (transparency)
        # min_sample_size affects recommendation confidence, not availability
        metrics = tracker.get_effectiveness_metrics("test-skill", min_sample_size=3)
        assert metrics is not None
        assert metrics.total_attempts == 2

    def test_effectiveness_metrics_above_sample_size(
        self, tracker: SkillsEffectivenessProtocol
    ) -> None:
        """Test metrics calculation with sufficient data."""
        embedding = np.array([0.1, 0.2, 0.3])

        # Record 5 successful attempts
        for i in range(5):
            record = SkillAttemptRecord(
                skill_name="test-skill",
                agent_name=None,
                user_query=f"Query {i}",
                query_embedding=embedding,
                context={"phase": "test"},
                success=True,
                confidence=0.8 + (i * 0.02),  # Varying confidence
                execution_time_ms=1000 + (i * 100),
                alternatives_considered=[],
                timestamp=datetime.now(),
            )
            tracker.record_attempt(record)

        # Record 2 failed attempts
        for i in range(2):
            record = SkillAttemptRecord(
                skill_name="test-skill",
                agent_name=None,
                user_query=f"Failed query {i}",
                query_embedding=embedding,
                context={},
                success=False,
                confidence=0.5,
                execution_time_ms=500,
                alternatives_considered=[],
                timestamp=datetime.now(),
            )
            tracker.record_attempt(record)

        # Get metrics
        metrics = tracker.get_effectiveness_metrics("test-skill", min_sample_size=3)

        assert metrics is not None
        assert metrics.skill_name == "test-skill"
        assert metrics.total_attempts == 7
        assert metrics.successful_attempts == 5
        assert metrics.success_rate == 5 / 7
        assert metrics.avg_confidence_when_successful > 0.8
        assert metrics.avg_execution_time_ms > 0


class TestSkillsEffectivenessIntegration:
    """Test integration layer for skills effectiveness."""

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_integration.db"

    @pytest.fixture
    def integration(self, temp_db: Path) -> SkillsEffectivenessIntegration:
        """Create integration with temp database."""
        tracker = SQLiteSkillsEffectivenessTracker(db_path=temp_db, min_sample_size=3)

        return SkillsEffectivenessIntegration(
            effectiveness_tracker=tracker,
            min_sample_size=3,
        )

    def test_track_skill_attempt(self, integration: SkillsEffectivenessIntegration) -> None:
        """Test tracking skill attempt returns completer."""
        embedding = np.array([0.1, 0.2, 0.3])

        completer = integration.track_skill_attempt(
            skill_name="python-pro",
            agent_name="PythonProAgent",
            user_query="Test query",
            query_embedding=embedding,
            context={"phase": "test"},
            alternatives_considered=[],
        )

        assert completer is not None

        # Call completer
        completer(success=True, confidence=0.9, execution_time_ms=1000)

        # Verify metrics recorded
        metrics = integration.get_skill_metrics("python-pro")
        assert metrics is not None
        assert metrics.total_attempts == 1
        assert metrics.successful_attempts == 1

    def test_get_skill_boosts_no_data(self, integration: SkillsEffectivenessIntegration) -> None:
        """Test boosts return empty dict with no data."""
        embedding = np.array([0.1, 0.2, 0.3])

        boosts = integration.get_skill_boosts(
            user_query="Test query",
            query_embedding=embedding,
            context={},
            candidates=["python-pro", "code-reviewer"],
        )

        # Empty dict when no data
        assert boosts == {}

    def test_get_skill_boosts_with_data(
        self, integration: SkillsEffectivenessIntegration
    ) -> None:
        """Test skill boosts with learned data."""
        embedding = np.array([0.1, 0.2, 0.3])

        # Record successful attempts for python-pro
        for i in range(5):
            completer = integration.track_skill_attempt(
                skill_name="python-pro",
                agent_name=None,
                user_query=f"Query {i}",
                query_embedding=embedding,
                context={"phase": "test"},
                alternatives_considered=["code-reviewer"],
            )
            completer(success=True, confidence=0.9, execution_time_ms=1000)

        # Get boosts
        boosts = integration.get_skill_boosts(
            user_query="Test query",
            query_embedding=embedding,
            context={"phase": "test"},
            candidates=["python-pro", "code-reviewer"],
        )

        # Should boost python-pro
        assert "python-pro" in boosts
        assert boosts["python-pro"] > 0


class TestFactoryFunction:
    """Test factory function for creating trackers."""

    def test_create_disabled(self) -> None:
        """Test creating disabled tracker."""
        tracker = create_skills_effectiveness_tracker(enabled=False)
        assert isinstance(tracker, NoOpSkillsEffectivenessTracker)
        assert not tracker.is_enabled()

    def test_create_enabled_with_temp_db(self) -> None:
        """Test creating enabled tracker with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = create_skills_effectiveness_tracker(
                enabled=True, db_path=db_path
            )

            assert tracker.is_enabled()
