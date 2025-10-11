"""Utilities for rendering the monitoring dashboard UI."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).with_suffix("").parent / "templates"


def _load_asset(filename: str) -> str:
    path = _TEMPLATE_DIR / filename
    if not path.exists():
        msg = f"Dashboard asset not found: {filename}"
        raise FileNotFoundError(msg)
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def render_monitoring_dashboard() -> str:
    """Render the monitoring dashboard HTML using cached assets."""
    html_template = _load_asset("monitoring_dashboard.html")
    css_styles = _load_asset("monitoring_dashboard.css")
    javascript_code = _load_asset("monitoring_dashboard.js")
    return html_template.format(
        css_styles=css_styles,
        javascript_code=javascript_code,
    )
