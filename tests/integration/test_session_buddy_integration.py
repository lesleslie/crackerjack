"""Integration tests for session-buddy git velocity metrics correlation.

Tests integration between:
- GitMetricsStorage (crackerjack git metrics)
- SessionBuddy (workflow metrics)
- CorrelationEngine (pattern detection)
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from crackerjack.integration.session_buddy_integration import (
    CorrelationInsight,
    CorrelationStorageSQLite,
    ExtendedSessionMetrics,
    GitVelocityMetrics,
    NoOpCorrelationStorage,
    NoOpGitMetricsReader,
    NoOpSessionBuddyClient,
    SessionBuddyDirectClient,
    SessionBuddyIntegration,
    create_session_buddy_integration,
)


class MockGitMetricsReader:
    """Mock git metrics reader for testing."""

    def __init__(self) -> None:
        self.metrics: list[dict] = []

    def add_metric(
        self,
        metric_type: str,
        value: float,
        timestamp: datetime,
    ) -> None:
        """Add a metric for testing."""
        self.metrics.append({
            "metric_type": metric_type,
            "value": value,
            "timestamp": timestamp,
        })

    def get_metrics(
        self,
        repository_path: str,
        metric_types: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict]:
        """Return filtered metrics."""
        filtered = self.metrics.copy()

        if repository_path:
            # In real implementation, would filter by repo
            pass

        if metric_types:
            filtered = [m for m in filtered if m["metric_type"] in metric_types]

        if since:
            filtered = [m for m in filtered if m["timestamp"] >= since]

        if until:
            filtered = [m for m in filtered if m["timestamp"] <= until]

        return filtered

    def get_latest_metrics(self, repository_path: str) -> dict[str, dict]:
        """Return latest metrics grouped by type."""
        latest: dict[str, dict] = {}

        for metric in self.metrics:
            metric_type = metric["metric_type"]
            if metric_type not in latest or metric["timestamp"] > latest[metric_type]["timestamp"]:
                latest[metric_type] = metric

        return latest


class MockSessionBuddyClient:
    """Mock session-buddy client for testing."""

    def __init__(self) -> None:
        self.sessions: list[dict] = []

    def add_session(self, session: dict) -> None:
        """Add a session for testing."""
        self.sessions.append(session)

    async def get_session_metrics(
        self,
        session_id: str | None = None,
        project_path: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """Return filtered sessions."""
        filtered = self.sessions.copy()

        if session_id:
            filtered = [s for s in filtered if s["session_id"] == session_id]

        if project_path:
            filtered = [s for s in filtered if s["project_path"] == project_path]

        if start_date:
            filtered = [s for s in filtered if datetime.fromisoformat(s["started_at"]) >= start_date]

        if end_date:
            filtered = [s for s in filtered if datetime.fromisoformat(s["started_at"]) <= end_date]

        return filtered

    async def get_workflow_metrics(
        self,
        project_path: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict | None:
        """Return workflow metrics."""
        if not self.sessions:
            return None

        # Calculate simple workflow metrics
        total_sessions = len(self.sessions)
        avg_quality = sum(s.get("avg_quality", 0) for s in self.sessions) / total_sessions

        # Determine quality trend
        qualities = [s.get("avg_quality", 0) for s in self.sessions]
        if len(qualities) >= 2:
            if qualities[-1] > qualities[0] + 5:
                quality_trend = "improving"
            elif qualities[-1] < qualities[0] - 5:
                quality_trend = "declining"
            else:
                quality_trend = "stable"
        else:
            quality_trend = "stable"

        return type("WorkflowMetrics", (), {
            "total_sessions": total_sessions,
            "avg_quality_score": avg_quality,
            "quality_trend": quality_trend,
            "avg_velocity_commits_per_hour": 2.5,
        })()


class TestExtendedSessionMetrics:
    """Tests for ExtendedSessionMetrics dataclass."""

    def test_extended_metrics_with_git_fields(self) -> None:
        """Test creating extended metrics with git velocity fields."""
        now = datetime.now(UTC)

        metrics = ExtendedSessionMetrics(
            session_id="test-session",
            project_path="/test/project",
            started_at=now,
            ended_at=now + timedelta(hours=1),
            duration_minutes=60.0,
            checkpoint_count=5,
            commit_count=10,
            quality_start=80.0,
            quality_end=85.0,
            quality_delta=5.0,
            avg_quality=82.5,
            files_modified=15,
            tools_used=["ruff", "pytest"],
            primary_language="Python",
            time_of_day="morning",
            # Extended git fields
            git_velocity_per_hour=10.0,
            git_velocity_per_day=80.0,
            git_conventional_compliance=0.95,
            git_breaking_changes=1,
            git_avg_commits_per_week=50.0,
            git_most_active_hour=10,
            git_most_active_day=1,
        )

        assert metrics.session_id == "test-session"
        assert metrics.git_velocity_per_hour == 10.0
        assert metrics.git_conventional_compliance == 0.95
        assert metrics.git_breaking_changes == 1

    def test_extended_metrics_without_git_fields(self) -> None:
        """Test creating extended metrics without git velocity data."""
        now = datetime.now(UTC)

        metrics = ExtendedSessionMetrics(
            session_id="test-session",
            project_path="/test/project",
            started_at=now,
            ended_at=now + timedelta(hours=1),
            duration_minutes=60.0,
            checkpoint_count=5,
            commit_count=10,
            quality_start=80.0,
            quality_end=85.0,
            quality_delta=5.0,
            avg_quality=82.5,
            files_modified=15,
            tools_used=["ruff", "pytest"],
            primary_language="Python",
            time_of_day="morning",
            # Git fields default to None
        )

        assert metrics.git_velocity_per_hour is None
        assert metrics.git_conventional_compliance is None
        assert metrics.git_breaking_changes is None

    def test_to_dict_serialization(self) -> None:
        """Test converting extended metrics to dictionary."""
        now = datetime.now(UTC)

        metrics = ExtendedSessionMetrics(
            session_id="test-session",
            project_path="/test/project",
            started_at=now,
            ended_at=now + timedelta(hours=1),
            duration_minutes=60.0,
            checkpoint_count=5,
            commit_count=10,
            quality_start=80.0,
            quality_end=85.0,
            quality_delta=5.0,
            avg_quality=82.5,
            files_modified=15,
            tools_used=["ruff", "pytest"],
            primary_language="Python",
            time_of_day="morning",
            git_velocity_per_hour=10.0,
        )

        result = metrics.to_dict()

        assert result["session_id"] == "test-session"
        assert result["git_velocity_per_hour"] == 10.0
        assert "started_at" in result
        assert isinstance(result["tools_used"], list)


class TestSessionBuddyIntegration:
    """Tests for SessionBuddyIntegration."""

    async def test_collect_extended_session_metrics_no_data(self) -> None:
        """Test collection when no session data exists."""
        integration = SessionBuddyIntegration(
            git_metrics_reader=NoOpGitMetricsReader(),
            session_buddy_client=NoOpSessionBuddyClient(),
            correlation_storage=NoOpCorrelationStorage(),
        )

        result = await integration.collect_extended_session_metrics(
            session_id="nonexistent",
            project_path="/test/project",
        )

        assert result is None

    async def test_collect_extended_session_metrics_with_data(self) -> None:
        """Test collection with session and git metrics."""
        # Setup mock data
        now = datetime.now(UTC)

        session_client = MockSessionBuddyClient()
        session_client.add_session({
            "session_id": "test-session",
            "project_path": "/test/project",
            "started_at": (now - timedelta(hours=2)).isoformat(),
            "ended_at": now.isoformat(),
            "duration_minutes": 120.0,
            "checkpoint_count": 5,
            "commit_count": 10,
            "quality_start": 80.0,
            "quality_end": 85.0,
            "quality_delta": 5.0,
            "avg_quality": 82.5,
            "files_modified": 15,
            "tools_used": ["ruff", "pytest"],
            "primary_language": "Python",
            "time_of_day": "morning",
        })

        git_reader = MockGitMetricsReader()
        git_reader.add_metric("commit_velocity_per_hour", 5.0, now - timedelta(hours=1))
        git_reader.add_metric("commit_velocity_per_day", 40.0, now - timedelta(hours=1))
        git_reader.add_metric("conventional_compliance_rate", 0.90, now - timedelta(hours=1))
        git_reader.add_metric("breaking_changes", 2, now - timedelta(hours=1))

        integration = SessionBuddyIntegration(
            git_metrics_reader=git_reader,
            session_buddy_client=session_client,
            correlation_storage=NoOpCorrelationStorage(),
        )

        result = await integration.collect_extended_session_metrics(
            session_id="test-session",
            project_path="/test/project",
        )

        assert result is not None
        assert result.session_id == "test-session"
        assert result.git_velocity_per_hour == 5.0
        assert result.git_conventional_compliance == 0.90
        assert result.git_breaking_changes == 2

    async def test_calculate_correlations(self) -> None:
        """Test correlation calculation between git and workflow metrics."""
        session_client = MockSessionBuddyClient()
        session_client.add_session({
            "session_id": "session-1",
            "project_path": "/test/project",
            "started_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "avg_quality": 85.0,
        })
        session_client.add_session({
            "session_id": "session-2",
            "project_path": "/test/project",
            "started_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
            "avg_quality": 80.0,
        })

        git_reader = MockGitMetricsReader()
        now = datetime.now(UTC)
        git_reader.add_metric("conventional_compliance_rate", 0.85, now - timedelta(days=1))
        git_reader.add_metric("conventional_compliance_rate", 0.80, now - timedelta(days=2))

        integration = SessionBuddyIntegration(
            git_metrics_reader=git_reader,
            session_buddy_client=session_client,
            correlation_storage=NoOpCorrelationStorage(),
        )

        insights = await integration.calculate_correlations(
            project_path="/test/project",
            days_back=30,
        )

        # Should generate at least one insight
        assert len(insights) >= 1

        # Check insight structure
        insight = insights[0]
        assert isinstance(insight, CorrelationInsight)
        assert -1.0 <= insight.correlation_coefficient <= 1.0
        assert insight.strength in ("strong", "moderate", "weak", "none")
        assert insight.direction in ("positive", "negative", "neutral")
        assert 0.0 <= insight.confidence <= 1.0


class TestCorrelationStorageSQLite:
    """Tests for CorrelationStorageSQLite."""

    async def test_store_and_retrieve_insights(self) -> None:
        """Test storing and retrieving correlation insights."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_insights.db"
            storage = CorrelationStorageSQLite(db_path=str(db_path))

            # Create test insight
            now = datetime.now(UTC)
            insight = CorrelationInsight(
                correlation_type="quality_vs_velocity",
                correlation_coefficient=0.75,
                strength="strong",
                direction="positive",
                description="Test insight",
                confidence=0.9,
                sample_size=100,
                timestamp=now,
            )

            # Store insight
            await storage.store_insight(insight)

            # Retrieve insights
            retrieved = await storage.get_insights()

            assert len(retrieved) == 1
            assert retrieved[0].correlation_type == "quality_vs_velocity"
            assert retrieved[0].correlation_coefficient == 0.75
            assert retrieved[0].strength == "strong"

    async def test_get_insights_with_date_filter(self) -> None:
        """Test retrieving insights with date filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_insights.db"
            storage = CorrelationStorageSQLite(db_path=str(db_path))

            now = datetime.now(UTC)
            old_time = now - timedelta(days=10)

            # Store two insights with different timestamps
            old_insight = CorrelationInsight(
                correlation_type="test1",
                correlation_coefficient=0.5,
                strength="moderate",
                direction="positive",
                description="Old insight",
                confidence=0.7,
                sample_size=50,
                timestamp=old_time,
            )

            new_insight = CorrelationInsight(
                correlation_type="test2",
                correlation_coefficient=0.8,
                strength="strong",
                direction="positive",
                description="New insight",
                confidence=0.9,
                sample_size=100,
                timestamp=now,
            )

            await storage.store_insight(old_insight)
            await storage.store_insight(new_insight)

            # Retrieve with filter (should only get new insight)
            since = now - timedelta(days=5)
            retrieved = await storage.get_insights(since=since)

            assert len(retrieved) == 1
            assert retrieved[0].correlation_type == "test2"

    def test_close_connection(self) -> None:
        """Test closing database connection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_insights.db"
            storage = CorrelationStorageSQLite(db_path=str(db_path))

            # Verify connection exists
            assert storage.conn is not None

            # Close connection
            storage.close()

            # Verify connection is closed
            assert storage.conn is None


class TestFactoryFunction:
    """Tests for create_session_buddy_integration factory."""

    def test_create_integration_with_defaults(self) -> None:
        """Test factory creates integration with default components."""
        integration = create_session_buddy_integration()

        assert integration is not None
        assert integration.git_reader is not None
        assert integration.session_buddy is not None
        assert integration.storage is not None

    def test_create_integration_with_custom_git_reader(self) -> None:
        """Test factory with custom git metrics reader."""
        custom_reader = MockGitMetricsReader()
        integration = create_session_buddy_integration(
            git_metrics_reader=custom_reader,
        )

        assert integration.git_reader is custom_reader

    def test_create_integration_with_custom_paths(self) -> None:
        """Test factory with custom database paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "workflow.db"
            insights_path = Path(tmpdir) / "insights.db"

            # Note: These databases won't be created until first use
            integration = create_session_buddy_integration(
                db_path=str(db_path),
                insights_db_path=str(insights_path),
            )

            # Integration should be created successfully
            assert integration is not None
            assert integration.session_buddy is not None
            assert integration.storage is not None


class TestProtocolCompliance:
    """Tests for protocol compliance and type safety."""

    def test_no_op_git_reader_compliance(self) -> None:
        """Test NoOpGitMetricsReader complies with protocol."""
        reader = NoOpGitMetricsReader()

        # Should not raise
        metrics = reader.get_metrics("/test/path")
        assert metrics == []

        latest = reader.get_latest_metrics("/test/path")
        assert latest == {}

    async def test_no_op_session_buddy_client_compliance(self) -> None:
        """Test NoOpSessionBuddyClient complies with protocol."""
        client = NoOpSessionBuddyClient()

        # Should not raise
        sessions = await client.get_session_metrics()
        assert sessions == []

        workflow = await client.get_workflow_metrics()
        assert workflow is None

    async def test_no_op_correlation_storage_compliance(self) -> None:
        """Test NoOpCorrelationStorage complies with protocol."""
        storage = NoOpCorrelationStorage()

        insight = CorrelationInsight(
            correlation_type="test",
            correlation_coefficient=0.5,
            strength="moderate",
            direction="positive",
            description="Test",
            confidence=0.7,
            sample_size=10,
        )

        # Should not raise
        await storage.store_insight(insight)

        insights = await storage.get_insights()
        assert insights == []


@pytest.mark.integration
class TestSessionBuddyDirectClient:
    """Integration tests for SessionBuddyDirectClient."""

    async def test_session_buddy_direct_client_no_database(self) -> None:
        """Test client handles missing database gracefully."""
        client = SessionBuddyDirectClient(
            db_path="/nonexistent/path/workflow_metrics.db"
        )

        # Should not raise, but return empty results
        sessions = await client.get_session_metrics(session_id="test")

        assert sessions == []

    async def test_session_buddy_direct_client_with_mock_database(self) -> None:
        """Test client with actual database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_workflow.db"

            # Create mock database with session data
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE session_metrics (
                    session_id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    ended_at TIMESTAMP,
                    duration_minutes FLOAT,
                    checkpoint_count INTEGER DEFAULT 0,
                    commit_count INTEGER DEFAULT 0,
                    quality_start FLOAT DEFAULT 0,
                    quality_end FLOAT DEFAULT 0,
                    quality_delta FLOAT DEFAULT 0,
                    avg_quality FLOAT DEFAULT 0,
                    files_modified INTEGER DEFAULT 0,
                    tools_used TEXT[],
                    primary_language TEXT,
                    time_of_day TEXT
                )
            """)

            # Insert test data
            now = datetime.now(UTC)
            conn.execute(
                """
                INSERT INTO session_metrics (
                    session_id, project_path, started_at, ended_at, duration_minutes,
                    checkpoint_count, commit_count, quality_start, quality_end,
                    quality_delta, avg_quality, files_modified, tools_used,
                    primary_language, time_of_day
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "test-session-1",
                    "/test/project",
                    now.isoformat(),
                    (now + timedelta(hours=1)).isoformat(),
                    60.0,
                    5,
                    10,
                    80.0,
                    85.0,
                    5.0,
                    82.5,
                    15,
                    '["ruff", "pytest"]',
                    "Python",
                    "morning",
                ),
            )
            conn.commit()
            conn.close()

            # Test client
            client = SessionBuddyDirectClient(db_path=str(db_path))
            sessions = await client.get_session_metrics(session_id="test-session-1")

            assert len(sessions) == 1
            assert sessions[0]["session_id"] == "test-session-1"
            assert sessions[0]["project_path"] == "/test/project"
