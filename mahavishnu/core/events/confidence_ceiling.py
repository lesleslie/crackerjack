"""Confidence ceiling gate (Spec #3).

Pure-function cap on reported confidence based on enumerable doubt
(open_questions + unchecked_sources). Caps do not raise; over-confidence
is calibration, not a rule violation. Spec:
docs/superpowers/specs/2026-06-22-confidence-ceiling-gate-design.md
"""

from __future__ import annotations

from copy import deepcopy

try:
    from oneiric.core.logging import get_logger
except ImportError:  # oneiric not installed; fall back to stdlib
    import logging

    def get_logger(name: str | None = None) -> logging.Logger:
        return logging.getLogger(name)

logger = get_logger(__name__)

OPEN_QUESTION_PENALTY = 8
UNCHECKED_SOURCE_PENALTY = 5
FLOOR = 0


def compute_confidence_cap(report: dict) -> int:
    """Compute the ceiling for an iteration report's confidence.

    Pure function; no side effects. Returns int in [0, 100].
    """
    open_q_count = len(report.get("open_questions", []))
    unchecked_count = len(report.get("unchecked_sources", []))
    raw = 100 - (open_q_count * OPEN_QUESTION_PENALTY) - (
        unchecked_count * UNCHECKED_SOURCE_PENALTY
    )
    return max(FLOOR, raw)


def apply_confidence_ceiling(report: dict) -> dict:
    """Apply the confidence ceiling to an IterationReport.

    If report["confidence"] exceeds the computed ceiling, returns a deep
    copy with confidence replaced by the ceiling. Otherwise returns the
    report unchanged.

    Side effects: logs a WARNING when capping occurs; best-effort emits
    an Akosha anomaly event when capping occurs (silent if unavailable).
    Does NOT raise.
    """
    cap = compute_confidence_cap(report)
    reported = report.get("confidence", 0)

    if reported <= cap:
        return report

    capped = deepcopy(report)
    capped["confidence"] = cap
    logger.warning(
        "confidence capped by ceiling",
        extra={
            "workflow_id": report.get("workflow_id"),
            "iteration_index": report.get("iteration_index"),
            "reported_confidence": reported,
            "computed_cap": cap,
            "open_questions_count": len(report.get("open_questions", [])),
            "unchecked_sources_count": len(report.get("unchecked_sources", [])),
        },
    )
    try:
        from mahavishnu.akosha_client import emit_anomaly  # type: ignore[import-not-found]

        emit_anomaly(
            kind="confidence_capped",
            workflow_id=report.get("workflow_id"),
            iteration_index=report.get("iteration_index"),
            reported_confidence=reported,
            computed_cap=cap,
        )
    except ImportError:
        pass
    except Exception:
        logger.exception("failed to emit akosha anomaly for confidence cap")
    return capped