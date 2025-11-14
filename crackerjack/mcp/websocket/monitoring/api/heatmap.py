"""REST API endpoints for error heatmap analysis.

This module provides HTTP endpoints for file-based, temporal, and
function-based error heatmap visualization and pattern analysis.
"""

from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.monitoring.error_pattern_analyzer import (
    ErrorPatternAnalyzer,
)


def register_heatmap_api_endpoints(
    app: FastAPI, error_analyzer: ErrorPatternAnalyzer, cache: CrackerjackCache
) -> None:
    """Register heatmap-related REST API endpoints."""

    @app.get("/api/heatmap/file_errors")
    async def get_file_error_heatmap() -> None:
        """Get error heat map by file."""
        return await _handle_file_error_heatmap_request(error_analyzer)

    @app.get("/api/heatmap/temporal_errors")
    async def get_temporal_error_heatmap(time_buckets: int = 24) -> None:
        """Get error heat map over time."""
        return await _handle_temporal_error_heatmap_request(
            error_analyzer, time_buckets
        )

    @app.get("/api/heatmap/function_errors")
    async def get_function_error_heatmap() -> None:
        """Get error heat map by function."""
        return await _handle_function_error_heatmap_request(error_analyzer)

    @app.get("/api/error_patterns")
    async def get_error_patterns(
        days: int = 30, min_occurrences: int = 2, severity: str | None = None
    ) -> None:
        """Get analyzed error patterns."""
        return await _handle_error_patterns_request(
            error_analyzer, days, min_occurrences, severity
        )

    @app.post("/api/trigger_error_analysis")
    async def trigger_error_analysis(request: dict) -> None:
        """Trigger fresh error pattern analysis."""
        return await _handle_trigger_error_analysis_request(
            error_analyzer, cache, request
        )


async def _handle_file_error_heatmap_request(
    error_analyzer: ErrorPatternAnalyzer,
) -> JSONResponse:
    """Handle file error heatmap API request."""
    try:
        error_analyzer.analyze_error_patterns(days=30)
        heatmap = error_analyzer.generate_file_error_heatmap()
        return JSONResponse(heatmap.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_temporal_error_heatmap_request(
    error_analyzer: ErrorPatternAnalyzer, time_buckets: int
) -> JSONResponse:
    """Handle temporal error heatmap API request."""
    try:
        error_analyzer.analyze_error_patterns(days=30)
        heatmap = error_analyzer.generate_temporal_heatmap(time_buckets=time_buckets)
        return JSONResponse(heatmap.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_function_error_heatmap_request(
    error_analyzer: ErrorPatternAnalyzer,
) -> JSONResponse:
    """Handle function error heatmap API request."""
    try:
        error_analyzer.analyze_error_patterns(days=30)
        heatmap = error_analyzer.generate_function_error_heatmap()
        return JSONResponse(heatmap.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_error_patterns_request(
    error_analyzer: ErrorPatternAnalyzer,
    days: int,
    min_occurrences: int,
    severity: str | None,
) -> JSONResponse:
    """Handle error patterns API request."""
    try:
        patterns = error_analyzer.analyze_error_patterns(
            days=days, min_occurrences=min_occurrences
        )

        # Filter by severity if specified
        if severity:
            patterns = [p for p in patterns if p.severity == severity]

        return JSONResponse(
            {
                "patterns": [pattern.to_dict() for pattern in patterns],
                "total_count": len(patterns),
                "analysis_period_days": days,
                "generated_at": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_trigger_error_analysis_request(
    error_analyzer: ErrorPatternAnalyzer, cache: CrackerjackCache, request: dict
) -> JSONResponse:
    """Handle trigger error analysis API request."""
    try:
        days = request.get("days", 30)
        min_occurrences = request.get("min_occurrences", 2)

        # Perform fresh analysis
        patterns = error_analyzer.analyze_error_patterns(
            days=days, min_occurrences=min_occurrences
        )

        # Store results in cache
        cache_key = f"error_patterns_{days}d"
        cache.set(cache_key, [p.to_dict() for p in patterns], ttl_seconds=1800)

        severity_breakdown = {
            severity: len([p for p in patterns if p.severity == severity])
            for severity in ("low", "medium", "high", "critical")
        }

        return JSONResponse(
            {
                "status": "success",
                "message": "Error pattern analysis completed",
                "patterns_found": len(patterns),
                "analysis_period_days": days,
                "severity_breakdown": severity_breakdown,
                "generated_at": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
