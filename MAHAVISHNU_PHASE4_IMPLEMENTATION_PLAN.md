# Mahavishnu Phase 4 Implementation Plan

## Overview
Task #14: Extend Mahavishnu Integration with Git analytics tools for cross-project metrics and WebSocket broadcasting for real-time dashboards.

## Requirements Analysis

### Current State
- **Existing**: `/crackerjack/integration/mahavishnu_integration.py` - Core aggregator with basic dashboard/health/pattern support
- **Existing**: `/crackerjack/mcp/tools/mahavishnu_tools.py` - MCP tools for dashboard/health/pattern/velocity
- **Existing**: `/crackerjack/memory/git_metrics_collector.py` - Comprehensive Git metrics collection
- **Existing**: `/crackerjack/memory/git_metrics_storage.py` - SQLite storage for Git metrics
- **Existing**: `/crackerjack/websocket/server.py` - WebSocket server with broadcasting

### Implementation Plan

#### 1. Extend `mahavishnu_integration.py` (~150 additional lines)
**Status**: Already exists at `/Users/les/Projects/crackerjack/crackerjack/integration/mahavishnu_integration.py`

**Changes Required**:
- Add `MahavishnuConfig` fields for Git metrics:
  - `git_metrics_enabled: bool`
  - `git_metrics_db_path: Path`
  - `portfolio_repos: list[str]`
  - `dashboard_refresh_interval: int`
- Extend `MahavishnuAggregator` methods:
  - `get_portfolio_velocity_dashboard()` - Aggregate across all portfolio repos
  - `get_merge_pattern_analysis()` - Analyze rebase frequency, conflict patterns
  - `propagate_best_practices()` - Find and share best practices across projects
- Add caching for cross-project queries

#### 2. Create `/crackerjack/mahavishnu/mcp/tools/git_analytics.py` (~250 lines)
**Status**: NEW FILE

**Structure**:
```python
# Directory structure:
crackerjack/
  mahavishnu/
    __init__.py
    mcp/
      __init__.py
      tools/
        git_analytics.py  # NEW - Portfolio analytics tools
```

**MCP Tools to Implement**:
1. `get_portfolio_velocity_dashboard(project_paths, days_back)` - Portfolio-wide metrics
2. `analyze_merge_patterns(project_paths, days_back)` - Rebase/merge pattern analysis
3. `get_best_practices_propagation(project_paths)` - Best practice discovery
4. `get_repository_comparison(repo_paths)` - Side-by-side comparison
5. `get_cross_project_conflicts(project_paths)` - Detect common conflict files

#### 3. Update Configuration
**File**: `/crackerjack/config/settings.py`

Add to `CrackerjackSettings`:
```python
class MahavishnuSettings(Settings):
    enabled: bool = False
    git_metrics_enabled: bool = True
    git_metrics_db_path: str = ".crackerjack/git_metrics.db"
    portfolio_repos: list[str] = []
    websocket_enabled: bool = False
    websocket_host: str = "127.0.0.1"
    websocket_port: int = 8686
    dashboard_refresh_interval: int = 300  # 5 minutes
```

#### 4. WebSocket Broadcasting
**Files to extend**:
- `/crackerjack/websocket/server.py` - Add Mahavishnu-specific event methods
- `/crackerjack/integration/mahavishnu_integration.py` - Use broadcaster for real-time updates

**Event Types**:
- `MAHAVISHNU_DASHBOARD_UPDATED` - Portfolio dashboard refresh
- `MAHAVISHNU_HEALTH_ALERT` - Repository health critical alert
- `MAHAVISHNU_PATTERN_DETECTED` - Cross-project pattern detected
- `MAHAVISHNU_BEST_PRACTICE` - Best practice discovered

#### 5. Documentation
Create `/docs/features/MAHAVISHNU_INTEGRATION.md`:
- Architecture overview
- Configuration guide
- MCP tools reference
- WebSocket event types
- Usage examples

## Implementation Details

### Protocol-Based Design
Follow crackerjack architecture:
- Import protocols from `models/protocols.py`
- Constructor injection for dependencies
- No global singletons

### WebSocket Integration
Use existing `CrackerjackWebSocketServer`:
- Already has `broadcast_to_room()` method
- Already supports mcp-common WebSocketProtocol
- Extend with Mahavishnu-specific rooms:
  - `mahavishnu:global` - Portfolio-wide updates
  - `mahavishnu:repo:{name}` - Repository-specific updates

### Git Metrics Integration
Leverage existing `GitMetricsCollector`:
- Already collects commit/branch/merge metrics
- Already stores to SQLite
- Query for cross-project aggregation

## Dependencies
No new dependencies required:
- `mcp_common` - Already integrated for WebSocket
- `pydantic_settings` - Already in settings
- SQLite - Standard library

## Testing Strategy
1. Unit tests for each new aggregator method
2. Integration tests for WebSocket broadcasting
3. MCP tool tests with mock repositories
4. Cross-project aggregation tests

## Success Criteria
- [ ] Portfolio velocity dashboard aggregates 5+ repositories
- [ ] Merge pattern analysis detects rebase vs. merge patterns
- [ ] Best practice propagation finds shared patterns
- [ ] WebSocket broadcasts dashboard updates in real-time
- [ ] Configuration loaded from settings/crackerjack.yaml
- [ ] MCP tools return valid JSON responses

## Files to Create/Modify

### New Files (~400 lines total)
1. `/crackerjack/mahavishnu/__init__.py` - Package init (~5 lines)
2. `/crackerjack/mahavishnu/mcp/__init__.py` - MCP package init (~5 lines)
3. `/crackerjack/mahavishnu/mcp/tools/__init__.py` - Tools package init (~5 lines)
4. `/crackerjack/mahavishnu/mcp/tools/git_analytics.py` - Analytics tools (~250 lines)
5. `/docs/features/MAHAVISHNU_INTEGRATION.md` - Documentation (~150 lines)

### Modified Files (~200 lines)
1. `/crackerjack/integration/mahavishnu_integration.py` - Extend aggregator (~150 lines)
2. `/crackerjack/config/settings.py` - Add MahavishnuSettings (~10 lines)
3. `/crackerjack/websocket/server.py` - Add broadcast methods (~40 lines)

**Total**: ~600 lines (400 new + 200 modified)

## Implementation Order
1. Create directory structure and __init__ files
2. Implement git_analytics.py MCP tools
3. Extend mahavishnu_integration.py aggregator
4. Update settings.py with MahavishnuSettings
5. Extend websocket server with Mahavishnu events
6. Create documentation
7. Run quality gates and tests

## Notes
- Use `from datetime import datetime, timedelta` for time handling
- Use `from pathlib import Path` for path handling
- Use async/await for all aggregator methods
- Cache results with TTL to avoid expensive re-computation
- Use `logger.debug()` for verbose, `logger.info()` for operational
