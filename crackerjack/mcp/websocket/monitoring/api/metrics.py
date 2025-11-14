"""REST API endpoints for metrics and quality analysis.

This module provides HTTP endpoints for metrics summaries, quality trends,
alert configuration, and data export.
"""

import asyncio
import csv
import typing as t
from datetime import datetime
from io import StringIO

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response

from crackerjack.services.quality.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,
)

from ..utils import get_current_metrics


def register_metrics_api_endpoints(
    app: FastAPI, job_manager: t.Any, quality_service: EnhancedQualityBaselineService
) -> None:
    """Register metrics-related REST API endpoints."""

    @app.get("/api/metrics/summary")
    async def get_metrics_summary() -> None:
        """Get current system summary."""
        try:
            current_metrics = await get_current_metrics(quality_service, job_manager)
            return JSONResponse(
                {
                    "status": "success",
                    "data": current_metrics.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/trends/quality")
    async def get_quality_trends(days: int = 30) -> None:
        """Get quality trend analysis."""
        return await _handle_quality_trends_request(quality_service, days)

    @app.get("/api/alerts/configure")
    async def get_alert_configuration() -> None:
        """Get current alert configuration."""
        return await _handle_get_alert_configuration(quality_service)

    @app.post("/api/alerts/configure")
    async def update_alert_configuration(config: dict) -> None:
        """Update alert configuration."""
        return await _handle_update_alert_configuration(quality_service, config)

    @app.get("/api/export/data")
    async def export_data(days: int = 30, format: str = "json") -> None:
        """Export historical data for external analysis."""
        return await _handle_export_data_request(quality_service, days, format)


async def _handle_quality_trends_request(
    quality_service: EnhancedQualityBaselineService, days: int
) -> JSONResponse:
    """Handle quality trends API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        trends = await asyncio.to_thread(
            quality_service.analyze_quality_trend,
            days,
        )
        return JSONResponse(
            {
                "status": "success",
                "data": trends.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_get_alert_configuration(
    quality_service: EnhancedQualityBaselineService,
) -> JSONResponse:
    """Handle get alert configuration API request."""
    try:
        config = quality_service.get_alert_thresholds()
        return JSONResponse(
            {
                "status": "success",
                "data": config,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_update_alert_configuration(
    quality_service: EnhancedQualityBaselineService, config: dict
) -> JSONResponse:
    """Handle update alert configuration API request."""
    try:
        # Update individual thresholds
        for metric, threshold in config.items():
            quality_service.set_alert_threshold(metric, threshold)
        return JSONResponse(
            {
                "status": "success",
                "message": "Alert configuration updated",
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_export_data_request(
    quality_service: EnhancedQualityBaselineService, days: int, format_type: str
) -> JSONResponse | t.Any:
    """Handle export data API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        if format_type not in ("json", "csv"):
            raise HTTPException(
                status_code=400, detail="Format must be 'json' or 'csv'"
            )

        historical_baselines = await quality_service.aget_recent_baselines(limit=days)

        if format_type == "csv":
            return _export_csv_data(historical_baselines, days)
        else:
            data = [baseline.to_dict() for baseline in historical_baselines]
            return JSONResponse(
                {
                    "status": "success",
                    "data": data,
                    "timestamp": datetime.now().isoformat(),
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _export_csv_data(historical_baselines: list[t.Any], days: int) -> t.Any:
    """Export data in CSV format."""
    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "timestamp",
            "git_hash",
            "quality_score",
            "coverage_percent",
            "test_count",
            "test_pass_rate",
            "hook_failures",
            "complexity_violations",
            "security_issues",
            "type_errors",
            "linting_issues",
        ]
    )

    # Write data
    for baseline in historical_baselines:
        writer.writerow(
            [
                baseline.timestamp.isoformat(),
                baseline.git_hash,
                baseline.quality_score,
                baseline.coverage_percent,
                baseline.test_count,
                baseline.test_pass_rate,
                baseline.hook_failures,
                baseline.complexity_violations,
                baseline.security_issues,
                baseline.type_errors,
                baseline.linting_issues,
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=crackerjack_metrics_{days}d.csv"
            )
        },
    )
