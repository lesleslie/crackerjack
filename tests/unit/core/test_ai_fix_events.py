from __future__ import annotations

import dataclasses
import time

import pytest

from crackerjack.core.ai_fix_events import (
    AgentDispatched,
    AIFixEvent,
    IssueFailed,
    IssueResolved,
    IterationFinished,
    IterationStarted,
    RunFinished,
    RunStarted,
)


class TestAIFixEventBase:
    def test_base_fields_present(self) -> None:
        event = RunStarted(run_id="r1", iteration=0)
        assert event.run_id == "r1"
        assert event.iteration == 0
        assert isinstance(event.ts, float)

    def test_ts_defaults_to_current_time(self) -> None:
        before = time.time()
        event = RunStarted(run_id="r1", iteration=0)
        after = time.time()
        assert before <= event.ts <= after

    def test_frozen(self) -> None:
        event = RunStarted(run_id="r1", iteration=0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.run_id = "r2"  # type: ignore[misc]


class TestRunStarted:
    def test_kind_class_var(self) -> None:
        assert RunStarted.kind == "run_started"
        assert RunStarted(run_id="r", iteration=0).kind == "run_started"

    def test_kind_not_in_asdict(self) -> None:
        d = dataclasses.asdict(RunStarted(run_id="r", iteration=0))
        assert "kind" not in d

    def test_defaults(self) -> None:
        event = RunStarted(run_id="r", iteration=0)
        assert event.stage == ""
        assert event.initial_issue_count == 0

    def test_fields(self) -> None:
        event = RunStarted(run_id="abc", iteration=0, stage="comprehensive", initial_issue_count=7)
        assert event.stage == "comprehensive"
        assert event.initial_issue_count == 7


class TestIterationStarted:
    def test_kind(self) -> None:
        assert IterationStarted.kind == "iteration_started"

    def test_fields(self) -> None:
        event = IterationStarted(run_id="r", iteration=2, strategy="fast", issue_count=5)
        assert event.iteration == 2
        assert event.strategy == "fast"
        assert event.issue_count == 5


class TestAgentDispatched:
    def test_kind(self) -> None:
        assert AgentDispatched.kind == "agent_dispatched"

    def test_fields(self) -> None:
        event = AgentDispatched(run_id="r", iteration=0, agent="RefactoringAgent", action="fix", file="foo.py")
        assert event.agent == "RefactoringAgent"
        assert event.action == "fix"
        assert event.file == "foo.py"


class TestIssueResolved:
    def test_kind(self) -> None:
        assert IssueResolved.kind == "issue_resolved"

    def test_duration_default(self) -> None:
        event = IssueResolved(run_id="r", iteration=0, agent="A", file="f.py")
        assert event.duration_s == 0.0


class TestIssueFailed:
    def test_kind(self) -> None:
        assert IssueFailed.kind == "issue_failed"

    def test_reason_default(self) -> None:
        event = IssueFailed(run_id="r", iteration=0, agent="A", file="f.py")
        assert event.reason == ""


class TestIterationFinished:
    def test_kind(self) -> None:
        assert IterationFinished.kind == "iteration_finished"

    def test_defaults(self) -> None:
        event = IterationFinished(run_id="r", iteration=1)
        assert event.resolved == 0
        assert event.failed == 0
        assert event.success is True


class TestRunFinished:
    def test_kind(self) -> None:
        assert RunFinished.kind == "run_finished"

    def test_defaults(self) -> None:
        event = RunFinished(run_id="r", iteration=3)
        assert event.success is True
        assert event.total_iterations == 0

    def test_asdict_serialisable(self) -> None:
        import json
        event = RunFinished(run_id="r", iteration=3, success=False, total_iterations=3)
        d = dataclasses.asdict(event)
        json.dumps(d)  # must not raise


class TestPolymorphism:
    def test_all_events_are_ai_fix_event(self) -> None:
        events: list[AIFixEvent] = [
            RunStarted(run_id="r", iteration=0),
            IterationStarted(run_id="r", iteration=1),
            AgentDispatched(run_id="r", iteration=0, agent="A", action="fix", file="f.py"),
            IssueResolved(run_id="r", iteration=0, agent="A", file="f.py"),
            IssueFailed(run_id="r", iteration=0, agent="A", file="f.py"),
            IterationFinished(run_id="r", iteration=1),
            RunFinished(run_id="r", iteration=2),
        ]
        for e in events:
            assert isinstance(e, AIFixEvent)
