"""Metrics utilities for the monitoring system.

This module contains functions for collecting, processing, and returning
current system metrics used by the monitoring endpoints.
"""

from datetime import datetime
from typing import Any

from crackerjack.services.quality.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,
    UnifiedMetrics,
)


async def get_monitoring_current_metrics(
    quality_service: EnhancedQualityBaselineService, job_manager: Any
) -> UnifiedMetrics:
    """Get current system metrics for monitoring API endpoints.

    Args:
        quality_service: EnhancedQualityBaselineService with the quality data
        job_manager: Job manager instance to access current job states

    Returns:
        UnifiedMetrics containing current system metrics
    """
    # Get current quality metrics from the service
    current_baseline = await quality_service.aget_current_baseline()

    # Calculate additional metrics
    active_jobs = 0
    error_count = 0

    # Access job manager to get current status if possible
    try:
        if hasattr(job_manager, "get_active_jobs"):
            active_jobs = len(job_manager.get_active_jobs() or [])
        elif hasattr(job_manager, "active_jobs"):
            active_jobs = len(job_manager.active_jobs or [])

        if hasattr(job_manager, "get_error_count"):
            error_count = job_manager.get_error_count()
        elif hasattr(job_manager, "error_count"):
            error_count = getattr(job_manager, "error_count", 0)
    except Exception:
        # If we can't access job info, use defaults
        pass

    # Create UnifiedMetrics instance with current data
    metrics = UnifiedMetrics(
        timestamp=datetime.now(),
        quality_score=current_baseline.quality_score if current_baseline else 100,
        test_coverage=current_baseline.coverage_percent if current_baseline else 0.0,
        hook_duration=current_baseline.hook_duration if current_baseline else 0.0,
        active_jobs=active_jobs,
        error_count=error_count,
        trend_direction=current_baseline.trend_direction
        if current_baseline
        else "stable",
        predictions=current_baseline.predictions if current_baseline else {},
    )

    return metrics
