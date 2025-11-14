"""REST API endpoint registration.

This module provides registration functions for all REST API endpoints
including telemetry, metrics, intelligence, dependencies, and heatmap analysis.
"""

from .dependencies import register_dependency_api_endpoints
from .heatmap import register_heatmap_api_endpoints
from .intelligence import register_intelligence_api_endpoints
from .metrics import register_metrics_api_endpoints
from .telemetry import register_telemetry_api_endpoints

__all__ = [
    "register_telemetry_api_endpoints",
    "register_metrics_api_endpoints",
    "register_intelligence_api_endpoints",
    "register_dependency_api_endpoints",
    "register_heatmap_api_endpoints",
]
