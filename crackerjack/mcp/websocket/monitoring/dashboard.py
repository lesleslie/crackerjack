"""Dashboard HTML rendering for monitoring endpoints.

This module provides the HTML dashboard endpoint for the monitoring system.
"""

from fastapi.responses import HTMLResponse

from crackerjack.ui.dashboard_renderer import render_monitoring_dashboard


async def get_dashboard_html() -> HTMLResponse:
    """Serve the monitoring dashboard HTML."""
    return HTMLResponse(_get_dashboard_html())


def _get_dashboard_html() -> str:
    """Generate the monitoring dashboard HTML."""
    return render_monitoring_dashboard()
