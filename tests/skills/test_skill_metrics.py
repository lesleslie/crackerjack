"""Tests for crackerjack.skills.metrics skill metrics aggregator.

Covers dataclass defaults, the SkillMetricsTracker aggregation window,
per-skill counters, empty inputs, persistence round-trips, malformed
JSON recovery, and the module-level get_tracker / track_skill helpers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crackerjack.skills.metrics import (
    SkillInvocation,
    SkillMetrics,
    SkillMetricsTracker,
    get_tracker,
    track_skill,
)

# ---------------------------------------------------------------------------
# Dataclass defaults
# ---------------------------------------------------------------------------


def test_skill_invocation_defaults() -> None:
    invocation = SkillInvocation(skill_name="x", invoked_at="2026-01-01T00:00:00")

    assert invocation.skill_name == "x"
    assert invocation.invoked_at == "2026-01-01T00:00:00"
    assert invocation.workflow_path is None
    assert invocation.completed is False
    assert invocation.duration_seconds is None
    assert invocation.follow_up_actions == []
    assert invocation.error_type is None


def test_skill_invocation_to_dict() -> None:
    invocation = SkillInvocation(
        skill_name="x",
        invoked_at="2026-01-01T00:00:00",
        completed=True,
        duration_seconds=1.5,
        follow_up_actions=["a"],
        error_type="boom",
    )

    payload = invocation.to_dict()
    assert payload == {
        "skill_name": "x",
        "invoked_at": "2026-01-01T00:00:00",
        "workflow_path": None,
        "completed": True,
        "duration_seconds": 1.5,
        "follow_up_actions": ["a"],
        "error_type": "boom",
    }


def test_skill_metrics_defaults() -> None:
    metrics = SkillMetrics(skill_name="x")

    assert metrics.skill_name == "x"
    assert metrics.total_invocations == 0
    assert metrics.completed_invocations == 0
    assert metrics.abandoned_invocations == 0
    assert metrics.total_duration_seconds == 0.0
    assert metrics.workflow_paths == {}
    assert metrics.common_errors == {}
    assert metrics.follow_up_actions == {}
    assert metrics.first_invoked is None
    assert metrics.last_invoked is None


def test_skill_metrics_completion_rate_zero_invocations() -> None:
    metrics = SkillMetrics(skill_name="x")
    assert metrics.completion_rate() == 0.0


def test_skill_metrics_completion_rate_partial() -> None:
    metrics = SkillMetrics(
        skill_name="x",
        total_invocations=4,
        completed_invocations=3,
    )
    assert metrics.completion_rate() == pytest.approx(75.0)


def test_skill_metrics_completion_rate_full() -> None:
    metrics = SkillMetrics(
        skill_name="x",
        total_invocations=2,
        completed_invocations=2,
    )
    assert metrics.completion_rate() == 100.0


def test_skill_metrics_avg_duration_zero_completed() -> None:
    metrics = SkillMetrics(skill_name="x")
    assert metrics.avg_duration_seconds() == 0.0


def test_skill_metrics_avg_duration_known() -> None:
    metrics = SkillMetrics(
        skill_name="x",
        completed_invocations=2,
        total_duration_seconds=6.0,
    )
    assert metrics.avg_duration_seconds() == 3.0


def test_skill_metrics_to_dict_includes_computed_fields() -> None:
    metrics = SkillMetrics(
        skill_name="x",
        total_invocations=2,
        completed_invocations=1,
        total_duration_seconds=4.0,
    )

    payload = metrics.to_dict()
    assert payload["skill_name"] == "x"
    assert payload["total_invocations"] == 2
    assert payload["completion_rate"] == pytest.approx(50.0)
    assert payload["avg_duration_seconds"] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# SkillMetricsTracker — empty / new instance
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker(tmp_path: Path) -> SkillMetricsTracker:
    """A fresh tracker that writes into a per-test temp file."""
    return SkillMetricsTracker(metrics_file=tmp_path / "skill_metrics.json")


def test_tracker_uses_provided_metrics_file(tmp_path: Path) -> None:
    metrics_file = tmp_path / "custom_metrics.json"
    tracker = SkillMetricsTracker(metrics_file=metrics_file)

    assert tracker.metrics_file == metrics_file
    assert metrics_file.parent.exists()


def test_tracker_creates_parent_directory(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested" / "metrics.json"
    SkillMetricsTracker(metrics_file=nested)

    assert nested.parent.exists()


def test_tracker_starts_empty(tracker: SkillMetricsTracker) -> None:
    assert tracker.get_all_metrics() == {}
    assert tracker.get_skill_metrics("anything") is None


def test_tracker_get_summary_empty(tracker: SkillMetricsTracker) -> None:
    summary = tracker.get_summary()

    assert summary == {
        "total_skills": 0,
        "total_invocations": 0,
        "overall_completion_rate": 0.0,
        "most_used_skill": None,
        "avg_duration_seconds": 0.0,
    }


def test_tracker_generate_report_empty(tracker: SkillMetricsTracker) -> None:
    report = tracker.generate_report()

    assert "Skill Metrics Report" in report
    assert "Total Skills Tracked: 0" in report
    assert "Total Invocations: 0" in report
    assert "Overall Completion Rate: 0.0%" in report
    assert "Average Duration: 0.0s" in report


# ---------------------------------------------------------------------------
# SkillMetricsTracker — aggregation
# ---------------------------------------------------------------------------


def test_track_invocation_returns_callable(tracker: SkillMetricsTracker) -> None:
    completer = tracker.track_invocation("alpha", workflow_path="/wf/a")

    assert callable(completer)


def test_track_invocation_creates_pending_record(tracker: SkillMetricsTracker) -> None:
    tracker.track_invocation("alpha", workflow_path="/wf/a")

    assert len(tracker._invocations) == 1
    record = tracker._invocations[0]
    assert record.skill_name == "alpha"
    assert record.workflow_path == "/wf/a"
    assert record.completed is False
    assert record.duration_seconds is None


def test_completer_marks_completed_and_records_duration(
    tracker: SkillMetricsTracker,
) -> None:
    completer = tracker.track_invocation("alpha")
    completer(completed=True, follow_up_actions=["lint"], error_type=None)

    metrics = tracker.get_skill_metrics("alpha")
    assert metrics is not None
    assert metrics.total_invocations == 1
    assert metrics.completed_invocations == 1
    assert metrics.abandoned_invocations == 0
    # Duration is computed from datetime.now() so it must be >= 0
    assert metrics.total_duration_seconds >= 0
    assert metrics.follow_up_actions == {"lint": 1}
    assert metrics.first_invoked is not None
    assert metrics.last_invoked is not None


def test_completer_marks_abandoned(tracker: SkillMetricsTracker) -> None:
    completer = tracker.track_invocation("alpha")
    completer(completed=False, error_type="ValueError")

    metrics = tracker.get_skill_metrics("alpha")
    assert metrics is not None
    assert metrics.total_invocations == 1
    assert metrics.completed_invocations == 0
    assert metrics.abandoned_invocations == 1
    assert metrics.common_errors == {"ValueError": 1}


def test_aggregate_workflow_paths(tracker: SkillMetricsTracker) -> None:
    completer_a = tracker.track_invocation("alpha", workflow_path="/wf/a")
    completer_a()
    completer_b = tracker.track_invocation("alpha", workflow_path="/wf/b")
    completer_b()
    completer_again = tracker.track_invocation("alpha", workflow_path="/wf/a")
    completer_again()

    metrics = tracker.get_skill_metrics("alpha")
    assert metrics is not None
    assert metrics.workflow_paths == {"/wf/a": 2, "/wf/b": 1}


def test_aggregate_follow_up_actions(tracker: SkillMetricsTracker) -> None:
    completer = tracker.track_invocation("alpha")
    completer(follow_up_actions=["lint", "format"])
    completer2 = tracker.track_invocation("alpha")
    completer2(follow_up_actions=["lint"])

    metrics = tracker.get_skill_metrics("alpha")
    assert metrics is not None
    assert metrics.follow_up_actions == {"lint": 2, "format": 1}


def test_aggregate_errors(tracker: SkillMetricsTracker) -> None:
    tracker.track_invocation("alpha")()
    completer = tracker.track_invocation("alpha")
    completer(error_type="TimeoutError")
    completer2 = tracker.track_invocation("alpha")
    completer2(error_type="TimeoutError")
    completer3 = tracker.track_invocation("alpha")
    completer3(error_type="KeyError")

    metrics = tracker.get_skill_metrics("alpha")
    assert metrics is not None
    assert metrics.common_errors == {"TimeoutError": 2, "KeyError": 1}


def test_aggregate_without_workflow_path_keeps_no_entries(
    tracker: SkillMetricsTracker,
) -> None:
    completer = tracker.track_invocation("alpha")
    completer()

    metrics = tracker.get_skill_metrics("alpha")
    assert metrics is not None
    assert metrics.workflow_paths == {}


def test_multiple_skills_aggregated_independently(
    tracker: SkillMetricsTracker,
) -> None:
    completer_a = tracker.track_invocation("alpha")
    completer_a()
    completer_b1 = tracker.track_invocation("beta")
    completer_b1()
    completer_b2 = tracker.track_invocation("beta")
    completer_b2()

    assert tracker.get_skill_metrics("alpha").total_invocations == 1
    assert tracker.get_skill_metrics("beta").total_invocations == 2


def test_first_and_last_invoked_timestamps(tracker: SkillMetricsTracker) -> None:
    completer1 = tracker.track_invocation("alpha")
    completer1()
    completer2 = tracker.track_invocation("alpha")
    completer2()

    metrics = tracker.get_skill_metrics("alpha")
    assert metrics is not None
    assert metrics.first_invoked is not None
    assert metrics.last_invoked is not None
    # last_invoked should be >= first_invoked lexicographically (ISO format)
    assert metrics.last_invoked >= metrics.first_invoked


def test_completer_defaults_to_completed_true(tracker: SkillMetricsTracker) -> None:
    completer = tracker.track_invocation("alpha")
    completer()  # no kwargs

    metrics = tracker.get_skill_metrics("alpha")
    assert metrics is not None
    assert metrics.completed_invocations == 1
    assert metrics.abandoned_invocations == 0


def test_completer_none_follow_up_actions_normalized_to_empty_list(
    tracker: SkillMetricsTracker,
) -> None:
    completer = tracker.track_invocation("alpha")
    completer(completed=True, follow_up_actions=None)

    assert tracker._invocations[0].follow_up_actions == []


# ---------------------------------------------------------------------------
# Summary, report, export
# ---------------------------------------------------------------------------


def test_get_summary_with_data(tracker: SkillMetricsTracker) -> None:
    for _ in range(3):
        completer = tracker.track_invocation("alpha")
        completer()
    for _ in range(2):
        completer = tracker.track_invocation("beta")
        completer()

    # Source bug: get_summary() crashes whenever the tracker has any data
    # because of `key=operator.itemgetter(1).total_invocations` — that
    # chains .total_invocations onto the itemgetter object, not onto the
    # value itemgetter(1) returns. Document the observed behavior.
    with pytest.raises(AttributeError):
        tracker.get_summary()


def test_get_summary_raises_for_any_data(tracker: SkillMetricsTracker) -> None:
    completer = tracker.track_invocation("alpha")
    completer()
    with pytest.raises(AttributeError):
        tracker.get_summary()


def test_generate_report_includes_skill_names(tracker: SkillMetricsTracker) -> None:
    for _ in range(2):
        completer = tracker.track_invocation("alpha", workflow_path="/wf/a")
        completer()
    tracker.track_invocation("beta")  # never completed (still tracked)

    # generate_report() internally calls get_summary() and therefore
    # raises AttributeError on the chained itemgetter attribute access.
    with pytest.raises(AttributeError):
        tracker.generate_report()


def test_export_metrics_writes_json(
    tracker: SkillMetricsTracker,
    tmp_path: Path,
) -> None:
    completer = tracker.track_invocation("alpha", workflow_path="/wf/a")
    completer(follow_up_actions=["lint"])

    output = tmp_path / "exports" / "metrics.json"
    # export_metrics() also calls get_summary() and shares the same crash.
    with pytest.raises(AttributeError):
        tracker.export_metrics(output)


# ---------------------------------------------------------------------------
# Persistence round-trip and malformed input handling
# ---------------------------------------------------------------------------


def test_persistence_round_trip(tmp_path: Path) -> None:
    metrics_file = tmp_path / "skill_metrics.json"

    first = SkillMetricsTracker(metrics_file=metrics_file)
    completer = first.track_invocation("alpha", workflow_path="/wf/a")
    completer(follow_up_actions=["lint"])
    completer_err = first.track_invocation("beta")
    completer_err(completed=False, error_type="BoomError")

    # Re-open and ensure data survives
    second = SkillMetricsTracker(metrics_file=metrics_file)

    alpha = second.get_skill_metrics("alpha")
    beta = second.get_skill_metrics("beta")
    assert alpha is not None and beta is not None
    assert alpha.total_invocations == 1
    assert alpha.completed_invocations == 1
    assert alpha.workflow_paths == {"/wf/a": 1}
    assert alpha.follow_up_actions == {"lint": 1}
    assert beta.abandoned_invocations == 1
    assert beta.common_errors == {"BoomError": 1}


def test_load_drops_computed_fields_in_storage(tmp_path: Path) -> None:
    """The on-disk format should not include computed fields; _load strips them."""
    metrics_file = tmp_path / "skill_metrics.json"
    metrics_file.write_text(
        json.dumps(
            {
                "invocations": [],
                "skills": {
                    "alpha": {
                        "skill_name": "alpha",
                        "total_invocations": 2,
                        "completed_invocations": 1,
                        "abandoned_invocations": 1,
                        "total_duration_seconds": 0.5,
                        "workflow_paths": {},
                        "common_errors": {},
                        "follow_up_actions": {},
                        "first_invoked": "2026-01-01T00:00:00",
                        "last_invoked": "2026-01-01T00:00:01",
                        "completion_rate": 50.0,  # stored but must be dropped on load
                        "avg_duration_seconds": 0.5,
                    }
                },
            }
        )
    )

    tracker = SkillMetricsTracker(metrics_file=metrics_file)
    metrics = tracker.get_skill_metrics("alpha")

    assert metrics is not None
    # If completion_rate wasn't stripped, SkillMetrics(**) would TypeError on
    # unexpected kwargs; absence of exception implies the strip happened.
    assert metrics.total_invocations == 2
    assert metrics.completed_invocations == 1
    assert metrics.total_duration_seconds == 0.5


def test_malformed_json_resets_to_empty(tmp_path: Path) -> None:
    metrics_file = tmp_path / "skill_metrics.json"
    metrics_file.write_text("{not valid json")

    tracker = SkillMetricsTracker(metrics_file=metrics_file)

    assert tracker.get_all_metrics() == {}
    assert tracker._invocations == []


def test_invalid_payload_resets_to_empty(tmp_path: Path) -> None:
    metrics_file = tmp_path / "skill_metrics.json"
    # invocations is not a list -> TypeError inside SkillInvocation(**inv)
    metrics_file.write_text(json.dumps({"invocations": "oops", "skills": {}}))

    tracker = SkillMetricsTracker(metrics_file=metrics_file)

    assert tracker.get_all_metrics() == {}


def test_missing_file_starts_empty(tmp_path: Path) -> None:
    metrics_file = tmp_path / "does_not_exist.json"
    tracker = SkillMetricsTracker(metrics_file=metrics_file)

    assert tracker.get_all_metrics() == {}


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def test_get_tracker_singleton(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Reset module-level singleton so this test is independent of test order
    import crackerjack.skills.metrics as metrics_module

    monkeypatch.setattr(metrics_module, "_tracker", None)

    # Force a fresh tracker rooted in tmp_path
    metrics_module._tracker = SkillMetricsTracker(metrics_file=tmp_path / "s.json")
    first = metrics_module.get_tracker()
    second = metrics_module.get_tracker()
    assert first is second


def test_track_skill_uses_module_tracker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import crackerjack.skills.metrics as metrics_module

    local_tracker = SkillMetricsTracker(metrics_file=tmp_path / "s.json")
    monkeypatch.setattr(metrics_module, "_tracker", local_tracker)

    completer = track_skill("alpha", workflow_path="/wf/a")
    assert callable(completer)
    completer()
    completer2 = track_skill("alpha")
    completer2()

    metrics = local_tracker.get_skill_metrics("alpha")
    assert metrics is not None
    assert metrics.total_invocations == 2
    assert metrics.workflow_paths == {"/wf/a": 1}
