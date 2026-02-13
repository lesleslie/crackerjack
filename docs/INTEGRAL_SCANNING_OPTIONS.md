# Incremental/Change-Based Scanning for Slow Hooks

## Context

**Problem**: Slow quality hooks (refurb, complexipy, skylos) run full repository scans on every execution, taking 10+ minutes even when only a few files changed.

**Goal**: Implement intelligent, change-based scanning that only analyzes modified files, reducing scan time from 10+ minutes to 30-60 seconds for typical commits.

**Tools Affected**:
- **refurb** (~290s): Python modernization suggestions (NOT obsolete - actively useful for Python 3.13+)
- **complexipy** (~605s): Cognitive complexity analysis
- **skylos** (~60s): Dead code detection (Rust-based, faster than vulture)

**Proposed Tool Strategy**:
- **Daily workflow**: Use fast alternatives (ruff for complexity, vulture for dead code)
- **Publish workflow**: Use full suite including skylos, refurb, complexipy
- **Incremental scans**: Change-based for all slow tools

---

## Option 1: Git-Diff-Based Incremental Scanning

### Approach
Scan only files changed since last successful run using git diff.

### Implementation
```python
# crackerjack/services/incremental_scanner.py

class IncrementalScanner:
    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path)
        self.marker_file = self.repo_path / ".crackerjack" / "last_scan_ref"

    def get_changed_files(self, base_ref: str = "HEAD~1") -> list[Path]:
        """Get files changed since base_ref."""
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", base_ref, "HEAD"],
            capture_output=True,
            text=True,
            cwd=self.repo_path
        )
        if result.returncode != 0:
            return []
        return [
            self.repo_path / line
            for line in result.stdout.strip().split("\n")
            if line and line.endswith(".py")
        ]

    def get_files_to_scan(self, tool_name: str) -> list[Path]:
        """Get files that need scanning for a specific tool."""
        changed = self.get_changed_files()
        if not changed:
            return []

        # Filter by file patterns relevant to each tool
        patterns = {
            "refurb": ["*.py"],
            "complexipy": ["*.py"],
            "skylos": ["*.py"],
        }

        import fnmatch
        matches = []
        for file in changed:
            if any(fnmatch.fnmatch(file.name, pat) for pat in patterns.get(tool_name, [])):
                matches.append(file)
        return matches
```

### Usage in Hooks
```python
# crackerjack/hooks/refurb_hook.py

async def run_refurb_incremental(options) -> HookResult:
    scanner = IncrementalScanner(pkg_path)
    files = scanner.get_files_to_scan("refurb")

    if not files:
        return HookResult(success=True, stdout="No changes to scan")

    # Run refurb only on changed files
    cmd = ["refurb", *map(str, files)]
    result = await run_command(cmd)
    return result
```

### Pros
- ✅ Simple implementation
- ✅ Based on proven git diff
- ✅ Fast for small commits
- ✅ Works with all git-based workflows

### Cons
- ❌ Can miss issues in files that changed due to refactoring
- ❌ Requires careful base_ref management
- ❌ Doesn't handle branch switching well

### Estimated Performance
- **Small commits** (<10 files): 10-30 seconds (vs 290s)
- **Medium commits** (10-50 files): 30-90 seconds
- **Large commits** (>50 files): Falls back to full scan

---

## Option 2: Marker-Based Incremental Scanning

### Approach
Track per-file scan markers/timestamps, only scan files modified since last scan.

### Implementation
```python
# crackerjack/services/marker_scanner.py

import sqlite3
from datetime import datetime
from pathlib import Path

class MarkerScanner:
    def __init__(self, repo_path: Path):
        self.db_path = repo_path / ".crackerjack" / "scan_markers.db"
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_markers (
                file_path TEXT PRIMARY KEY,
                tool_name TEXT,
                last_scan_time TEXT,
                last_scan_hash TEXT,
                UNIQUE(file_path, tool_name)
            )
        """)
        conn.commit()

    def get_files_needing_scan(self, tool_name: str, files: list[Path]) -> list[Path]:
        """Get files that need scanning based on modification time."""
        import hashlib

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        needs_scan = []
        for file in files:
            if not file.exists():
                continue

            # Get file modification time and hash
            mtime = file.stat().st_mtime
            file_hash = hashlib.md5(file.read_bytes()).hexdigest()

            # Check if file was scanned and unchanged
            cursor.execute(
                """
                SELECT last_scan_hash FROM file_markers
                WHERE file_path = ? AND tool_name = ?
                """,
                (str(file), tool_name)
            )
            row = cursor.fetchone()

            if not row or row[0] != file_hash:
                needs_scan.append(file)

        conn.close()
        return needs_scan

    def mark_scanned(self, tool_name: str, files: list[Path]):
        """Mark files as scanned."""
        import hashlib
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for file in files:
            if not file.exists():
                continue

            file_hash = hashlib.md5(file.read_bytes()).hexdigest()
            cursor.execute(
                """
                INSERT OR REPLACE INTO file_markers
                (file_path, tool_name, last_scan_time, last_scan_hash)
                VALUES (?, ?, ?, ?)
                """,
                (str(file), tool_name, datetime.now().isoformat(), file_hash)
            )

        conn.commit()
        conn.close()
```

### Usage in Hooks
```python
async def run_refurb_with_markers(options) -> HookResult:
    scanner = MarkerScanner(pkg_path)
    all_files = list(pkg_path.rglob("*.py"))

    # Get only files needing scan
    files_to_scan = scanner.get_files_needing_scan("refurb", all_files)

    if not files_to_scan:
        return HookResult(success=True, stdout="No changes since last scan")

    # Run refurb on changed files
    cmd = ["refurb", *map(str, files_to_scan)]
    result = await run_command(cmd)

    # Mark as scanned
    if result.success:
        scanner.mark_scanned("refurb", files_to_scan)

    return result
```

### Pros
- ✅ Accurate tracking of file changes
- ✅ No git dependency
- ✅ Handles branch switching correctly
- ✅ Can track tool-specific scans

### Cons
- ❌ Requires database management
- ❌ Database can become stale
- ❌ Need cleanup mechanism for deleted files

### Estimated Performance
- **Typical workflow** (<20 files changed): 15-45 seconds
- **After full scan**: Subsequent scans <30 seconds
- **Database overhead**: Minimal (~5ms per file)

---

## Option 3: Hybrid Approach (Git-Diff + Fallback)

### Approach
Use git-diff for daily workflows, with periodic full scans as fallback.

### Implementation
```python
# crackerjack/services/hybrid_scanner.py

class HybridScanner:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.marker_file = self.repo_path / ".crackerjack" / "last_full_scan"

    def get_scan_strategy(
        self,
        tool_name: str,
        force_full: bool = False
    ) -> tuple[str, list[Path]]:
        """
        Returns (strategy, files) where strategy is "incremental" or "full".

        Forces full scan if:
        - Last full scan was >7 days ago
        - force_full=True
        - Cannot determine git base
        """
        import time
        from datetime import datetime, timedelta

        # Check if we need a full scan
        if force_full:
            return self._get_full_scan_files(tool_name)

        if self.marker_file.exists():
            last_scan = datetime.fromtimestamp(self.marker_file.stat().st_mtime)
            if datetime.now() - last_scan > timedelta(days=7):
                return self._get_full_scan_files(tool_name)

        # Try incremental scan
        try:
            scanner = IncrementalScanner(self.repo_path)
            files = scanner.get_files_to_scan(tool_name)
            if files:
                return "incremental", files
        except Exception:
            pass

        # Fallback to full scan
        return self._get_full_scan_files(tool_name)

    def _get_full_scan_files(self, tool_name: str) -> tuple[str, list[Path]]:
        """Get all Python files for full scan."""
        files = list(self.repo_path.rglob("*.py"))
        # Update marker
        self.marker_file.touch()
        return "full", files
```

### Configuration
```yaml
# .crackerjack.yaml

incremental_scanning:
  enabled: true

  # Tools to use incremental scanning
  tools:
    - refurb
    - complexipy
    - skylos

  # Force full scan interval (days)
  full_scan_interval: 7

  # Maximum files for incremental scan
  incremental_threshold: 100

  # Publish workflow always does full scan
  publish_always_full: true
```

### Pros
- ✅ Best of both worlds
- ✅ Automatic fallback to full scan
- ✅ Configurable thresholds
- ✅ Safety net with periodic full scans

### Cons
- ❌ More complex logic
- ❌ More configuration options
- ❌ Still some overhead

### Estimated Performance
- **Daily workflow** (incremental): 20-60 seconds
- **Weekly full scan**: 10+ minutes (runs in background/CI)
- **Publish workflow**: Full scan (expected)

---

## Option 4: Pool-Based Parallel Scanning (Mahavishnu Integration)

### Approach
Use mahavishnu's pool management to distribute scanning across multiple worker processes.

### Architecture
```
┌─────────────────────────────────────────────────────────┐
│ Crackerjack Hook Executor                               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐      ┌──────────────────────────┐   │
│  │ File Scanner │ ───> │ Mahavishnu Pool Manager  │   │
│  └──────────────┘      └──────────────────────────┘   │
│                                 │                      │
│                                 ▼                      │
│                    ┌─────────────────────────┐         │
│                    │  Worker Pool (N=4-8)    │         │
│                    ├─────────────────────────┤         │
│                    │  Worker 1: refurb      │         │
│                    │  Worker 2: complexipy  │         │
│                    │  Worker 3: skylos      │         │
│                    │  Worker 4: vulture     │         │
│                    └─────────────────────────┘         │
└─────────────────────────────────────────────────────────┘
```

### Implementation
```python
# crackerjack/services/pool_scanner.py

class PoolBasedScanner:
    def __init__(self, pool_manager):
        """
        pool_manager: Mahavishnu pool manager instance
        """
        self.pool = pool_manager

    async def scan_with_pool(self, files: list[Path], tools: list[str]) -> dict:
        """
        Distribute scanning across worker pool.

        Each tool gets a dedicated worker for parallel execution.
        """
        tasks = {}
        for tool in tools:
            task = await self.pool.submit_task(
                func=self._run_tool_scan,
                tool_name=tool,
                files=files,
                priority="normal"
            )
            tasks[tool] = task

        # Wait for all scans to complete
        results = {}
        for tool, task in tasks.items():
            results[tool] = await task

        return results

    async def _run_tool_scan(self, tool_name: str, files: list[Path]) -> HookResult:
        """Run a single tool scan (executed in worker pool)."""
        cmd = self._get_tool_command(tool_name, files)
        return await run_command(cmd)
```

### Integration with Mahavishnu
```python
# Uses mahavishnu's task pools for:
# - Parallel tool execution
# - Worker lifecycle management
# - Result aggregation
# - Error handling and retries
```

### Pros
- ✅ Maximum parallelization
- ✅ Fault isolation (worker crashes don't affect others)
- ✅ Resource management (CPU, memory limits per worker)
- ✅ Can scale to large codebases
- ✅ Mahavishnu provides orchestration

### Cons
- ❌ Mahavishnu dependency
- ❌ More complex debugging
- ❌ Pool management overhead
- ❌ Need to ensure mahavishnu is running

### Estimated Performance
- **With 8 workers**: 3-4x speedup on multi-core systems
- **Full scan time**: 10+ minutes → 3-4 minutes
- **Incremental + pool**: 20-60 seconds → 10-20 seconds

---

## Recommended Implementation Strategy

### Phase 1: Quick Win (Option 1 - Git-Diff)
**Timeline**: 2-3 hours
**Impact**: 80% of workflows see 90% time reduction

1. Implement `IncrementalScanner` with git-diff
2. Update refurb, complexipy, skylos hooks to use it
3. Add configuration option to enable/disable
4. Test on typical commits

### Phase 2: Enhanced Tracking (Option 2 - Markers)
**Timeline**: 4-6 hours
**Impact**: More accurate, handles edge cases

1. Implement `MarkerScanner` with SQLite
2. Add migration from git-diff to markers
3. Implement cleanup for deleted files
4. Add admin commands for marker management

### Phase 3: Pool Integration (Option 4 - Mahavishnu)
**Timeline**: 6-8 hours
**Impact**: Maximum performance, best for large repos

1. Integrate with mahavishnu pool manager
2. Implement worker pool for tool execution
3. Add pool monitoring and debugging tools
4. Benchmark and optimize pool size

### Phase 4: Publish Workflow (Full Scans)
**Timeline**: 2-3 hours
**Impact**: Ensures quality for releases

1. Keep full scans for publish workflow
2. Add pre-publish validation gate
3. Generate comprehensive reports
4. Archive scan results

---

## Configuration Example

```yaml
# .crackerjack.yaml

scanning:
  # Default scanning mode
  mode: incremental  # incremental | full | hybrid

  # Incremental scanning configuration
  incremental:
    # Use git-diff based incremental scanning
    git_diff_enabled: true

    # Fallback to markers if git unavailable
    markers_enabled: false

    # Maximum files for incremental scan
    threshold: 100

    # Force full scan interval (days, 0 = never force)
    full_scan_interval_days: 7

  # Tool-specific configuration
  tools:
    refurb:
      enabled: true
      mode: incremental
      publish_mode: full

    complexipy:
      enabled: true
      mode: incremental
      publish_mode: full
      alternative: ruff  # Use ruff for daily workflow

    skylos:
      enabled: true
      mode: incremental
      publish_mode: full
      alternative: vulture  # Use vulture for daily workflow

  # Pool-based scanning (requires mahavishnu)
  pools:
    enabled: false  # Enable when mahavishnu is available
    workers: 8  # Number of parallel workers
    timeout: 300  # Per-tool timeout (seconds)

# Publish workflow configuration
publish:
  # Always do full scans before publishing
  full_scans: true

  # Required tools for publish
  required_tools:
    - refurb
    - complexipy
    - skylos
    - gitleaks
    - semgrep

  # Fail publish if tools fail
  fail_on_tool_failure: true
```

---

## Performance Estimates

### Before (Full Scans Always)
| Workflow | Time | Tools Run |
|----------|------|-----------|
| Daily commit | 10+ min | All tools |
| Small commit | 10+ min | All tools |
| Publish | 10+ min | All tools |

### After (Incremental Scans)
| Workflow | Time | Tools Run | Files Scanned |
|----------|------|-----------|---------------|
| Daily commit (small) | 30-60s | Incremental tools | 5-20 files |
| Daily commit (medium) | 60-90s | Incremental tools | 20-50 files |
| Daily commit (large) | 3-5 min | Full scan (fallback) | All files |
| Weekly full scan | 10+ min | All tools | All files |
| Publish | 10+ min | All tools | All files |

### After (Incremental + Pools)
| Workflow | Time | Speedup |
|----------|------|---------|
| Daily commit (small) | 10-20s | 30-60x faster |
| Daily commit (medium) | 20-30s | 20-40x faster |
| Weekly full scan | 3-4 min | 2.5-3x faster |
| Publish | 3-4 min | 2.5-3x faster |

---

## Open Questions for Consultants

1. **Git-Diff vs Markers**: Which approach is more reliable for your workflow?
2. **Full Scan Frequency**: How often should we force full scans? (Weekly? Bi-weekly?)
3. **Pool Integration**: Is mahavishnu available in all environments (CI, local, docker)?
4. **Tool Alternatives**: Are ruff/vulture acceptable substitutes for daily workflows?
5. **Publish Gate**: Should publish workflow fail if incremental scan was used (not full)?
6. **Cache Invalidation**: How do we handle branch switching, rebasing, cherry-picking?
7. **Monitoring**: What metrics should we track? (scan times, cache hit rates, etc.)
8. **Rollback**: If incremental scanning misses issues, how do we recover?

---

## Next Steps

1. **Review options** with team and consultants
2. **Choose approach** (recommend: Phase 1 → Phase 2 → Phase 4)
3. **Implement incrementally** (git-diff first, measure, then enhance)
4. **Integrate mahavishnu** when available for pool-based scanning
5. **Monitor and tune** based on actual usage patterns

---

**Prepared by**: Claude Sonnet 4.5
**Date**: 2026-02-13
**Status**: Ready for review
