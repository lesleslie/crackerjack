# Dashboard HTML Template Extraction Strategy

**Created**: 2025-10-10
**Status**: 🔄 IN PROGRESS
**Target**: Reduce `_get_dashboard_html()` from 1,223 lines → <50 lines
**File**: `crackerjack/mcp/websocket/monitoring_endpoints.py` (lines 1713-2935)

## Analysis Summary

### Current State
- **Monolithic HTML function**: 1,223 lines of inline HTML/CSS/JavaScript
- **No separation of concerns**: Presentation logic mixed with application logic
- **Untestable**: Cannot unit test individual components
- **Unmaintainable**: 81x complexity limit violation

### Identified Sections

```
_get_dashboard_html() breakdown (1,223 lines total):
├── HTML Head (80 lines)
│   ├── Meta tags & title
│   ├── External scripts (D3.js v7, React 18)
│   └── Inline CSS styles (~80 lines)
├── HTML Body (93 lines)
│   ├── Metrics cards container
│   ├── Quality chart container
│   ├── Coverage chart container
│   ├── Health chart container
│   ├── Alerts panel
│   ├── ML Intelligence section
│   │   ├── Anomalies panel
│   │   ├── Predictions panel
│   │   └── Patterns panel
│   ├── Dependency Graph section
│   │   ├── Load button & controls
│   │   ├── Filter dropdown
│   │   └── Graph container
│   └── Heat Map section (tabbed interface)
│       ├── Heat map visualization container
│       ├── Error patterns list
│       └── Severity breakdown
└── JavaScript (1,050 lines)
    ├── WebSocket Management (56 lines)
    │   ├── Connection state
    │   ├── Multiple WS connections (6 streams)
    │   └── Reconnection logic
    ├── Dashboard Updates (84 lines)
    │   ├── Message handling
    │   ├── Metrics rendering
    │   └── Alert handling
    ├── D3.js Visualizations (622 lines)
    │   ├── Quality chart (60 lines)
    │   ├── Dependency graph (140 lines)
    │   └── Heat map (422 lines)
    ├── Intelligence Panels (204 lines)
    │   ├── Anomalies rendering
    │   ├── Predictions rendering
    │   └── Patterns rendering
    ├── Error Patterns (174 lines)
    │   ├── Pattern list rendering
    │   └── Severity breakdown
    └── Initialization (10 lines)
```

## Template Architecture

### Directory Structure

```
crackerjack/
├── templates/
│   ├── dashboard/
│   │   ├── base.html.j2                 # Main layout with WebSocket setup
│   │   ├── metrics_cards.html.j2        # Top-level metric cards
│   │   ├── charts_section.html.j2       # Quality/Coverage/Health charts
│   │   ├── intelligence_section.html.j2 # ML anomalies/predictions/patterns
│   │   ├── dependency_section.html.j2   # Dependency graph & controls
│   │   └── heatmap_section.html.j2      # Error heat map & patterns
│   ├── components/
│   │   ├── metric_card.html.j2          # Reusable metric card
│   │   ├── alert_item.html.j2           # Single alert item
│   │   ├── anomaly_item.html.j2         # Single anomaly item
│   │   ├── error_pattern.html.j2        # Error pattern card
│   │   └── chart_container.html.j2      # Generic D3 chart wrapper
│   └── layouts/
│       └── websocket_base.html.j2       # WebSocket-enabled base
├── static/
│   ├── css/
│   │   └── dashboard.css                # Extracted CSS styles
│   └── js/
│       ├── dashboard_core.js            # WebSocket & state management
│       ├── dashboard_charts.js          # D3.js visualizations
│       ├── dashboard_intelligence.js    # ML panels
│       └── dashboard_heatmap.js         # Heat map rendering
└── services/
    └── template_service.py              # Jinja2 rendering service
```

### Component Breakdown

#### 1. Base Template (`dashboard/base.html.j2`)

**Responsibility**: Page structure, external dependencies, script loading

**Lines Saved**: ~100

```jinja2
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/css/dashboard.css') }}">
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://unpkg.com/react@18/umd/react.development.js"></script>
</head>
<body>
    <div class="dashboard-container">
        {% block content %}{% endblock %}
    </div>
    <script src="{{ url_for('static', path='/js/dashboard_core.js') }}"></script>
    <script src="{{ url_for('static', path='/js/dashboard_charts.js') }}"></script>
    <script src="{{ url_for('static', path='/js/dashboard_intelligence.js') }}"></script>
    <script src="{{ url_for('static', path='/js/dashboard_heatmap.js') }}"></script>
</body>
</html>
```

#### 2. Metrics Cards (`dashboard/metrics_cards.html.j2`)

**Responsibility**: Top-level KPI display

**Lines Saved**: ~20

**Reuses**: `components/metric_card.html.j2`

```jinja2
<div id="metrics-cards" class="metrics-container">
    {% for metric in metrics %}
        {% include 'components/metric_card.html.j2' with context %}
    {% endfor %}
</div>
```

#### 3. Charts Section (`dashboard/charts_section.html.j2`)

**Responsibility**: D3.js chart containers

**Lines Saved**: ~30

```jinja2
<div class="charts-row">
    <div id="quality-chart" class="chart-container">
        <h3>Quality Score Trend</h3>
    </div>
    <div id="coverage-chart" class="chart-container">
        <h3>Test Coverage</h3>
    </div>
    <div id="health-chart" class="chart-container">
        <h3>System Health</h3>
    </div>
</div>
```

#### 4. Intelligence Section (`dashboard/intelligence_section.html.j2`)

**Responsibility**: ML-powered insights panels

**Lines Saved**: ~40

```jinja2
<div class="intelligence-section">
    <h2>🤖 ML Intelligence</h2>
    <div class="intelligence-grid">
        <div id="anomalies-panel" class="intelligence-panel">
            <h3>🚨 Anomalies</h3>
        </div>
        <div id="predictions-panel" class="intelligence-panel">
            <h3>📈 Predictions</h3>
        </div>
        <div id="patterns-panel" class="intelligence-panel">
            <h3>🔗 Patterns</h3>
        </div>
    </div>
</div>
```

#### 5. Dependency Section (`dashboard/dependency_section.html.j2`)

**Responsibility**: Dependency graph visualization

**Lines Saved**: ~35

```jinja2
<div class="dependency-section">
    <h2>📦 Dependency Analysis</h2>
    <div class="graph-controls">
        <button id="load-dependency-graph" onclick="loadDependencyGraph()">
            Load Dependency Graph
        </button>
        <select id="graph-filter" onchange="applyGraphFilter()" disabled>
            <option value="">All Types</option>
            <option value="module">Modules</option>
            <option value="class">Classes</option>
            <option value="function">Functions</option>
        </select>
        <label>
            <input type="checkbox" id="include-external" onchange="applyGraphFilter()" disabled>
            Include External
        </label>
    </div>
    <div id="dependency-graph" class="graph-container"></div>
</div>
```

#### 6. Heat Map Section (`dashboard/heatmap_section.html.j2`)

**Responsibility**: Error heat map with tabbed interface

**Lines Saved**: ~60

```jinja2
<div class="heatmap-section">
    <h2>🔥 Error Heat Map</h2>

    <div class="heatmap-controls">
        <select id="heatmap-type" onchange="updateHeatMap()">
            <option value="file">By File</option>
            <option value="severity">By Severity</option>
            <option value="temporal">By Time</option>
        </select>
        <input type="number" id="analysis-days" value="7" min="1" max="30"
               onchange="updateHeatMap()">
        <input type="number" id="time-buckets" value="24" min="4" max="48"
               onchange="updateTemporalHeatMap()" disabled>
    </div>

    <div class="tab-buttons">
        <button class="tab-button active" onclick="showHeatMapTab('heatmap')">Heat Map</button>
        <button class="tab-button" onclick="showHeatMapTab('patterns')">Error Patterns</button>
        <button class="tab-button" onclick="showHeatMapTab('severity')">Severity Analysis</button>
    </div>

    <div id="heatmap-tab" class="tab-content active">
        <div id="error-heatmap"></div>
    </div>
    <div id="patterns-tab" class="tab-content">
        <div id="error-patterns-list"></div>
    </div>
    <div id="severity-tab" class="tab-content">
        <div id="severity-breakdown"></div>
    </div>
</div>
```

### JavaScript Extraction

#### 1. Core (`static/js/dashboard_core.js`)

**Responsibility**: WebSocket management, state, message routing

**Lines**: ~150

**Key Functions**:
- `connect()` - Initialize WebSocket connections (6 streams)
- `handleMessage()` - Route incoming messages
- `updateConnectionStatus()` - Connection indicator
- `connectIntelligenceStreams()` - ML WebSocket setup

#### 2. Charts (`static/js/dashboard_charts.js`)

**Responsibility**: D3.js visualizations

**Lines**: ~200

**Key Functions**:
- `renderQualityChart()` - Quality score line chart
- `renderCoverageChart()` - Coverage area chart
- `renderHealthChart()` - System health gauge

#### 3. Intelligence (`static/js/dashboard_intelligence.js`)

**Responsibility**: ML panels rendering

**Lines**: ~180

**Key Functions**:
- `renderAnomaliesPanel()` - Anomaly detection display
- `renderPredictionsPanel()` - Predictions & recommendations
- `renderPatternsPanel()` - Pattern correlation display

#### 4. Heat Map (`static/js/dashboard_heatmap.js`)

**Responsibility**: Heat map & error pattern visualization

**Lines**: ~520

**Key Functions**:
- `renderHeatMap()` - D3.js heat map with color scales
- `renderErrorPatterns()` - Error pattern cards
- `renderSeverityBreakdown()` - Severity distribution chart
- `updateHeatMap()` - Filter and refresh

### CSS Extraction

**File**: `static/css/dashboard.css`

**Lines**: ~80

**Sections**:
- Base styles (body, containers)
- Metric cards (`.metric-card`, `.metric-value`, `.metric-label`)
- Charts (`.chart-container`, SVG styles)
- Intelligence panels (`.intelligence-grid`, `.intelligence-panel`)
- Heat map (`.heatmap-section`, `.tab-button`, `.tab-content`)
- Trend indicators (`.trend-improving`, `.trend-declining`, `.trend-stable`)

## Template Service Implementation

### Service Class

**File**: `crackerjack/services/template_service.py`

**Responsibility**: Jinja2 template rendering with data preparation

```python
"""Jinja2 template rendering service for dashboard HTML generation."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


class TemplateService:
    """Service for rendering Jinja2 templates with dashboard data."""

    def __init__(self, template_dir: Path | None = None) -> None:
        """Initialize Jinja2 environment.

        Args:
            template_dir: Optional template directory override
        """
        if template_dir is None:
            # Default to templates/ in project root
            template_dir = Path(__file__).parent.parent / "templates"

        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml", "j2"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_dashboard(self, data: dict[str, Any]) -> str:
        """Render the complete monitoring dashboard.

        Args:
            data: Dashboard data dictionary with metrics, alerts, etc.

        Returns:
            Rendered HTML string
        """
        template = self.env.get_template("dashboard/base.html.j2")
        return template.render(**data)

    def render_metrics_cards(self, metrics: list[dict[str, Any]]) -> str:
        """Render metric cards section.

        Args:
            metrics: List of metric dictionaries

        Returns:
            Rendered HTML string
        """
        template = self.env.get_template("dashboard/metrics_cards.html.j2")
        return template.render(metrics=metrics)

    def render_intelligence_section(
        self,
        anomalies: list[dict[str, Any]],
        predictions: dict[str, Any],
        patterns: dict[str, Any],
    ) -> str:
        """Render ML intelligence section.

        Args:
            anomalies: List of detected anomalies
            predictions: Prediction insights
            patterns: Pattern analysis results

        Returns:
            Rendered HTML string
        """
        template = self.env.get_template("dashboard/intelligence_section.html.j2")
        return template.render(
            anomalies=anomalies,
            predictions=predictions,
            patterns=patterns,
        )


def get_template_service() -> TemplateService:
    """Get singleton template service instance.

    Returns:
        TemplateService instance
    """
    return TemplateService()
```

### Function Replacement

**Before** (1,223 lines):
```python
def _get_dashboard_html() -> str:
    """Generate the monitoring dashboard HTML."""
    return """<!DOCTYPE html>
<html lang="en">
...
    # 1,223 lines of inline HTML/CSS/JavaScript
...
</html>
    """
```

**After** (<50 lines):
```python
def _get_dashboard_html() -> str:
    """Generate the monitoring dashboard HTML using templates.

    Returns:
        Rendered dashboard HTML
    """
    template_service = get_template_service()

    # Prepare data for template (this replaces inline data)
    data = _prepare_dashboard_data()

    # Render using Jinja2 templates
    return template_service.render_dashboard(data)


def _prepare_dashboard_data() -> dict[str, Any]:
    """Prepare data dictionary for dashboard template.

    Returns:
        Dictionary with all dashboard data
    """
    return {
        "title": "Crackerjack Monitoring Dashboard",
        "metrics": [
            {
                "label": "Quality Score",
                "value": "{{ currentMetrics.quality_score }}",
                "trend": "{{ currentMetrics.trend_direction }}",
            },
            {
                "label": "Test Coverage",
                "value": "{{ currentMetrics.test_coverage }}%",
                "trend": "improving",
            },
            # ... additional metrics
        ],
        "websocket_url": "/ws/dashboard/overview",
        "static_url": "/static",
    }
```

## Implementation Plan

### Phase 1: Infrastructure Setup (Days 1-2)

**Tasks**:
1. Create `templates/` directory structure
2. Create `static/css/` and `static/js/` directories
3. Implement `TemplateService` class
4. Add Jinja2 dependency to `pyproject.toml`

**Validation**:
- Template service initializes correctly
- Template directories exist and are loadable
- Basic template rendering works

### Phase 2: CSS Extraction (Day 3)

**Tasks**:
1. Extract inline CSS from lines 1715-1793
2. Create `static/css/dashboard.css`
3. Organize CSS by component
4. Add CSS minification (optional)

**Validation**:
- CSS file loads in browser
- All styles render correctly
- No visual regressions

### Phase 3: JavaScript Extraction (Days 4-6)

**Tasks**:
1. Extract WebSocket management → `dashboard_core.js`
2. Extract D3.js charts → `dashboard_charts.js`
3. Extract ML intelligence → `dashboard_intelligence.js`
4. Extract heat map → `dashboard_heatmap.js`
5. Handle JavaScript module dependencies

**Validation**:
- All JavaScript functions work
- WebSocket connections establish
- Charts render correctly
- No JavaScript errors in console

### Phase 4: HTML Template Extraction (Days 7-9)

**Tasks**:
1. Create `base.html.j2` with page structure
2. Create section templates (metrics, charts, intelligence, etc.)
3. Create reusable components (metric_card, alert_item, etc.)
4. Wire up template inheritance

**Validation**:
- Templates render without errors
- Data binding works correctly
- All sections display properly

### Phase 5: Integration & Testing (Days 10-12)

**Tasks**:
1. Replace `_get_dashboard_html()` with template call
2. Add unit tests for `TemplateService`
3. Add integration tests for template rendering
4. Add visual regression tests (optional)
5. Performance testing (template rendering time)

**Validation**:
- Zero functional changes (dashboard identical)
- All tests passing
- Template rendering <10ms
- Dashboard loads successfully

### Phase 6: Documentation & Cleanup (Day 13)

**Tasks**:
1. Document template structure
2. Add template usage examples
3. Create template development guide
4. Remove old inline HTML function
5. Update monitoring endpoint documentation

**Validation**:
- Documentation complete
- Old code removed
- No dead code remaining

## Success Criteria

- ✅ Function reduced from 1,223 lines → <50 lines (96% reduction)
- ✅ All templates <100 lines each
- ✅ Components reusable across dashboards
- ✅ 100% test coverage on templates
- ✅ Zero functionality changes (visual identical)
- ✅ Template rendering time <10ms
- ✅ No JavaScript errors
- ✅ All WebSocket connections working
- ✅ All D3.js charts rendering correctly
- ✅ ML intelligence panels functional

## Testing Strategy

### Unit Tests

**Test Coverage**:
1. **TemplateService initialization**: Verify template directory loading
2. **Template rendering**: Each template renders without errors
3. **Data binding**: Template variables populate correctly
4. **Component reusability**: Metric card component works in different contexts

**Example Test**:
```python
def test_template_service_renders_dashboard():
    service = TemplateService()
    data = {"title": "Test Dashboard", "metrics": []}
    html = service.render_dashboard(data)

    assert "Test Dashboard" in html
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html
```

### Integration Tests

**Test Coverage**:
1. **Full dashboard rendering**: Complete HTML generation with real data
2. **WebSocket URL generation**: Correct URLs in rendered HTML
3. **Static asset URLs**: CSS/JS files referenced correctly

### Visual Regression Tests

**Test Coverage** (Optional):
1. Screenshot comparison (before/after)
2. Element positioning verification
3. Chart rendering consistency

## Risk Mitigation

### Risk 1: Template Rendering Errors

**Mitigation**: Extensive unit tests, template syntax validation

### Risk 2: JavaScript Breaking After Extraction

**Mitigation**: Incremental extraction, continuous testing, browser console monitoring

### Risk 3: WebSocket Connections Failing

**Mitigation**: Integration tests, manual WebSocket testing, connection monitoring

### Risk 4: D3.js Charts Not Rendering

**Mitigation**: Visual regression tests, manual chart verification, D3.js version pinning

### Risk 5: Performance Regression

**Mitigation**: Template caching, rendering benchmarks, performance profiling

## Performance Considerations

### Template Caching

**Strategy**: Cache compiled templates in production

```python
# Jinja2 auto-caches compiled templates
# Additional caching for rendered HTML (if data is static):

from functools import lru_cache

@lru_cache(maxsize=1)
def _get_cached_dashboard_base() -> str:
    """Cache base dashboard HTML structure."""
    template_service = get_template_service()
    return template_service.env.get_template("dashboard/base.html.j2").module
```

### Expected Performance

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Function Lines** | 1,223 | <50 | -96% |
| **Rendering Time** | ~1ms (string return) | <10ms (template render) | -9ms |
| **Maintainability** | Unmaintainable | Excellent | ✅ |
| **Testability** | Untestable | 100% coverage | ✅ |
| **Reusability** | None | High | ✅ |

## Timeline

**Total Duration**: 13 days (2 work weeks with buffer)

**Critical Path**:
1. Days 1-2: Infrastructure
2. Days 3-6: CSS + JavaScript extraction
3. Days 7-9: HTML template extraction
4. Days 10-12: Integration & testing
5. Day 13: Documentation

**Parallel Work Opportunities**:
- CSS extraction can happen alongside JavaScript extraction
- Template creation can start before JavaScript is fully extracted
- Testing can begin as soon as individual templates are created

## Conclusion

This strategy provides a comprehensive, incremental approach to decomposing the massive 1,223-line HTML function into modular, testable, maintainable Jinja2 templates. The result will be:

- **96% code reduction** in the function (1,223 → <50 lines)
- **Modular architecture** with reusable components
- **100% test coverage** on all templates
- **Zero visual changes** (identical dashboard rendering)
- **Improved maintainability** (templates are self-documenting)
- **Better developer experience** (templates hot-reload in development)

---

**Next Action**: Begin Phase 1 - Infrastructure Setup
