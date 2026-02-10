"""
Unit tests for AgentPerformanceTracker.

Tests thread-safety, persistence, metrics calculation, and reporting features.
"""

import json
import tempfile
from pathlib import Path

import pytest

from crackerjack.agents.performance_tracker import (
    AgentAttempt,
    AgentMetrics,
    AgentPerformanceTracker,
    METRICS_FILE,
)


@pytest.fixture
def temp_metrics_file():
    """Create temporary metrics file path (file not created)."""
    # Use mkstemp to get a path without creating the file
    fd, temp_path = tempfile.mkstemp(suffix=".json")
    # Close the file descriptor and delete the file
    import os
    os.close(fd)
    os.unlink(temp_path)

    yield Path(temp_path)

    # Cleanup
    if Path(temp_path).exists():
        Path(temp_path).unlink()


@pytest.fixture
def tracker(temp_metrics_file):
    """Create tracker with temporary file."""
    return AgentPerformanceTracker(metrics_file=temp_metrics_file)


class TestAgentAttempt:
    """Test AgentAttempt dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        attempt = AgentAttempt(
            timestamp="2025-01-09T12:00:00",
            agent_name="RefactoringAgent",
            model_name="claude-sonnet-4-5-20250929",
            issue_type="complexity",
            success=True,
            confidence=0.85,
            time_seconds=2.3,
        )

        result = attempt.to_dict()

        assert result["timestamp"] == "2025-01-09T12:00:00"
        assert result["agent_name"] == "RefactoringAgent"
        assert result["success"] is True
        assert result["confidence"] == 0.85
        assert result["time_seconds"] == 2.3


class TestAgentMetrics:
    """Test AgentMetrics dataclass."""

    def test_initial_state(self):
        """Test initial metrics state."""
        metrics = AgentMetrics(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
        )

        assert metrics.total_attempts == 0
        assert metrics.successful_fixes == 0
        assert metrics.failed_fixes == 0
        assert metrics.avg_confidence == 0.0
        assert metrics.avg_time_seconds == 0.0
        assert metrics.recent_results == []

    def test_add_attempt_success(self):
        """Test recording successful attempt."""
        metrics = AgentMetrics(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
        )

        metrics.add_attempt(success=True, confidence=0.8, time_seconds=1.5)

        assert metrics.total_attempts == 1
        assert metrics.successful_fixes == 1
        assert metrics.failed_fixes == 0
        assert metrics.avg_confidence == 0.8
        assert metrics.avg_time_seconds == 1.5

    def test_add_attempt_failure(self):
        """Test recording failed attempt."""
        metrics = AgentMetrics(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
        )

        metrics.add_attempt(success=False, confidence=0.3, time_seconds=0.5)

        assert metrics.total_attempts == 1
        assert metrics.successful_fixes == 0
        assert metrics.failed_fixes == 1
        assert metrics.avg_confidence == 0.3
        assert metrics.avg_time_seconds == 0.5

    def test_multiple_attempts_averaging(self):
        """Test averaging across multiple attempts."""
        metrics = AgentMetrics(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
        )

        # Add multiple attempts
        metrics.add_attempt(success=True, confidence=0.8, time_seconds=2.0)
        metrics.add_attempt(success=True, confidence=0.6, time_seconds=4.0)
        metrics.add_attempt(success=False, confidence=0.4, time_seconds=1.0)

        assert metrics.total_attempts == 3
        assert metrics.successful_fixes == 2
        assert metrics.failed_fixes == 1
        assert metrics.avg_confidence == pytest.approx(0.6, rel=1e-3)  # (0.8+0.6+0.4)/3
        assert metrics.avg_time_seconds == pytest.approx(2.333, rel=1e-3)  # (2+4+1)/3

    def test_get_success_rate(self):
        """Test success rate calculation."""
        metrics = AgentMetrics(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
        )

        assert metrics.get_success_rate() == 0.0

        metrics.add_attempt(success=True, confidence=0.8, time_seconds=1.0)
        assert metrics.get_success_rate() == 100.0

        metrics.add_attempt(success=False, confidence=0.5, time_seconds=1.0)
        assert metrics.get_success_rate() == 50.0

    def test_add_recent_results(self):
        """Test adding recent results with max limit."""
        metrics = AgentMetrics(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
        )

        # Add more than MAX_RECENT_RESULTS
        for i in range(105):
            attempt = AgentAttempt(
                timestamp=f"2025-01-09T{ i:02d}:00:00",
                agent_name="TestAgent",
                model_name="test-model",
                issue_type="test-type",
                success=True,
                confidence=0.8,
                time_seconds=1.0,
            )
            metrics.add_recent_result(attempt)

        assert len(metrics.recent_results) == 100

    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = AgentMetrics(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
        )
        metrics.add_attempt(success=True, confidence=0.8, time_seconds=1.5)

        result = metrics.to_dict()

        assert result["agent_name"] == "TestAgent"
        assert result["total_attempts"] == 1
        assert result["avg_confidence"] == 0.8
        assert isinstance(result["recent_results"], list)

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "agent_name": "TestAgent",
            "model_name": "test-model",
            "issue_type": "test-type",
            "total_attempts": 5,
            "successful_fixes": 3,
            "failed_fixes": 2,
            "avg_confidence": 0.75,
            "avg_time_seconds": 2.5,
            "recent_results": [],
        }

        metrics = AgentMetrics.from_dict(data)

        assert metrics.agent_name == "TestAgent"
        assert metrics.total_attempts == 5
        assert metrics.get_success_rate() == 60.0


class TestAgentPerformanceTracker:
    """Test AgentPerformanceTracker class."""

    def test_initialization(self, tracker):
        """Test tracker initialization."""
        assert tracker.get_metric_count() == 0
        # Metrics file created on first save, not initialization
        assert tracker.metrics_file.exists() is False

    def test_record_attempt(self, tracker):
        """Test recording a single attempt."""
        tracker.record_attempt(
            agent_name="RefactoringAgent",
            model_name="claude-sonnet-4-5-20250929",
            issue_type="complexity",
            success=True,
            confidence=0.85,
            time_seconds=2.3,
        )

        assert tracker.get_metric_count() == 1

    def test_record_multiple_attempts_same_key(self, tracker):
        """Test recording multiple attempts for same agent/model/issue."""
        tracker.record_attempt(
            agent_name="RefactoringAgent",
            model_name="claude-sonnet-4-5-20250929",
            issue_type="complexity",
            success=True,
            confidence=0.8,
            time_seconds=2.0,
        )

        tracker.record_attempt(
            agent_name="RefactoringAgent",
            model_name="claude-sonnet-4-5-20250929",
            issue_type="complexity",
            success=False,
            confidence=0.5,
            time_seconds=1.0,
        )

        assert tracker.get_metric_count() == 1  # Same key

    def test_record_multiple_attempts_different_keys(self, tracker):
        """Test recording attempts for different agent/model/issue combos."""
        tracker.record_attempt(
            agent_name="RefactoringAgent",
            model_name="claude-sonnet-4-5-20250929",
            issue_type="complexity",
            success=True,
            confidence=0.8,
            time_seconds=2.0,
        )

        tracker.record_attempt(
            agent_name="SecurityAgent",
            model_name="claude-sonnet-4-5-20250929",
            issue_type="security",
            success=True,
            confidence=0.9,
            time_seconds=1.5,
        )

        assert tracker.get_metric_count() == 2

    def test_get_success_rate_specific(self, tracker):
        """Test getting success rate for specific metric."""
        tracker.record_attempt(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
            success=True,
            confidence=0.8,
            time_seconds=1.0,
        )

        tracker.record_attempt(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
            success=False,
            confidence=0.5,
            time_seconds=1.0,
        )

        rate = tracker.get_success_rate(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
        )

        assert rate == 50.0

    def test_get_success_rate_no_data(self, tracker):
        """Test getting success rate when no data exists."""
        rate = tracker.get_success_rate(
            agent_name="NonExistent",
            model_name="test-model",
            issue_type="test-type",
        )

        assert rate == 0.0

    def test_get_success_rate_by_issue_type(self, tracker):
        """Test getting success rates grouped by issue type."""
        tracker.record_attempt(
            agent_name="Agent1",
            model_name="model1",
            issue_type="type1",
            success=True,
            confidence=0.8,
            time_seconds=1.0,
        )

        tracker.record_attempt(
            agent_name="Agent2",
            model_name="model1",
            issue_type="type1",
            success=False,
            confidence=0.5,
            time_seconds=1.0,
        )

        rates = tracker.get_success_rate(issue_type="type1")

        assert isinstance(rates, dict)
        assert "model1" in rates
        assert rates["model1"] == 50.0

    def test_get_best_agent_for_issue_type(self, tracker):
        """Test finding best agent for issue type."""
        # Add data for multiple agents
        for i in range(10):
            tracker.record_attempt(
                agent_name="GoodAgent",
                model_name="model1",
                issue_type="complexity",
                success=i < 8,  # 80% success
                confidence=0.8,
                time_seconds=2.0,
            )

        for i in range(10):
            tracker.record_attempt(
                agent_name="BadAgent",
                model_name="model1",
                issue_type="complexity",
                success=i < 4,  # 40% success
                confidence=0.6,
                time_seconds=3.0,
            )

        best = tracker.get_best_agent_for_issue_type("complexity", min_attempts=5)

        assert best is not None
        assert best["agent_name"] == "GoodAgent"
        assert best["success_rate"] == 80.0

    def test_get_best_agent_insufficient_data(self, tracker):
        """Test best agent with insufficient attempts."""
        tracker.record_attempt(
            agent_name="TestAgent",
            model_name="model1",
            issue_type="complexity",
            success=True,
            confidence=0.8,
            time_seconds=1.0,
        )

        best = tracker.get_best_agent_for_issue_type("complexity", min_attempts=5)

        assert best is None

    def test_get_model_comparison(self, tracker):
        """Test comparing models."""
        # Add data for model1
        for i in range(10):
            tracker.record_attempt(
                agent_name="Agent",
                model_name="model1",
                issue_type="complexity",
                success=i < 8,  # 80%
                confidence=0.8,
                time_seconds=2.0,
            )

        # Add data for model2
        for i in range(10):
            tracker.record_attempt(
                agent_name="Agent",
                model_name="model2",
                issue_type="complexity",
                success=i < 5,  # 50%
                confidence=0.6,
                time_seconds=3.0,
            )

        comparison = tracker.get_model_comparison(issue_type="complexity")

        assert "model1" in comparison
        assert "model2" in comparison
        assert comparison["model1"]["avg_success_rate"] > comparison["model2"][
            "avg_success_rate"
        ]

    @pytest.mark.timeout(700)  # Allow 700 seconds for this comprehensive test
    def test_generate_performance_report(self, tracker):
        """Test comprehensive performance report."""
        # Add sample data
        tracker.record_attempt(
            agent_name="Agent1",
            model_name="model1",
            issue_type="type1",
            success=True,
            confidence=0.8,
            time_seconds=1.0,
        )

        tracker.record_attempt(
            agent_name="Agent2",
            model_name="model1",
            issue_type="type2",
            success=False,
            confidence=0.5,
            time_seconds=2.0,
        )

        report = tracker.generate_performance_report()

        assert "summary" in report
        assert "by_agent" in report
        assert "by_issue_type" in report
        assert "by_model" in report
        assert "recommendations" in report
        assert report["summary"]["total_attempts"] == 2
        assert report["summary"]["total_agents"] == 2
        assert "generated_at" in report["summary"]
        assert isinstance(report["by_agent"], dict)
        assert isinstance(report["by_issue_type"], dict)

    def test_persistence_save_and_load(self, temp_metrics_file):
        """Test saving and loading metrics from disk."""
        # Create tracker and add data
        tracker1 = AgentPerformanceTracker(metrics_file=temp_metrics_file)

        tracker1.record_attempt(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
            success=True,
            confidence=0.8,
            time_seconds=1.0,
        )

        assert temp_metrics_file.exists()

        # Create new tracker instance (should load from disk)
        tracker2 = AgentPerformanceTracker(metrics_file=temp_metrics_file)

        assert tracker2.get_metric_count() == 1

        # Verify data integrity
        rate = tracker2.get_success_rate(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
        )

        assert rate == 100.0

    def test_persistence_corrupted_file(self, temp_metrics_file):
        """Test handling of corrupted metrics file."""
        # Write invalid JSON
        temp_metrics_file.write_text("invalid json {{{")

        # Should handle gracefully
        tracker = AgentPerformanceTracker(metrics_file=temp_metrics_file)

        assert tracker.get_metric_count() == 0

    def test_reset_metrics(self, tracker):
        """Test resetting all metrics."""
        tracker.record_attempt(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
            success=True,
            confidence=0.8,
            time_seconds=1.0,
        )

        assert tracker.get_metric_count() == 1
        assert tracker.metrics_file.exists()

        tracker.reset_metrics()

        assert tracker.get_metric_count() == 0
        assert tracker.metrics_file.exists() is False

    def test_get_metric_count(self, tracker):
        """Test getting metric count."""
        assert tracker.get_metric_count() == 0

        tracker.record_attempt(
            agent_name="Agent1",
            model_name="model1",
            issue_type="type1",
            success=True,
            confidence=0.8,
            time_seconds=1.0,
        )

        assert tracker.get_metric_count() == 1

    def test_get_raw_metrics(self, tracker):
        """Test getting raw metrics data."""
        tracker.record_attempt(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
            success=True,
            confidence=0.8,
            time_seconds=1.0,
        )

        raw = tracker.get_raw_metrics()

        assert isinstance(raw, dict)
        assert len(raw) == 1

        key = list(raw.keys())[0]
        assert raw[key]["agent_name"] == "TestAgent"

    def test_thread_safety(self, tracker):
        """Test concurrent recording from multiple threads."""
        import threading

        def record_attempts(thread_id: int):
            for i in range(50):
                tracker.record_attempt(
                    agent_name=f"Agent{thread_id % 3}",
                    model_name=f"model{thread_id % 2}",
                    issue_type=f"type{i % 5}",
                    success=i % 2 == 0,
                    confidence=0.5 + (i % 5) * 0.1,
                    time_seconds=1.0 + i * 0.1,
                )

        threads = [threading.Thread(target=record_attempts, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All threads should have completed without errors
        assert tracker.get_metric_count() > 0

    def test_atomic_write(self, temp_metrics_file):
        """Test that metrics file writes are atomic."""
        tracker = AgentPerformanceTracker(metrics_file=temp_metrics_file)

        # Record some data
        tracker.record_attempt(
            agent_name="TestAgent",
            model_name="test-model",
            issue_type="test-type",
            success=True,
            confidence=0.8,
            time_seconds=1.0,
        )

        # Verify no temp file left behind
        temp_file = temp_metrics_file.with_suffix(".tmp")
        assert temp_file.exists() is False

        # Verify main file exists and is valid JSON
        assert temp_metrics_file.exists()
        data = json.loads(temp_metrics_file.read_text())
        assert "metrics" in data
