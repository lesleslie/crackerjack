"""Tests for ai_fix_events module."""

import time

import pytest

from crackerjack.core.ai_fix_events import (
    AIFixEvent,
    AgentDispatched,
    IterationFinished,
    IterationStarted,
    IssueFailed,
    IssueResolved,
    PreflightFinished,
    PreflightStarted,
    RunFinished,
    RunStarted,
)


class TestAIFixEvent:
    """Tests for base AIFixEvent dataclass."""

    def test_creation(self) -> None:
        """Test basic event creation."""
        event = AIFixEvent(run_id="test-123", iteration=1)
        assert event.run_id == "test-123"
        assert event.iteration == 1
        assert event.ts > 0

    def test_is_frozen(self) -> None:
        """Test that AIFixEvent is frozen."""
        event = AIFixEvent(run_id="test-123", iteration=1)
        with pytest.raises(Exception):  # FrozenInstanceError
            event.run_id = "changed"

    def test_default_ts(self) -> None:
        """Test that ts has a default value."""
        before = time.time()
        event = AIFixEvent(run_id="test", iteration=1)
        after = time.time()
        assert before <= event.ts <= after


class TestRunStarted:
    """Tests for RunStarted event."""

    def test_creation(self) -> None:
        """Test RunStarted creation with defaults."""
        event = RunStarted(run_id="test-123", iteration=0)
        assert event.run_id == "test-123"
        assert event.iteration == 0
        assert event.stage == ""
        assert event.initial_issue_count == 0

    def test_creation_with_values(self) -> None:
        """Test RunStarted creation with custom values."""
        event = RunStarted(
            run_id="test-123",
            iteration=1,
            stage="preflight",
            initial_issue_count=10,
        )
        assert event.stage == "preflight"
        assert event.initial_issue_count == 10

    def test_kind_class_var(self) -> None:
        """Test kind class variable."""
        assert RunStarted.kind == "run_started"


class TestIterationStarted:
    """Tests for IterationStarted event."""

    def test_creation(self) -> None:
        """Test IterationStarted creation with defaults."""
        event = IterationStarted(run_id="test-123", iteration=1)
        assert event.strategy == ""
        assert event.issue_count == 0

    def test_creation_with_values(self) -> None:
        """Test IterationStarted creation with custom values."""
        event = IterationStarted(
            run_id="test-123",
            iteration=2,
            strategy="aggressive",
            issue_count=5,
        )
        assert event.strategy == "aggressive"
        assert event.issue_count == 5

    def test_kind_class_var(self) -> None:
        """Test kind class variable."""
        assert IterationStarted.kind == "iteration_started"


class TestAgentDispatched:
    """Tests for AgentDispatched event."""

    def test_creation(self) -> None:
        """Test AgentDispatched creation with defaults."""
        event = AgentDispatched(run_id="test-123", iteration=1)
        assert event.agent == ""
        assert event.action == ""
        assert event.file == ""

    def test_creation_with_values(self) -> None:
        """Test AgentDispatched creation with custom values."""
        event = AgentDispatched(
            run_id="test-123",
            iteration=1,
            agent="refurb",
            action="remove_dead_code",
            file="src/main.py",
        )
        assert event.agent == "refurb"
        assert event.action == "remove_dead_code"
        assert event.file == "src/main.py"

    def test_kind_class_var(self) -> None:
        """Test kind class variable."""
        assert AgentDispatched.kind == "agent_dispatched"


class TestIssueResolved:
    """Tests for IssueResolved event."""

    def test_creation(self) -> None:
        """Test IssueResolved creation with defaults."""
        event = IssueResolved(run_id="test-123", iteration=1)
        assert event.agent == ""
        assert event.file == ""
        assert event.duration_s == 0.0

    def test_creation_with_values(self) -> None:
        """Test IssueResolved creation with custom values."""
        event = IssueResolved(
            run_id="test-123",
            iteration=2,
            agent="security",
            file="src/auth.py",
            duration_s=1.5,
        )
        assert event.agent == "security"
        assert event.file == "src/auth.py"
        assert event.duration_s == 1.5

    def test_kind_class_var(self) -> None:
        """Test kind class variable."""
        assert IssueResolved.kind == "issue_resolved"


class TestIssueFailed:
    """Tests for IssueFailed event."""

    def test_creation(self) -> None:
        """Test IssueFailed creation with defaults."""
        event = IssueFailed(run_id="test-123", iteration=1)
        assert event.agent == ""
        assert event.file == ""
        assert event.reason == ""

    def test_creation_with_values(self) -> None:
        """Test IssueFailed creation with custom values."""
        event = IssueFailed(
            run_id="test-123",
            iteration=2,
            agent="refurb",
            file="src/broken.py",
            reason="Syntax error",
        )
        assert event.agent == "refurb"
        assert event.file == "src/broken.py"
        assert event.reason == "Syntax error"

    def test_kind_class_var(self) -> None:
        """Test kind class variable."""
        assert IssueFailed.kind == "issue_failed"


class TestIterationFinished:
    """Tests for IterationFinished event."""

    def test_creation(self) -> None:
        """Test IterationFinished creation with defaults."""
        event = IterationFinished(run_id="test-123", iteration=1)
        assert event.resolved == 0
        assert event.failed == 0
        assert event.success is True

    def test_creation_with_values(self) -> None:
        """Test IterationFinished creation with custom values."""
        event = IterationFinished(
            run_id="test-123",
            iteration=2,
            resolved=5,
            failed=1,
            success=False,
        )
        assert event.resolved == 5
        assert event.failed == 1
        assert event.success is False

    def test_kind_class_var(self) -> None:
        """Test kind class variable."""
        assert IterationFinished.kind == "iteration_finished"


class TestRunFinished:
    """Tests for RunFinished event."""

    def test_creation(self) -> None:
        """Test RunFinished creation with defaults."""
        event = RunFinished(run_id="test-123", iteration=0)
        assert event.success is True
        assert event.total_iterations == 0
        assert event.total_resolved == 0

    def test_creation_with_values(self) -> None:
        """Test RunFinished creation with custom values."""
        event = RunFinished(
            run_id="test-123",
            iteration=5,
            success=True,
            total_iterations=3,
            total_resolved=10,
        )
        assert event.success is True
        assert event.total_iterations == 3
        assert event.total_resolved == 10

    def test_kind_class_var(self) -> None:
        """Test kind class variable."""
        assert RunFinished.kind == "run_finished"


class TestPreflightStarted:
    """Tests for PreflightStarted event."""

    def test_creation(self) -> None:
        """Test PreflightStarted creation with defaults."""
        event = PreflightStarted(run_id="test-123", iteration=0)
        assert event.tools == ()

    def test_creation_with_values(self) -> None:
        """Test PreflightStarted creation with custom values."""
        event = PreflightStarted(
            run_id="test-123",
            iteration=0,
            tools=("ruff", "mypy", "bandit"),
        )
        assert event.tools == ("ruff", "mypy", "bandit")

    def test_kind_class_var(self) -> None:
        """Test kind class variable."""
        assert PreflightStarted.kind == "preflight_started"


class TestPreflightFinished:
    """Tests for PreflightFinished event."""

    def test_creation(self) -> None:
        """Test PreflightFinished creation with defaults."""
        event = PreflightFinished(run_id="test-123", iteration=0)
        assert event.issues_saved == 0
        assert event.duration_s == 0.0

    def test_creation_with_values(self) -> None:
        """Test PreflightFinished creation with custom values."""
        event = PreflightFinished(
            run_id="test-123",
            iteration=0,
            issues_saved=5,
            duration_s=2.5,
        )
        assert event.issues_saved == 5
        assert event.duration_s == 2.5

    def test_kind_class_var(self) -> None:
        """Test kind class variable."""
        assert PreflightFinished.kind == "preflight_finished"


class TestEventFrozen:
    """Tests for frozen nature of all events."""

    @pytest.mark.parametrize("event_class", [
        RunStarted,
        IterationStarted,
        AgentDispatched,
        IssueResolved,
        IssueFailed,
        IterationFinished,
        RunFinished,
        PreflightStarted,
        PreflightFinished,
    ])
    def test_events_are_frozen(self, event_class: type) -> None:
        """Test that all event classes produce frozen instances."""
        if event_class == RunStarted:
            event = event_class(run_id="test", iteration=1)
        elif event_class == IterationStarted:
            event = event_class(run_id="test", iteration=1)
        elif event_class == PreflightStarted:
            event = event_class(run_id="test", iteration=0)
        else:
            event = event_class(run_id="test", iteration=1)

        with pytest.raises(Exception):  # FrozenInstanceError
            event.run_id = "changed"


class TestEventKind:
    """Tests for kind class variable on all events."""

    @pytest.mark.parametrize("event_class,expected_kind", [
        (RunStarted, "run_started"),
        (IterationStarted, "iteration_started"),
        (AgentDispatched, "agent_dispatched"),
        (IssueResolved, "issue_resolved"),
        (IssueFailed, "issue_failed"),
        (IterationFinished, "iteration_finished"),
        (RunFinished, "run_finished"),
        (PreflightStarted, "preflight_started"),
        (PreflightFinished, "preflight_finished"),
    ])
    def test_kind_values(self, event_class: type, expected_kind: str) -> None:
        """Test kind class variable for all event types."""
        assert event_class.kind == expected_kind