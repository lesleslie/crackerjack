"""REST API endpoints for quality intelligence features.

This module provides HTTP endpoints for anomaly detection, predictions,
insights, and pattern analysis.
"""

import typing as t
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from crackerjack.services.quality.quality_intelligence import (
    QualityIntelligenceService,
)


def register_intelligence_api_endpoints(
    app: FastAPI, intelligence_service: QualityIntelligenceService
) -> None:
    """Register intelligence-related REST API endpoints."""

    @app.get("/api/intelligence/anomalies")
    async def get_anomalies(days: int = 7, metrics: str = None) -> None:
        """Get anomaly detection results."""
        return await _handle_anomalies_request(intelligence_service, days, metrics)

    @app.get("/api/intelligence/predictions/{metric}")
    async def get_metric_prediction(metric: str, horizon_days: int = 7) -> None:
        """Get prediction for a specific metric."""
        return await _handle_metric_prediction_request(
            intelligence_service, metric, horizon_days
        )

    @app.get("/api/intelligence/insights")
    async def get_quality_insights(days: int = 30) -> None:
        """Get comprehensive quality insights."""
        return await _handle_quality_insights_request(intelligence_service, days)

    @app.get("/api/intelligence/patterns")
    async def get_pattern_analysis(days: int = 30) -> None:
        """Get pattern recognition analysis."""
        return await _handle_pattern_analysis_request(intelligence_service, days)

    @app.post("/api/intelligence/analyze")
    async def run_comprehensive_analysis(request: dict) -> None:
        """Run comprehensive intelligence analysis."""
        return await _handle_comprehensive_analysis_request(
            intelligence_service, request
        )


async def _handle_anomalies_request(
    intelligence_service: QualityIntelligenceService, days: int, metrics: str | None
) -> JSONResponse:
    """Handle anomalies API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        metrics_list = metrics.split(",") if metrics else None
        anomalies = intelligence_service.detect_anomalies(
            days=days, metrics=metrics_list
        )

        return JSONResponse(
            {
                "status": "success",
                "data": [anomaly.to_dict() for anomaly in anomalies],
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_metric_prediction_request(
    intelligence_service: QualityIntelligenceService, metric: str, horizon_days: int
) -> JSONResponse:
    """Handle metric prediction API request."""
    try:
        if horizon_days > 30:
            raise HTTPException(status_code=400, detail="Horizon too far in the future")

        all_predictions = intelligence_service.generate_advanced_predictions(
            horizon_days
        )
        prediction = next((p for p in all_predictions if p.metric_name == metric), None)
        if not prediction:
            raise HTTPException(status_code=404, detail="Prediction not available")

        return JSONResponse(
            {
                "status": "success",
                "data": prediction.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_quality_insights_request(
    intelligence_service: QualityIntelligenceService, days: int
) -> JSONResponse:
    """Handle quality insights API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        insights = intelligence_service.generate_comprehensive_insights(days=days)

        return JSONResponse(
            {
                "status": "success",
                "data": insights.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_pattern_analysis_request(
    intelligence_service: QualityIntelligenceService, days: int
) -> JSONResponse:
    """Handle pattern analysis API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        patterns = intelligence_service.identify_patterns(days=days)

        return JSONResponse(
            {
                "status": "success",
                "data": patterns,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_comprehensive_analysis_request(
    intelligence_service: QualityIntelligenceService, request: dict
) -> JSONResponse:
    """Handle comprehensive analysis API request."""
    try:
        days = request.get("days", 30)

        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        results = await _build_comprehensive_analysis_results(
            intelligence_service, request, days
        )

        return JSONResponse(
            {
                "status": "success",
                "data": results,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _build_comprehensive_analysis_results(
    intelligence_service: QualityIntelligenceService, request: dict, days: int
) -> dict[str, t.Any]:
    """Build comprehensive analysis results based on request parameters."""
    results = {}

    if request.get("include_anomalies", True):
        results["anomalies"] = [
            anomaly.to_dict()
            for anomaly in intelligence_service.detect_anomalies(days=days)
        ]

    if request.get("include_predictions", True):
        insights = intelligence_service.generate_comprehensive_insights(days=days)
        results["insights"] = insights.to_dict()

        # Generate specific predictions
        predictions = {}
        for metric in ("quality_score", "test_coverage", "hook_duration"):
            pred = intelligence_service.generate_advanced_predictions(
                metric, horizon_days=7
            )
            if pred:
                predictions[metric] = pred.to_dict()
        results["predictions"] = predictions

    if request.get("include_patterns", True):
        results["patterns"] = intelligence_service.identify_patterns(days=days)

    return results
