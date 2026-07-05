"""L0 unit tests for the confidence ceiling gate.

Covers formula edge cases, capping behavior, deep copy semantics, and
the warning-log side effect. Spec: 2026-06-22-confidence-ceiling-gate-design.md
"""

from __future__ import annotations

import logging

import pytest

from mahavishnu.core.events.confidence_ceiling import (
    apply_confidence_ceiling,
    compute_confidence_cap,
)


def _report(confidence: int = 0, open_q: int = 0, unchecked: int = 0) -> dict:
    return {
        "confidence": confidence,
        "open_questions": [f"q{i}" for i in range(open_q)],
        "unchecked_sources": [f"s{i}" for i in range(unchecked)],
    }


def test_compute_cap_no_questions_no_sources():
    assert compute_confidence_cap(_report()) == 100


def test_compute_cap_one_open_question():
    assert compute_confidence_cap(_report(open_q=1)) == 92


def test_compute_cap_one_unchecked_source():
    assert compute_confidence_cap(_report(unchecked=1)) == 95


def test_compute_cap_mixed():
    assert compute_confidence_cap(_report(open_q=5, unchecked=5)) == 35


def test_compute_cap_floor_zero():
    assert compute_confidence_cap(_report(open_q=13, unchecked=1)) == 0


def test_compute_cap_missing_arrays_defaults_to_empty():
    report: dict = {"confidence": 50}
    assert compute_confidence_cap(report) == 100


def test_apply_ceiling_reports_within_cap_returns_unchanged():
    report = _report(confidence=80, open_q=2)
    result = apply_confidence_ceiling(report)
    assert result is report
    assert result["confidence"] == 80


def test_apply_ceiling_reports_above_cap_returns_capped_copy():
    report = _report(confidence=99, open_q=2)
    result = apply_confidence_ceiling(report)
    assert result is not report
    assert result["confidence"] == 84  # 100 - 2*8
    assert report["confidence"] == 99  # original unchanged


def test_apply_ceiling_logs_warning_when_capping():
    """Verify the gate emits a WARNING when capping occurs."""
    import structlog.testing

    report = _report(confidence=99, open_q=3)
    with structlog.testing.capture_logs() as cap_logs:
        result = apply_confidence_ceiling(report)
    assert result["confidence"] == 76
    assert any(
        "confidence capped" in entry["event"].lower() for entry in cap_logs
    ), cap_logs


def test_apply_ceiling_at_exact_cap_no_log():
    """Verify the gate does NOT emit a warning when within cap."""
    import structlog.testing

    report = _report(confidence=84, open_q=2)
    with structlog.testing.capture_logs() as cap_logs:
        result = apply_confidence_ceiling(report)
    assert result is report
    assert not any("capped" in entry["event"].lower() for entry in cap_logs)
