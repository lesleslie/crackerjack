# Git Metrics Collector - Implementation Plan

## Overview
Create `crackerjack/memory/git_metrics_collector.py` to parse git log output and calculate development metrics for time-series storage.

## Architecture Decisions

### 1. Dependency Strategy
- **Primary**: GitPython (not currently in dependencies)
- **Fallback**: subprocess with `SecureSubprocessExecutor` (already in codebase)
- **Implementation**: Try import GitPython, fallback to secure subprocess

### 2. Data Models
Use dataclasses for type safety and clarity:
- `CommitData`: Raw commit information
- `BranchActivity`: Branch creation/deletion events
- `MergePattern`: Merge and rebase detection
- `CommitMetrics`: Velocity calculations
- `BranchMetrics`: Switch frequency
- `MergeMetrics`: Conflict rates
- `VelocityDashboard`: Aggregated metrics

### 3. Git Commands to Parse
Using secure subprocess pattern from `crackerjack/services/secure_subprocess.py`:
```bash
git log --pretty=format:'%H|%ai|%an|%ae|%s' --date=iso
git branch -vv
git reflog show --date=iso
git log --merges --oneline
git log --grep="conflict" --oneline
```

### 4. Conventional Commits Detection
Pattern matching for:
- feat:, fix:, docs:, style:, refactor:, test:, chore:, perf:, ci:, build:
- BREAKING CHANGE: footer
- Scopes in parentheses: feat(scope): message

### 5. Time-Series Storage
Phase 1: SQLite tables for metrics (mirroring fix_strategy_storage.py)
Phase 2: Integration with Dhruva (not yet implemented)

## Implementation Steps

### Step 1: Create Data Models
Define all dataclasses with proper type hints

### Step 2: Git Repository Interface
Create `_GitRepository` protocol with GitPython/subprocess variants

### Step 3: Metrics Calculation Logic
Implement velocity, frequency, and pattern detection

### Step 4: Conventional Commit Parser
Regex-based detection following conventionalcommits.org spec

### Step 5: Time-Series Storage
SQLite schema for metrics storage

### Step 6: Public API
`GitMetricsCollector` class with all required methods

## Security Considerations
- Use `SecureSubprocessExecutor` for all git commands
- Validate repository paths (prevent path traversal)
- Sanitize git ref arguments
- Set reasonable timeouts (60s default)

## Performance Optimization
- Batch git log parsing (single call for all commits)
- Cache reflog data (expensive to parse)
- Lazy loading of metrics (calculate on demand)
- SQLite indexes on timestamp fields

## Testing Strategy
- Mock git command output
- Test with real git repository
- Validate conventional commit detection
- Test edge cases (empty repos, no branches, etc.)

## Dependencies
- **Existing**: subprocess, sqlite3, dataclasses, pathlib, re
- **Optional**: GitPython (not adding to pyproject.toml yet)
- **No new dependencies required** (use subprocess fallback)

## File Structure
```
crackerjack/memory/
├── git_metrics_collector.py  (NEW)
├── git_metrics_schema.sql     (NEW - SQLite schema)
├── __init__.py                (UPDATE - export new classes)
├── fix_strategy_storage.py    (EXISTING)
├── fix_strategy_schema.sql    (EXISTING)
└── ...
```

## Success Criteria
- ✅ Parse git log output correctly
- ✅ Detect merge/rebase operations
- ✅ Calculate commit velocity (hourly/daily/weekly)
- ✅ Detect conventional commits
- ✅ Store metrics in SQLite
- ✅ Secure subprocess execution
- ✅ Type-safe API (100% type hints)
- ✅ Complexity ≤15 per function
