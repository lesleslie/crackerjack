from __future__ import annotations

from copy import deepcopy

try:
    from oneiric.core.logging import get_logger
except ImportError:
    import logging

    def get_logger(name: str | None = None) -> logging.Logger:
        return logging.getLogger(name)


logger = get_logger(__name__)

OPEN_QUESTION_PENALTY = 8
UNCHECKED_SOURCE_PENALTY = 5
FLOOR = 0


def compute_confidence_cap(report: dict) -> int:
    open_q_count = len(report.get("open_questions", []))
    unchecked_count = len(report.get("unchecked_sources", []))
    raw = (
        100
        - (open_q_count * OPEN_QUESTION_PENALTY)
        - (unchecked_count * UNCHECKED_SOURCE_PENALTY)
    )
    return max(FLOOR, raw)


def apply_confidence_ceiling(report: dict) -> dict:
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
        from mahavishnu.akosha_client import (
            emit_anomaly, # type: ignore[import-not-found]
        )

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
