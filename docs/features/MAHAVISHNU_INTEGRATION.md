# Mahavishnu Integration

## Overview

Mahavishnu is a cross-project Git analytics system that provides portfolio-wide metrics, health monitoring, and best practice discovery across multiple repositories. It aggregates Git metrics from individual repositories to enable portfolio-level insights and real-time dashboards.

## Architecture

### Components

```
crackerjack/
├── integration/
│   └── mahavishnu_integration.py    # Core aggregator with WebSocket support
├── mahavishnu/
│   └── mcp/
│       └── tools/
│           └── git_analytics.py      # MCP tools for Git analytics
├── memory/
│   ├── git_metrics_collector.py       # Git metrics collection
│   └── git_metrics_storage.py        # SQLite storage
└── websocket/
    └── server.py                    # WebSocket broadcasting
```

## Configuration

### Enable in `settings/crackerjack.yaml`

```yaml
mahavishnu:
  enabled: true
  git_metrics_enabled: true
  git_metrics_db_path: ".crackerjack/git_metrics.db"
  portfolio_repos:
    - "/Users/les/Projects/crackerjack"
    - "/Users/les/Projects/mcp-common"
  websocket_enabled: true
  websocket_host: "127.0.0.1"
  websocket_port: 8686
  dashboard_refresh_interval: 300
```

## MCP Tools

### Available Tools

1. **get_portfolio_velocity_dashboard** - Portfolio-wide velocity metrics
1. **analyze_merge_patterns** - Merge/rebase pattern analysis
1. **get_best_practices_propagation** - Best practice discovery
1. **get_repository_comparison** - Side-by-side repository comparison
1. **get_cross_project_conflicts** - Conflict pattern detection

## WebSocket Events

- `dashboard_update` - Portfolio dashboard refresh
- `health_alert` - Repository health critical alert
- `pattern_detected` - Cross-project pattern detected
- `merge_analysis` - Merge pattern analysis
- `best_practices` - Best practice discovered

## Health Scoring

Health scores (0-100) are calculated from:

- Conventional Commit Compliance (30%)
- Commit Velocity (30%)
- Merge Conflict Rate (20%)
- Breaking Changes penalty (-5 each)

Risk Levels:

- 80-100: Low
- 60-79: Medium
- 40-59: High
- 0-39: Critical

## Programmatic Usage

```python
import asyncio
from crackerjack.integration.mahavishnu_integration import (
    MahavishnuAggregator,
    MahavishnuConfig,
)

async def main():
    config = MahavishnuConfig(
        db_path=".crackerjack/mahavishnu.db",
        websocket_enabled=True,
        websocket_port=8686,
    )

    aggregator = MahavishnuAggregator(config=config)
    await aggregator.initialize()

    dashboard = await aggregator.get_portfolio_velocity_dashboard(
        project_paths=["/path/to/repo1", "/path/to/repo2"],
        days_back=30,
    )

    print(f"Portfolio velocity: {dashboard.portfolio_velocity:.2f} commits/day")
    print(f"Average health: {dashboard.avg_health_score:.1f}/100")

asyncio.run(main())
```

## See Also

- [Git Metrics Storage](../reference/GIT_METRICS_STORAGE.md)
- [WebSocket Server](../reference/WEBSOCKET_SERVER.md)
