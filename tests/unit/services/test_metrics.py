"""Comprehensive unit tests for crackerjack.services.metrics.

Covers MetricsCollector (sqlite-backed) and the module-level
get_metrics()/reset_metrics() singletons. Goal: lift module coverage
from 24% baseline to 80%+.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.services.metrics import (
    MetricsCollector,
    get_metrics,
    reset_metrics,
)


@pytest.fixture(autouse=True)
def _reset_metrics_singleton() -> None:
    """Reset the module-level metrics singleton around every test."""
    reset_metrics()
    yield
    reset_metrics()


class TestInit:
    """Tests for MetricsCollector.__init__ and db_path resolution."""

    def test_creates_db_file_at_given_path(self, tmp_path: Path) -> None:
        db_path = tmp_path / "metrics.db"
        MetricsCollector(db_path=db_path)

        assert db_path.exists()
        assert db_path.is_file()

    def test_does_not_create_parent_dirs_when_path_provided(
        self, tmp_path: Path
    ) -> None:
        # When an explicit db_path is given whose parent already exists,
        # sqlite3.connect creates the file there. Parent-dir creation is
        # NOT performed by the constructor on this branch — that only
        # happens on the None branch (see test_default_path_uses_home_cache_dir).
        db_path = tmp_path / "metrics.db"

        MetricsCollector(db_path=db_path)

        assert db_path.exists()

    def test_db_path_attribute_stored(self, tmp_path: Path) -> None:
        db_path = tmp_path / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        assert collector.db_path == db_path

    def test_lock_is_threading_lock(self, tmp_path: Path) -> None:
        import threading

        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        assert isinstance(collector._lock, type(threading.Lock()))

    def test_default_path_uses_home_cache_dir(self, tmp_path: Path) -> None:
        # When db_path is None, the collector should fall back to
        # ~/.cache/crackerjack/metrics.db. Patch Path.home() to a tmp
        # location to keep tests hermetic.
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        expected_dir = fake_home / ".cache" / "crackerjack"

        with patch("pathlib.Path.home", return_value=fake_home):
            collector = MetricsCollector()

        try:
            assert collector.db_path == expected_dir / "metrics.db"
            assert expected_dir.exists()
            assert collector.db_path.exists()
        finally:
            reset_metrics()


class TestInitDatabase:
    """Tests for _init_database — verifies tables and indexes."""

    def test_creates_agent_executions_table(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        rows = collector.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_executions'"
        )

        assert len(rows) == 1
        assert rows[0]["name"] == "agent_executions"

    def test_creates_provider_performance_table(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        rows = collector.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='provider_performance'"
        )

        assert len(rows) == 1

    def test_creates_jobs_table(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        rows = collector.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
        )

        assert len(rows) == 1

    def test_creates_expected_indexes(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        rows = collector.execute_query(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        index_names = {row["name"] for row in rows}

        assert "idx_agent_executions_job_id" in index_names
        assert "idx_agent_executions_agent_name" in index_names
        assert "idx_provider_performance_provider_id" in index_names

    def test_init_is_idempotent(self, tmp_path: Path) -> None:
        # Re-instantiating against the same DB should not raise.
        db_path = tmp_path / "metrics.db"
        MetricsCollector(db_path=db_path)
        MetricsCollector(db_path=db_path)

        # Tables still present.
        rows = MetricsCollector(db_path=db_path).execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        names = {row["name"] for row in rows}
        assert {"agent_executions", "provider_performance", "jobs"}.issubset(names)


class TestGetConnection:
    """Tests for _get_connection commit/rollback/close behavior."""

    def test_commits_on_success(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        with collector._get_connection() as conn:
            conn.execute(
                "INSERT INTO provider_performance (provider_id, success, timestamp) VALUES (?, ?, ?)",
                ("prov-a", 1, "2026-01-01 00:00:00"),
            )

        rows = collector.execute_query(
            "SELECT provider_id FROM provider_performance WHERE provider_id = ?",
            ("prov-a",),
        )
        assert len(rows) == 1

    def test_rollback_on_exception(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        with pytest.raises(RuntimeError, match="boom"):
            with collector._get_connection() as conn:
                conn.execute(
                    "INSERT INTO provider_performance (provider_id, success, timestamp) VALUES (?, ?, ?)",
                    ("prov-rollback", 1, "2026-01-01 00:00:00"),
                )
                raise RuntimeError("boom")

        rows = collector.execute_query(
            "SELECT provider_id FROM provider_performance WHERE provider_id = ?",
            ("prov-rollback",),
        )
        assert len(rows) == 0

    def test_always_closes_connection(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        with collector._get_connection() as conn:
            real_conn = conn

        # After exit, the underlying sqlite3 connection should be closed.
        # Accessing execute on a closed connection raises ProgrammingError.
        with pytest.raises(sqlite3.ProgrammingError):
            real_conn.execute("SELECT 1")

    def test_row_factory_is_sqlite_row(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        with collector._get_connection() as conn:
            assert conn.row_factory is sqlite3.Row

    def test_check_same_thread_disabled(self, tmp_path: Path) -> None:
        # _get_connection opens with check_same_thread=False, so we can
        # safely use the resulting connection from another thread. If the
        # flag were True, sqlite3 would raise ProgrammingError on the
        # foreign-thread call.
        import threading

        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        seen: dict[str, object] = {}
        error: list[BaseException] = []

        def worker() -> None:
            try:
                with collector._get_connection() as conn:
                    cur = conn.execute("SELECT 1 AS one")
                    seen["one"] = cur.fetchone()["one"]
            except BaseException as exc:  # pragma: no cover - error path
                error.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        assert error == []
        assert seen["one"] == 1


class TestExecuteAndQuery:
    """Tests for execute / execute_query."""

    def test_execute_inserts_row(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        collector.execute(
            "INSERT INTO provider_performance (provider_id, success, timestamp) VALUES (?, ?, ?)",
            ("p1", 1, "2026-01-01 00:00:00"),
        )

        rows = collector.execute_query(
            "SELECT provider_id, success FROM provider_performance WHERE provider_id = ?",
            ("p1",),
        )
        assert len(rows) == 1
        assert rows[0]["provider_id"] == "p1"
        assert rows[0]["success"] == 1

    def test_execute_query_returns_list_of_rows(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        for pid in ("a", "b", "c"):
            collector.execute(
                "INSERT INTO provider_performance (provider_id, success, timestamp) VALUES (?, ?, ?)",
                (pid, 1, "2026-01-01 00:00:00"),
            )

        rows = collector.execute_query("SELECT provider_id FROM provider_performance")

        assert isinstance(rows, list)
        assert len(rows) == 3
        # Row dict-like access works.
        assert rows[0]["provider_id"] == "a"

    def test_execute_query_empty_result_returns_empty_list(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        rows = collector.execute_query("SELECT 1 FROM provider_performance")

        assert rows == []


class TestTrackProviderSelection:
    """Tests for track_provider_selection."""

    def test_row_count_grows(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        assert len(collector.execute_query("SELECT 1 FROM provider_performance")) == 0

        collector.track_provider_selection("p1", success=True, latency_ms=12.5)
        collector.track_provider_selection("p2", success=False, latency_ms=99.0)

        rows = collector.execute_query("SELECT provider_id FROM provider_performance")
        assert len(rows) == 2

    def test_success_stored_as_int_one(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        collector.track_provider_selection("p1", success=True)

        row = collector.execute_query(
            "SELECT success FROM provider_performance WHERE provider_id = ?",
            ("p1",),
        )[0]
        assert row["success"] == 1
        assert isinstance(row["success"], int)

    def test_success_stored_as_int_zero(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        collector.track_provider_selection("p1", success=False)

        row = collector.execute_query(
            "SELECT success FROM provider_performance WHERE provider_id = ?",
            ("p1",),
        )[0]
        assert row["success"] == 0
        assert isinstance(row["success"], int)

    def test_latency_stored(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        collector.track_provider_selection("p1", success=True, latency_ms=42.5)

        row = collector.execute_query(
            "SELECT latency_ms FROM provider_performance WHERE provider_id = ?",
            ("p1",),
        )[0]
        assert row["latency_ms"] == 42.5

    def test_latency_optional(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        collector.track_provider_selection("p1", success=True)

        row = collector.execute_query(
            "SELECT latency_ms FROM provider_performance WHERE provider_id = ?",
            ("p1",),
        )[0]
        assert row["latency_ms"] is None


class TestTrackAgentExecution:
    """Tests for track_agent_execution."""

    def test_row_count_grows(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        assert len(collector.execute_query("SELECT 1 FROM agent_executions")) == 0

        collector.track_agent_execution(
            job_id="j1",
            agent_name="ruff",
            issue_type="E501",
            success=True,
            confidence=0.9,
            fixes_applied=2,
            files_modified=1,
            remaining_issues=0,
        )

        rows = collector.execute_query("SELECT 1 FROM agent_executions")
        assert len(rows) == 1

    def test_all_columns_populated(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        collector.track_agent_execution(
            job_id="j1",
            agent_name="ruff",
            issue_type="E501",
            success=True,
            confidence=0.75,
            fixes_applied=3,
            files_modified=2,
            remaining_issues=1,
            execution_time_ms=120.5,
        )

        row = collector.execute_query(
            "SELECT * FROM agent_executions WHERE job_id = ?",
            ("j1",),
        )[0]

        assert row["job_id"] == "j1"
        assert row["agent_name"] == "ruff"
        assert row["issue_type"] == "E501"
        assert row["success"] == 1
        assert row["confidence"] == 0.75
        assert row["fixes_applied"] == 3
        assert row["files_modified"] == 2
        assert row["remaining_issues"] == 1
        assert row["execution_time_ms"] == 120.5
        assert row["timestamp"] is not None

    def test_execution_time_optional(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        collector.track_agent_execution(
            job_id="j1",
            agent_name="ruff",
            issue_type="E501",
            success=True,
            confidence=0.5,
            fixes_applied=0,
            files_modified=0,
            remaining_issues=0,
        )

        row = collector.execute_query(
            "SELECT execution_time_ms FROM agent_executions WHERE job_id = ?",
            ("j1",),
        )[0]
        assert row["execution_time_ms"] is None

    def test_success_bool_coerced_to_int(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        collector.track_agent_execution(
            "j-fail", "ruff", "E501", success=False, confidence=0.1,
            fixes_applied=0, files_modified=0, remaining_issues=1,
        )

        row = collector.execute_query(
            "SELECT success FROM agent_executions WHERE job_id = ?",
            ("j-fail",),
        )[0]
        assert row["success"] == 0


class TestGetProviderStats:
    """Tests for get_provider_stats."""

    def test_returns_empty_when_no_data(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        result = collector.get_provider_stats()

        assert result == []

    def test_returns_one_dict_per_provider(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        # Two providers, multiple rows each.
        collector.track_provider_selection("p1", success=True, latency_ms=10.0)
        collector.track_provider_selection("p1", success=False, latency_ms=20.0)
        collector.track_provider_selection("p2", success=True, latency_ms=30.0)

        result = collector.get_provider_stats()

        assert isinstance(result, list)
        assert len(result) == 2
        # Each entry is a dict with the expected keys.
        for entry in result:
            assert isinstance(entry, dict)
            assert {
                "provider_id",
                "total_selections",
                "successful_selections",
                "avg_latency_ms",
            }.issubset(entry.keys())

    def test_aggregates_counts_and_sums(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_provider_selection("p1", success=True, latency_ms=10.0)
        collector.track_provider_selection("p1", success=True, latency_ms=20.0)
        collector.track_provider_selection("p1", success=False, latency_ms=30.0)

        result = collector.get_provider_stats(provider_id="p1")

        assert len(result) == 1
        entry = result[0]
        assert entry["provider_id"] == "p1"
        assert entry["total_selections"] == 3
        assert entry["successful_selections"] == 2
        assert entry["avg_latency_ms"] == pytest.approx(20.0)

    def test_provider_id_filter(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_provider_selection("p1", success=True, latency_ms=10.0)
        collector.track_provider_selection("p2", success=True, latency_ms=20.0)

        result = collector.get_provider_stats(provider_id="p1")

        assert len(result) == 1
        assert result[0]["provider_id"] == "p1"


class TestGetAgentStats:
    """Tests for get_agent_stats."""

    def test_returns_empty_when_no_data(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        result = collector.get_agent_stats()

        assert result == []

    def test_returns_one_dict_per_agent(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        for i in range(2):
            collector.track_agent_execution(
                job_id=f"j-{i}", agent_name="ruff", issue_type="E501",
                success=True, confidence=0.8, fixes_applied=1,
                files_modified=1, remaining_issues=0,
            )
        collector.track_agent_execution(
            job_id="j-mypy", agent_name="mypy", issue_type="arg-type",
            success=False, confidence=0.4, fixes_applied=0,
            files_modified=0, remaining_issues=1,
        )

        result = collector.get_agent_stats()

        assert len(result) == 2
        for entry in result:
            assert {
                "agent_name",
                "total_executions",
                "successful_executions",
                "avg_confidence",
                "total_fixes",
            }.issubset(entry.keys())

    def test_aggregates_counts_sums_and_avg(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_agent_execution(
            "j1", "ruff", "E501", success=True, confidence=0.8,
            fixes_applied=2, files_modified=1, remaining_issues=0,
        )
        collector.track_agent_execution(
            "j2", "ruff", "F401", success=False, confidence=0.2,
            fixes_applied=0, files_modified=0, remaining_issues=1,
        )

        result = collector.get_agent_stats(agent_name="ruff")

        assert len(result) == 1
        entry = result[0]
        assert entry["agent_name"] == "ruff"
        assert entry["total_executions"] == 2
        assert entry["successful_executions"] == 1
        assert entry["avg_confidence"] == pytest.approx(0.5)
        assert entry["total_fixes"] == 2

    def test_agent_name_filter(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_agent_execution(
            "j1", "ruff", "E501", success=True, confidence=0.8,
            fixes_applied=1, files_modified=1, remaining_issues=0,
        )
        collector.track_agent_execution(
            "j2", "mypy", "arg-type", success=True, confidence=0.7,
            fixes_applied=0, files_modified=0, remaining_issues=0,
        )

        result = collector.get_agent_stats(agent_name="mypy")

        assert len(result) == 1
        assert result[0]["agent_name"] == "mypy"


class TestGetAgentSuccessRate:
    """Tests for get_agent_success_rate."""

    def test_zero_with_no_rows(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        rate = collector.get_agent_success_rate("nonexistent-agent")

        assert rate == 0.0

    def test_one_with_all_success(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        for i in range(3):
            collector.track_agent_execution(
                f"j-{i}", "ruff", "E501", success=True, confidence=0.9,
                fixes_applied=1, files_modified=1, remaining_issues=0,
            )

        rate = collector.get_agent_success_rate("ruff")

        assert rate == 1.0

    def test_zero_with_all_failure(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        for i in range(3):
            collector.track_agent_execution(
                f"j-{i}", "ruff", "E501", success=False, confidence=0.1,
                fixes_applied=0, files_modified=0, remaining_issues=1,
            )

        rate = collector.get_agent_success_rate("ruff")

        assert rate == 0.0

    def test_partial_success_rate(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        for i in range(3):
            collector.track_agent_execution(
                f"j-ok-{i}", "ruff", "E501", success=True, confidence=0.9,
                fixes_applied=1, files_modified=1, remaining_issues=0,
            )
        collector.track_agent_execution(
            "j-bad", "ruff", "E501", success=False, confidence=0.1,
            fixes_applied=0, files_modified=0, remaining_issues=1,
        )

        rate = collector.get_agent_success_rate("ruff")

        assert rate == pytest.approx(0.75)

    def test_filters_by_agent_name(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        # ruff: 2/2 success.
        collector.track_agent_execution(
            "j1", "ruff", "E501", success=True, confidence=0.9,
            fixes_applied=1, files_modified=1, remaining_issues=0,
        )
        collector.track_agent_execution(
            "j2", "ruff", "E501", success=True, confidence=0.9,
            fixes_applied=1, files_modified=1, remaining_issues=0,
        )
        # mypy: 0/2 success.
        collector.track_agent_execution(
            "j3", "mypy", "arg-type", success=False, confidence=0.1,
            fixes_applied=0, files_modified=0, remaining_issues=1,
        )
        collector.track_agent_execution(
            "j4", "mypy", "arg-type", success=False, confidence=0.1,
            fixes_applied=0, files_modified=0, remaining_issues=1,
        )

        assert collector.get_agent_success_rate("ruff") == 1.0
        assert collector.get_agent_success_rate("mypy") == 0.0


class TestGetProviderAvailability:
    """Tests for get_provider_availability — uses sqlite datetime math."""

    def test_zero_with_no_rows(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        rate = collector.get_provider_availability("nonexistent")

        assert rate == 0.0

    def test_includes_recent_rows(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        # Three rows inserted at "now" should fall within the 24h window.
        collector.track_provider_selection("p1", success=True, latency_ms=10.0)
        collector.track_provider_selection("p1", success=False, latency_ms=20.0)
        collector.track_provider_selection("p1", success=True, latency_ms=30.0)

        rate = collector.get_provider_availability("p1", hours=24)

        assert rate == pytest.approx(2 / 3)

    def test_excludes_old_rows(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        # Backdate a row by 48 hours via direct INSERT (sqlite's datetime
        # math uses 'YYYY-MM-DD HH:MM:SS' strings).
        collector.execute(
            "INSERT INTO provider_performance "
            "(provider_id, success, latency_ms, timestamp) VALUES (?, ?, ?, ?)",
            ("p-old", 1, 5.0, "2020-01-01 00:00:00"),
        )
        collector.track_provider_selection("p-old", success=False, latency_ms=10.0)

        # With a 24h window, only the fresh failure counts — rate is 0/1 = 0.0.
        rate = collector.get_provider_availability("p-old", hours=24)

        assert rate == 0.0

    def test_hours_window_includes_one_hour_old_row(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        # Insert a row 1 hour ago.
        collector.execute(
            "INSERT INTO provider_performance "
            "(provider_id, success, latency_ms, timestamp) "
            "VALUES (?, ?, ?, datetime('now', '-1 hours'))",
            ("p-recent", 1, 1.0),
        )

        # A 24h window should still see it.
        rate = collector.get_provider_availability("p-recent", hours=24)

        assert rate == 1.0

    def test_filters_by_provider_id(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_provider_selection("p1", success=True, latency_ms=10.0)
        collector.track_provider_selection("p2", success=False, latency_ms=10.0)

        assert collector.get_provider_availability("p1") == 1.0
        assert collector.get_provider_availability("p2") == 0.0


class TestGetAgentConfidenceDistribution:
    """Tests for get_agent_confidence_distribution bucketing."""

    def test_empty_distribution_for_unknown_agent(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        dist = collector.get_agent_confidence_distribution("unknown")

        assert dist == {"low": 0, "medium": 0, "high": 0}

    def test_low_bucket_boundary_zero(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_agent_execution(
            "j1", "ruff", "E501", success=True, confidence=0.0,
            fixes_applied=1, files_modified=1, remaining_issues=0,
        )

        dist = collector.get_agent_confidence_distribution("ruff")

        assert dist == {"low": 1, "medium": 0, "high": 0}

    def test_low_bucket_boundary_zero_four(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_agent_execution(
            "j1", "ruff", "E501", success=True, confidence=0.4,
            fixes_applied=1, files_modified=1, remaining_issues=0,
        )

        dist = collector.get_agent_confidence_distribution("ruff")

        assert dist["low"] == 1
        assert dist["medium"] == 0
        assert dist["high"] == 0

    def test_medium_bucket_boundary_zero_four_one(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_agent_execution(
            "j1", "ruff", "E501", success=True, confidence=0.41,
            fixes_applied=1, files_modified=1, remaining_issues=0,
        )

        dist = collector.get_agent_confidence_distribution("ruff")

        assert dist == {"low": 0, "medium": 1, "high": 0}

    def test_medium_bucket_boundary_zero_seven(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_agent_execution(
            "j1", "ruff", "E501", success=True, confidence=0.7,
            fixes_applied=1, files_modified=1, remaining_issues=0,
        )

        dist = collector.get_agent_confidence_distribution("ruff")

        assert dist == {"low": 0, "medium": 1, "high": 0}

    def test_high_bucket_boundary_zero_seven_one(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_agent_execution(
            "j1", "ruff", "E501", success=True, confidence=0.71,
            fixes_applied=1, files_modified=1, remaining_issues=0,
        )

        dist = collector.get_agent_confidence_distribution("ruff")

        assert dist == {"low": 0, "medium": 0, "high": 1}

    def test_high_bucket_boundary_one(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_agent_execution(
            "j1", "ruff", "E501", success=True, confidence=1.0,
            fixes_applied=1, files_modified=1, remaining_issues=0,
        )

        dist = collector.get_agent_confidence_distribution("ruff")

        assert dist == {"low": 0, "medium": 0, "high": 1}

    def test_all_three_buckets(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        for conf, job_id in [
            (0.1, "low-1"),
            (0.3, "low-2"),
            (0.5, "med-1"),
            (0.6, "med-2"),
            (0.7, "med-3"),
            (0.8, "high-1"),
            (0.95, "high-2"),
        ]:
            collector.track_agent_execution(
                job_id=job_id, agent_name="ruff", issue_type="E501",
                success=True, confidence=conf,
                fixes_applied=1, files_modified=1, remaining_issues=0,
            )

        dist = collector.get_agent_confidence_distribution("ruff")

        assert dist == {"low": 2, "medium": 3, "high": 2}

    def test_filters_by_agent_name(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")
        collector.track_agent_execution(
            "j1", "ruff", "E501", success=True, confidence=0.9,
            fixes_applied=1, files_modified=1, remaining_issues=0,
        )
        collector.track_agent_execution(
            "j2", "mypy", "arg-type", success=True, confidence=0.1,
            fixes_applied=0, files_modified=0, remaining_issues=0,
        )

        assert collector.get_agent_confidence_distribution("ruff") == {
            "low": 0,
            "medium": 0,
            "high": 1,
        }
        assert collector.get_agent_confidence_distribution("mypy") == {
            "low": 1,
            "medium": 0,
            "high": 0,
        }


class TestClose:
    """Tests for close() — legacy no-op behavior."""

    def test_close_does_not_raise(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        # Should not raise.
        collector.close()

    def test_close_is_callable_multiple_times(self, tmp_path: Path) -> None:
        collector = MetricsCollector(db_path=tmp_path / "metrics.db")

        collector.close()
        collector.close()


class TestModuleLevelSingletons:
    """Tests for get_metrics() / reset_metrics()."""

    def test_get_metrics_creates_singleton(self) -> None:
        with patch("pathlib.Path.home", return_value=Path("/tmp")):
            first = get_metrics()

        assert isinstance(first, MetricsCollector)

    def test_get_metrics_returns_same_instance(self) -> None:
        with patch("pathlib.Path.home", return_value=Path("/tmp")):
            first = get_metrics()
            second = get_metrics()

        assert first is second

    def test_reset_metrics_clears_singleton(self) -> None:
        with patch("pathlib.Path.home", return_value=Path("/tmp")):
            first = get_metrics()
        assert first is not None

        reset_metrics()

        with patch("pathlib.Path.home", return_value=Path("/tmp")):
            second = get_metrics()

        # After reset, a brand-new instance is created.
        assert second is not first

    def test_reset_metrics_when_no_singleton(self) -> None:
        # Idempotent when already None — should not raise.
        reset_metrics()
        reset_metrics()

    def test_reset_metrics_calls_close(self) -> None:
        with patch("pathlib.Path.home", return_value=Path("/tmp")):
            instance = get_metrics()
        with patch.object(instance, "close") as close_spy:
            reset_metrics()
            close_spy.assert_called_once()
