# Oneiric CLI Factory: Specification Refinement & Crackerjack Migration Plan

**Status:** READY FOR PEER REVIEW
**Created:** 2025-12-20
**Timeline:** Spec refinements during Phase 1 implementation; Crackerjack migration Week 2
**Approval Required:** Yes (holding for peer review before implementation)

______________________________________________________________________

## Executive Summary

This plan covers two parallel workstreams:

1. **Specification Refinement** - 8 refinements to `ONEIRIC_CLI_FACTORY_IMPLEMENTATION.md` based on user decisions and spec review findings
1. **Crackerjack Migration Plan** - Detailed 5-phase migration from ACB to Oneiric+mcp-common (Week 2, ~30 hours)

Both plans are designed to support the grand Oneiric migration strategy across all MCP servers.

______________________________________________________________________

## PLAN 1: Specification Refinement

### Overview

Refine the CLI factory specification based on:

- User decisions from Q&A (daemon mode, multi-instance, reload handler)
- Spec review findings (5 technical refinements)
- Implementation readiness improvements

**Timing:** During Phase 1 implementation (not blocking)

### Refinements Required (8 total)

| ID | Refinement | Priority | Section | Time | Status |
|----|------------|----------|---------|------|--------|
| R1 | CLI flag override implementation | P2 | §6 | 15m | Review finding |
| R2 | health_probe_handler parameter | P1 | §2 | 30m | User-requested |
| R3 | Restart race condition handling | P3 | §3 | 20m | Review finding |
| R4 | Logging initialization point | P3 | §2/§7 | 10m | Review finding |
| R5 | Enhanced weather example | P3 | Appendix | 20m | Review finding |
| R6 | Systemd integration (no daemon) | P1 | §10 | 30m | User-requested |
| R7 | Multi-instance documentation | P1 | §6 | 20m | User-requested |
| R8 | reload_handler parameter | P1 | §5 | 25m | User-requested |

**Total Effort:** ~2.5 hours (distributed across Phase 1 implementation)

**Priority Levels:**

- **P1** (User-requested): R2, R6, R7, R8 - Must include
- **P2** (Important): R1 - Should include
- **P3** (Polish): R3, R4, R5 - Nice to have

### Refinement Details

#### R1: CLI Flag Override Implementation (§6 Configuration)

**Location:** Add to §6 "Configuration Hierarchy"

**Current Gap:** Configuration hierarchy mentions CLI flags as highest priority, but doesn't show implementation pattern.

**Add:**

```python
class MCPServerCLIFactory:
    def _cmd_start(
        self,
        cache_root: Path | None = typer.Option(
            None, "--cache-root", help="Override cache directory"
        ),
        health_ttl: float | None = typer.Option(
            None, "--health-ttl", help="Override health TTL (seconds)"
        ),
        force: bool = typer.Option(False, "--force", help="Force start"),
        json_output: bool = typer.Option(False, "--json", help="JSON output"),
    ) -> None:
        """Start the MCP server."""
        # Apply CLI flag overrides to settings
        if cache_root is not None:
            self.settings.cache_root = cache_root
        if health_ttl is not None:
            self.settings.health_ttl_seconds = health_ttl

        # Rest of start logic...
```

**Impact:** Clarifies override pattern, enables all commands to support setting overrides.

______________________________________________________________________

#### R2: Health Probe Handler Parameter (§2 CLI Factory API)

**Location:** Add to §2 "CLI Factory API Architecture"

**Current Gap:** Health command mentions `--probe` but doesn't define server integration interface.

**Add to MCPServerCLIFactory.__init__:**

```python
def __init__(
    self,
    server_name: str,
    settings: MCPServerSettings | None = None,
    start_handler: Callable[[], None] | None = None,
    stop_handler: Callable[[int], None] | None = None,
    health_probe_handler: Callable[[], RuntimeHealthSnapshot] | None = None,  # NEW
):
    """Initialize CLI factory.

    Args:
        server_name: Server identifier
        settings: Optional custom settings
        start_handler: Optional custom start logic
        stop_handler: Optional custom stop logic
        health_probe_handler: Optional health probe for --health --probe
    """
    self.health_probe_handler = health_probe_handler
```

**Add to \_cmd_health:**

```python
def _cmd_health(self, probe: bool = False, ...):
    """Display server health."""
    if probe:
        if self.health_probe_handler is not None:
            # Run live health checks
            snapshot = self.health_probe_handler()
            write_runtime_health(self.settings.health_snapshot_path(), snapshot)
        else:
            logger.warning("No health probe handler configured, reading cached snapshot")
            snapshot = load_runtime_health(self.settings.health_snapshot_path())
    else:
        # Read cached snapshot
        snapshot = load_runtime_health(self.settings.health_snapshot_path())

    # Display snapshot...
```

**Impact:** Enables Oneiric LifecycleManager integration for live health checks.

______________________________________________________________________

#### R3: Restart Race Condition Handling (§3 Error Handling)

**Location:** Add to §3 "Error Handling & Recovery"

**Current Gap:** Restart does `stop() → start()` without validating PID cleanup.

**Add:**

```python
def _cmd_restart(
    self,
    timeout: int = typer.Option(10, "--timeout", help="Stop timeout (seconds)"),
    force: bool = typer.Option(False, "--force", help="Force restart"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Restart the MCP server (stop + start with validation)."""
    # Stop server
    self._cmd_stop(timeout=timeout, force=force, json_output=json_output)

    # Wait for PID file removal (max 5 seconds)
    pid_path = self.settings.pid_path()
    wait_start = time.time()
    while pid_path.exists() and (time.time() - wait_start) < 5.0:
        time.sleep(0.1)

    # If PID still exists after 5s
    if pid_path.exists():
        if force:
            logger.warning("PID file not removed after stop, forcing removal")
            pid_path.unlink(missing_ok=True)
        else:
            raise RuntimeError(
                f"PID file {pid_path} not removed after stop. Use --force to override."
            )

    # Start server
    self._cmd_start(force=force, json_output=json_output)
```

**Impact:** Prevents race conditions where start tries to create PID before stop finishes.

______________________________________________________________________

#### R4: Logging Initialization Point (§2 or §7)

**Location:** Add to §2 "CLI Factory API Architecture"

**Current Gap:** `configure_logging()` function exists but initialization point unclear.

**Add to MCPServerCLIFactory.__init__:**

```python
def __init__(self, ...):
    self.server_name = server_name
    self.settings = settings or MCPServerSettings.load(server_name)

    # Configure logging based on settings
    self.logger = configure_logging(
        level=self.settings.log_level,
        log_file=self.settings.log_file,
    )

    self.start_handler = start_handler
    self.stop_handler = stop_handler
```

**Impact:** Clarifies when logging is configured (factory initialization).

______________________________________________________________________

#### R5: Enhanced Weather Example (Appendix)

**Location:** Add to Appendix "Complete Example"

**Current Gap:** Weather server example doesn't demonstrate health probe integration.

**Add to WeatherServer class:**

```python
class WeatherServer:
    def get_health_snapshot(self) -> RuntimeHealthSnapshot:
        """Health probe for --health --probe.

        Runs live health checks and returns updated snapshot.
        """
        # Check API connectivity
        api_healthy = self._check_api_connection()

        # Check cache status
        cache_healthy = self._check_cache_status()

        return RuntimeHealthSnapshot(
            orchestrator_pid=os.getpid(),
            watchers_running=self.running,
            lifecycle_state={
                "weather_api": {
                    "healthy": api_healthy,
                    "last_check": datetime.now(UTC).isoformat(),
                },
                "cache": {
                    "healthy": cache_healthy,
                    "entries": len(self._cache),
                },
            },
        )

    def _check_api_connection(self) -> bool:
        """Test API connectivity."""
        try:
            response = httpx.get(f"{self.api_url}/health", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False

    def _check_cache_status(self) -> bool:
        """Validate cache is operational."""
        return hasattr(self, "_cache") and self._cache is not None
```

**Add to main():**

```python
factory = MCPServerCLIFactory(
    "weather-server",
    settings=settings,
    start_handler=start_handler,
    stop_handler=stop_handler,
    health_probe_handler=server.get_health_snapshot,  # NEW
)
```

**Impact:** Demonstrates complete health probe integration pattern.

______________________________________________________________________

#### R6: Systemd Integration Documentation (§10 Migration Guide)

**Location:** Add new subsection to §10 "Migration Guide"

**User Decision:** No daemon mode support (use systemd)

**Add:**

##### Production Deployment with Systemd

**Systemd Unit Template** (`/etc/systemd/system/mcp-server@.service`):

```ini
[Unit]
Description=%i MCP Server
After=network.target

[Service]
Type=simple
User=mcp
Group=mcp
WorkingDirectory=/opt/mcp-servers/%i
ExecStart=/opt/mcp-servers/%i/.venv/bin/python -m %i start
ExecStop=/opt/mcp-servers/%i/.venv/bin/python -m %i stop --timeout=30
Restart=on-failure
RestartSec=10s

# Security
PrivateTmp=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/mcp-servers/%i/.oneiric_cache

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=%i-mcp

[Install]
WantedBy=multi-user.target
```

**Usage:**

```bash
# Install service
sudo systemctl daemon-reload
sudo systemctl enable mcp-server@session-buddy
sudo systemctl start mcp-server@session-buddy

# Status check
sudo systemctl status mcp-server@session-buddy

# Logs
sudo journalctl -u mcp-server@session-buddy -f

# Reload config (SIGHUP)
sudo systemctl reload mcp-server@session-buddy
```

**Why No Daemon Mode:**

- Modern best practice: systemd/supervisord for process management
- Daemon mode is complex (stdio redirection, signal handling, double fork)
- Systemd provides better features (auto-restart, logging, resource limits)
- Containers don't need daemon mode (foreground execution preferred)

**Impact:** Documents production deployment pattern, justifies no daemon mode.

______________________________________________________________________

#### R7: Multi-Instance Documentation (§6 Configuration)

**Location:** Add new subsection to §6 "Configuration Hierarchy"

**User Decision:** Document multi-instance pattern using cache-root override

**Add:**

##### Running Multiple Server Instances

**Use Case:** Run multiple instances of the same MCP server with different configurations.

**Method 1: Separate Cache Directories**

```bash
# Instance 1 (Project A)
mcp-server start --cache-root=.cache/project-a

# Instance 2 (Project B)
mcp-server start --cache-root=.cache/project-b

# Each instance has isolated:
# - PID file: .cache/project-a/mcp_server.pid
# - Health snapshot: .cache/project-a/runtime_health.json
```

**Method 2: Systemd Template Units**

```bash
# Create separate working directories
/opt/mcp-servers/
├── session-buddy-project-a/
│   ├── settings/local.yaml  # cache_root: .cache/project-a
│   └── .venv/
└── session-buddy-project-b/
    ├── settings/local.yaml  # cache_root: .cache/project-b
    └── .venv/

# Start instances
sudo systemctl start mcp-server@session-buddy-project-a
sudo systemctl start mcp-server@session-buddy-project-b
```

**Method 3: YAML Configuration**

```yaml
# settings/project-a.yaml
server_name: session-buddy
cache_root: .cache/project-a
health_ttl_seconds: 60.0

# settings/project-b.yaml
server_name: session-buddy
cache_root: .cache/project-b
health_ttl_seconds: 120.0
```

**Key Considerations:**

- Each instance needs unique `cache_root`
- PID files must not collide
- Systemd handles process isolation automatically

**Impact:** Enables multi-tenant deployments, project-specific servers.

______________________________________________________________________

#### R8: Reload Handler Parameter (§5 Signal Handling)

**Location:** Add to §5 "Signal Handling"

**User Decision:** Add reload_handler parameter for SIGHUP config reload

**Add to SignalHandler.__init__:**

```python
class SignalHandler:
    def __init__(
        self,
        on_shutdown: Callable[[], None],
        on_reload: Callable[[], None] | None = None,
    ):
        """Initialize signal handler.

        Args:
            on_shutdown: Called on SIGTERM/SIGINT (graceful shutdown)
            on_reload: Optional callback for SIGHUP (config reload)
        """
        self.on_shutdown = on_shutdown
        self.on_reload = on_reload
```

**Add to MCPServerCLIFactory.__init__:**

```python
def __init__(
    self,
    server_name: str,
    settings: MCPServerSettings | None = None,
    start_handler: Callable[[], None] | None = None,
    stop_handler: Callable[[int], None] | None = None,
    health_probe_handler: Callable[[], RuntimeHealthSnapshot] | None = None,
    reload_handler: Callable[[], None] | None = None,  # NEW
):
    self.reload_handler = reload_handler
```

**Example Usage:**

```python
class WeatherServer:
    def reload_config(self):
        """Reload configuration on SIGHUP."""
        logger.info("Reloading configuration...")

        # Reload settings
        new_settings = WeatherServerSettings.load("weather-server")

        # Apply safe changes (can't change cache_root!)
        self.settings.log_level = new_settings.log_level
        self.settings.api_timeout = new_settings.api_timeout

        # Reconfigure logging
        configure_logging(level=new_settings.log_level)

        logger.info("Configuration reloaded successfully")


# In main():
factory = MCPServerCLIFactory(
    ...,
    reload_handler=server.reload_config,
)
```

**Signal Registration:**

```python
signal_handler = SignalHandler(
    on_shutdown=shutdown,
    on_reload=reload if self.reload_handler else None,
)
signal_handler.register()
```

**Impact:** Enables live config reloads (log level, timeouts) without restart.

______________________________________________________________________

### Implementation Strategy

**When:** During Phase 1 implementation (Week 1)

**How:**

1. Implement P1 refinements (R2, R6, R7, R8) first - 2 hours
1. Implement P2 refinements (R1) during API implementation - 15 min
1. Implement P3 refinements (R3, R4, R5) as polish - 50 min

**Validation:**

- Update tests for new parameters (health_probe_handler, reload_handler)
- Add multi-instance integration test
- Update example weather server with all features

**Documentation:**

- Update specification document with all refinements
- Add systemd deployment guide
- Update migration guide

______________________________________________________________________

## PLAN 2: Crackerjack Migration to Oneiric

### Overview

Migrate crackerjack from ACB-based architecture to Oneiric+mcp-common in 5 phases over Week 2.

**Scope:**

- Remove 55 MCP files (WebSocket/monitoring/dashboard)
- Remove 310 ACB imports
- Port 38 QA adapters to Oneiric
- Integrate Oneiric CLI factory
- Preserve all QA tooling functionality

**Timeline:** Week 2 (5 days, ~30 hours)
**Risk Level:** MODERATE-HIGH
**Reversibility:** YES (git rollback, feature flags)

### Critical Decisions

#### Decision 1: CLI Mapping Strategy

**Approach:** Hybrid (Factory + Custom Commands)

**Lifecycle Commands → Oneiric Factory:**

```bash
crackerjack start           # MCPServerCLIFactory
crackerjack stop            # MCPServerCLIFactory
crackerjack restart         # MCPServerCLIFactory
crackerjack status          # MCPServerCLIFactory
crackerjack health          # MCPServerCLIFactory (--probe supported)
```

**QA Commands → Custom Commands:**

```bash
crackerjack run-tests       # @app.command() - Custom
crackerjack analyze         # @app.command() - Custom
crackerjack qa-health       # @app.command() - Custom QA health
crackerjack benchmark       # @app.command() - Custom
```

**Breaking Changes:**

- `--start-mcp-server` → `start` (minimal impact, we're only users)
- `--stop-mcp-server` → `stop`
- `--health` → `health` (new command)

**Migration Path:**

```python
# Old (ACB):
crackerjack --start-mcp-server --verbose

# New (Oneiric):
crackerjack start --verbose
```

______________________________________________________________________

#### Decision 2: QA Adapter Categorization

**Complex Adapters (12) → Oneiric Adapters**
Require full MODULE_ID/STATUS/METADATA:

- zuban.py, claude.py, ruff.py, semgrep.py
- bandit.py, gitleaks.py, pyright.py, mypy.py
- pip_audit.py, pyscn.py, refurb.py, complexipy.py

**Simple Adapters (18) → Oneiric Services**
Lightweight, no complex lifecycle:

- mdformat.py, codespell.py, ty.py, pyrefly.py
- creosote.py, skylos.py, type_stubs tools
- Utility adapters (checks.py, etc.)

**Workflow Adapters (8) → Oneiric Tasks (Optional)**
If time permits:

- AI workflow coordinators
- Multi-stage QA orchestration

**Migration Priority:**

1. Complex adapters (critical for QA) - 6 hours
1. Simple adapters (nice to have) - 3 hours
1. Workflow adapters (optional) - Skip if time-constrained

______________________________________________________________________

#### Decision 3: Testing Strategy

**Incremental Migration with Feature Flag:**

```bash
# Environment variable controls migration
export USE_ONEIRIC_CLI=true   # Use new Oneiric CLI
export USE_ONEIRIC_CLI=false  # Rollback to ACB CLI

# Test both paths
USE_ONEIRIC_CLI=true crackerjack start
USE_ONEIRIC_CLI=false crackerjack start
```

**Test Phases:**

1. Unit tests - Adapter pattern compliance
1. Integration tests - End-to-end QA workflows
1. Smoke tests - Basic CLI operations
1. Regression tests - Preserve all existing functionality

______________________________________________________________________

### Migration Phases

#### Phase 0: Pre-Migration Audit (Day 1 AM, 2 hours)

**Goal:** Complete inventory and risk assessment

**Tasks:**

1. Inventory ACB usage across codebase

   - Count: 310 ACB imports identified
   - Map: `grep -r "from acb" crackerjack/` → categorize by module

1. Categorize 38 QA adapters

   - Complex: 12 adapters (require Oneiric Adapter pattern)
   - Simple: 18 adapters (lightweight Services)
   - Workflow: 8 adapters (optional Tasks)

1. Map CLI commands to factory/custom

   - Lifecycle: 5 commands → Factory
   - QA: 15+ commands → Custom

1. Document breaking changes

   - `--start` → `start` (command vs flag)
   - 100+ options need validation

**Deliverables:**

- `MIGRATION_AUDIT.md` - Complete inventory
- `BREAKING_CHANGES.md` - User-facing changes
- Risk assessment matrix

**Success Criteria:**

- [ ] All ACB imports catalogued
- [ ] Adapter categorization complete
- [ ] CLI mapping documented
- [ ] Rollback strategy defined

______________________________________________________________________

#### Phase 1: Remove WebSocket/Dashboard Stack (Day 1 PM, 3 hours)

**Goal:** Delete deprecated monitoring infrastructure

**Files to Remove (55 files):**

```
crackerjack/mcp/websocket/           # Entire directory (10 files)
crackerjack/mcp/dashboard.py
crackerjack/mcp/progress_monitor.py
crackerjack/mcp/enhanced_progress_monitor.py
crackerjack/mcp/progress_components.py
crackerjack/mcp/file_monitor.py
crackerjack/ui/dashboard_renderer.py
crackerjack/ui/templates/            # Entire directory
crackerjack/services/monitoring/     # Entire directory
crackerjack/monitoring/              # Entire directory
```

**CLI Changes:**

```python
# Remove options from cli/options.py:
--start - websocket - server
--stop - websocket - server
--restart - websocket - server
--websocket - port
--monitor - mode
```

**Add Oneiric Snapshot Writes:**

```python
# In mcp/server_core.py
from oneiric.runtime.health import write_runtime_health, RuntimeHealthSnapshot


def start_server():
    snapshot = RuntimeHealthSnapshot(
        orchestrator_pid=os.getpid(),
        watchers_running=True,
    )
    write_runtime_health(".oneiric_cache/runtime_health.json", snapshot)
```

**Test Validation:**

```bash
# Remove WebSocket tests
rm tests/test_websocket.py
rm tests/test_monitoring.py

# Validate no imports remain
grep -r "websocket" crackerjack/ --exclude-dir=.git
```

**Success Criteria:**

- [ ] 55 files deleted
- [ ] No WebSocket imports remain
- [ ] Oneiric snapshots writing on start/stop
- [ ] Tests pass without monitoring

**Rollback:** `git checkout main -- crackerjack/mcp/websocket/ crackerjack/monitoring/`

______________________________________________________________________

#### Phase 2: Remove ACB Dependency (Day 2, 6 hours)

**Goal:** Complete ACB removal from codebase

**Step 1: Remove from pyproject.toml (5 min)**

```toml
# Before:
dependencies = [
    "acb>=0.31.19",
    ...
]

# After:
dependencies = [
    "oneiric>=1.0.0",
    "mcp-common>=3.0.0",
    ...
]
```

**Step 2: Replace ACB Logger (310 files, 3 hours)**

**Pattern:**

```python
# Before (ACB):
from acb.adapters.logger import LoggerProtocol
from acb.depends import Inject


@depends.inject
def handler(logger: Inject[LoggerProtocol] = None):
    logger.info("Message")


# After (Standard logging):
import logging

logger = logging.getLogger(__name__)


def handler():
    logger.info("Message")
```

**Automated Migration Script:**

```python
# scripts/migrate_logging.py
import re
from pathlib import Path


def migrate_file(file_path):
    content = file_path.read_text()

    # Remove ACB logger imports
    content = re.sub(r"from acb\.adapters\.logger import .*\n", "", content)
    content = re.sub(r"from acb\.depends import .*\n", "", content)

    # Replace Inject[LoggerProtocol]
    content = re.sub(
        r"logger: Inject\[LoggerProtocol\] = None",
        "logger = logging.getLogger(__name__)",
        content,
    )

    # Add logging import if needed
    if "logger" in content and "import logging" not in content:
        content = "import logging\n" + content

    file_path.write_text(content)


# Run on all Python files
for file in Path("crackerjack").rglob("*.py"):
    migrate_file(file)
```

**Step 3: Remove ACB DI (@depends.inject, 2 hours)**

**Pattern:**

```python
# Before:
@depends.inject
def setup_ai_agent_env(ai_agent: bool, console: Inject[Console] = None): ...


# After:
def setup_ai_agent_env(ai_agent: bool):
    console = Console()  # Direct instantiation
    ...
```

**Step 4: Remove ACB Workflows/Events (1 hour)**

```bash
# Remove workflow engines
rm crackerjack/workflows/*.py
rm crackerjack/events/*.py
rm crackerjack/core/workflow_orchestrator.py
rm crackerjack/core/async_workflow_orchestrator.py
```

**Validation:**

```bash
# Verify no ACB imports remain
grep -r "from acb" crackerjack/ --exclude-dir=.git
# Expected: 0 results

# Verify no @depends.inject
grep -r "@depends.inject" crackerjack/
# Expected: 0 results
```

**Success Criteria:**

- [ ] ACB removed from pyproject.toml
- [ ] 310 files updated (logging migration)
- [ ] 0 ACB imports remain
- [ ] 0 @depends.inject decorators remain

**Rollback:** `git checkout main -- pyproject.toml crackerjack/`

______________________________________________________________________

#### Phase 3: Integrate Oneiric CLI Factory (Day 3 AM, 3 hours)

**Goal:** Replace custom CLI with Oneiric factory

**Step 1: Create CrackerjackSettings (30 min)**

**File:** `crackerjack/config/settings.py` (new)

```python
from pathlib import Path
from pydantic import Field
from mcp_common.cli import MCPServerSettings


class CrackerjackSettings(MCPServerSettings):
    """Crackerjack server configuration extending MCP base."""

    # QA-specific settings
    qa_mode: bool = Field(default=False, description="Enable QA mode")
    test_suite_path: Path = Field(
        default=Path("tests"), description="Test suite directory"
    )
    auto_fix: bool = Field(default=False, description="Auto-fix issues")
    ai_agent: bool = Field(default=False, description="Enable AI agent")

    # Tool settings
    ruff_enabled: bool = Field(default=True, description="Enable Ruff")
    bandit_enabled: bool = Field(default=True, description="Enable Bandit")
    semgrep_enabled: bool = Field(default=False, description="Enable Semgrep")
```

**Step 2: Create CrackerjackServer (1 hour)**

**File:** `crackerjack/server.py` (new)

```python
import asyncio
import os
from mcp_common.cli import RuntimeHealthSnapshot


class CrackerjackServer:
    """Crackerjack MCP server with QA tooling."""

    def __init__(self, settings: CrackerjackSettings):
        self.settings = settings
        self.running = False

    async def start(self):
        """Start server (background task)."""
        self.running = True

        # Initialize QA adapters
        self._init_qa_adapters()

        # Server main loop
        while self.running:
            await asyncio.sleep(1)

    def stop(self):
        """Stop server."""
        self.running = False

    def get_health_snapshot(self) -> RuntimeHealthSnapshot:
        """Health probe for --health --probe."""
        return RuntimeHealthSnapshot(
            orchestrator_pid=os.getpid(),
            watchers_running=self.running,
            lifecycle_state={
                "qa_adapters": {
                    "count": len(self.adapters),
                    "healthy": all(a.healthy for a in self.adapters),
                },
            },
        )
```

**Step 3: Rewrite __main__.py (1.5 hours)**

**File:** `crackerjack/__main__.py`

**Before:** 659 lines, 100+ Typer options
**After:** ~150 lines, Oneiric factory + custom commands

```python
import asyncio
from mcp_common.cli import MCPServerCLIFactory
from crackerjack.config.settings import CrackerjackSettings
from crackerjack.server import CrackerjackServer


def main():
    # Load settings
    settings = CrackerjackSettings.load("crackerjack")

    # Create server instance
    server = CrackerjackServer(settings)

    # Create CLI factory
    factory = MCPServerCLIFactory(
        "crackerjack",
        settings=settings,
        start_handler=lambda: asyncio.run(server.start()),
        stop_handler=lambda pid: server.stop(),
        health_probe_handler=server.get_health_snapshot,
    )

    # Create Typer app
    app = factory.create_app()

    # Add custom QA commands
    @app.command()
    def run_tests(
        workers: int = typer.Option(4, "--workers", help="Test workers"),
        timeout: int = typer.Option(300, "--timeout", help="Test timeout"),
    ):
        """Run test suite with coverage."""
        # Implementation...

    @app.command()
    def analyze(
        fix: bool = typer.Option(False, "--fix", help="Auto-fix issues"),
    ):
        """Run QA analysis."""
        # Implementation...

    @app.command()
    def qa_health():
        """Check QA adapter health."""
        # Implementation...

    # Run CLI
    app()


if __name__ == "__main__":
    main()
```

**Migration Benefits:**

- 659 lines → 150 lines (77% reduction)
- Standard lifecycle commands via factory
- Custom QA commands preserved
- Cleaner separation of concerns

**Success Criteria:**

- [ ] CrackerjackSettings created
- [ ] CrackerjackServer created
- [ ] __main__.py rewritten (150 lines)
- [ ] `crackerjack start` works
- [ ] Custom commands preserved

**Rollback:** `git checkout main -- crackerjack/__main__.py`

______________________________________________________________________

#### Phase 4: Port QA Adapters to Oneiric (Day 3 PM + Day 4, 10 hours)

**Goal:** Migrate 38 QA adapters to Oneiric pattern

**Adapter Migration Workflow:**

**Step 1: Complex Adapters → Oneiric Adapters (6 hours)**

**Pattern (12 adapters):**

```python
# Before (ACB pattern - non-compliant):
from uuid import uuid4
from acb.adapters import AdapterBase

MODULE_ID = uuid4()  # ISSUE: Not static
MODULE_STATUS = "stable"  # ISSUE: Not enum


class RuffAdapter(BaseToolAdapter): ...


# After (Oneiric pattern):
from uuid import UUID
from oneiric.adapters import AdapterBase, AdapterStatus, AdapterMetadata
import logging

# Static UUID7 (generated once, hardcoded forever)
MODULE_ID = UUID("01947e12-3b4c-7d8e-9f0a-1b2c3d4e5f6a")
MODULE_STATUS = AdapterStatus.STABLE  # Enum

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Ruff Adapter",
    category="format",
    provider="ruff",
    version="1.0.0",
    status=MODULE_STATUS,
)


class RuffAdapter(AdapterBase):
    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def _create_client(self):
        self.logger.info("Ruff adapter initialized")

    async def _cleanup_resources(self):
        self.logger.info("Ruff adapter cleaned up")
```

**Automated Migration (Phase 1):**

```bash
# Generate static UUID7 for each adapter
python -c "from uuidv7 import uuid7; print(uuid7())"

# Script: scripts/migrate_adapters.py
for adapter in crackerjack/adapters/*.py:
    1. Generate static UUID7
    2. Replace uuid4() with hardcoded UUID7
    3. Replace "stable" with AdapterStatus.STABLE
    4. Add MODULE_METADATA
    5. Replace LoggerProtocol with logging.getLogger()
    6. Add lifecycle methods (_create_client, _cleanup_resources)
```

**Manual Review:**

- Validate each adapter (12 adapters × 30 min = 6 hours)
- Ensure lifecycle methods work
- Test adapter initialization

**Step 2: Simple Adapters → Oneiric Services (3 hours)**

**Pattern (18 adapters):**

```python
# Lightweight services (no complex lifecycle)
from oneiric.services import ServiceBase

class MdformatService(ServiceBase):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def format_markdown(self, file_path: Path) -> bool:
        # Implementation...
```

**Step 3: Workflow Adapters → Skip (Optional)**

If time permits, port 8 workflow adapters to Oneiric Tasks. Otherwise, mark as technical debt.

**Success Criteria:**

- [ ] 12 complex adapters ported (Oneiric Adapters)
- [ ] 18 simple adapters ported (Oneiric Services)
- [ ] All adapters have static UUID7
- [ ] All adapters use AdapterStatus enum
- [ ] All adapters tested

**Rollback:** `git checkout main -- crackerjack/adapters/`

______________________________________________________________________

#### Phase 5: Tests & Documentation (Day 5, 5 hours)

**Goal:** Validate migration, update docs, ensure quality

**Step 1: Fix Broken Tests (3 hours)**

**Issues:**

- ACB DI removal breaks test mocks
- Adapter pattern changes require test updates
- WebSocket/monitoring tests removed

**Strategy:**

```python
# Before (ACB DI mocks):
@pytest.fixture
def mock_logger():
    mock = MockLogger()
    depends.set(LoggerProtocol, mock)
    return mock


# After (direct mocking):
@pytest.fixture
def mock_logger(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("crackerjack.module.logger", mock)
    return mock
```

**Test Categories:**

- Unit tests (adapters) - 50 tests
- Integration tests (QA workflows) - 30 tests
- CLI tests (start/stop) - 20 tests

**Target:** 95%+ pass rate (100 tests)

**Step 2: Update Documentation (1.5 hours)**

**Files to Update:**

- `README.md` - Remove WebSocket references, update CLI examples
- `docs/CLI.md` - Update to Oneiric standard commands
- `docs/QA_ADAPTERS.md` - Document Oneiric adapter pattern
- `MIGRATION_GUIDE.md` - Create guide for other projects

**Example Updates:**

```markdown
# Before:
crackerjack --start-mcp-server --verbose

# After:
crackerjack start --verbose
crackerjack health --probe
```

**Step 3: End-to-End Validation (30 min)**

**Smoke Tests:**

```bash
# Lifecycle commands
crackerjack start
crackerjack status
crackerjack health
crackerjack health --probe
crackerjack stop

# QA commands
crackerjack run-tests
crackerjack analyze
crackerjack qa-health
```

**Success Criteria:**

- [ ] 95%+ test pass rate
- [ ] README updated
- [ ] CLI docs updated
- [ ] Migration guide created
- [ ] All smoke tests pass

______________________________________________________________________

### Risk Mitigation

#### Risk 1: ACB Removal Breaks Critical Functionality

**Probability:** MEDIUM
**Impact:** HIGH

**Mitigation:**

- Feature flag: `USE_ONEIRIC_CLI` for gradual rollout
- Comprehensive test suite (100+ tests)
- Automated migration scripts with validation

**Rollback:**

```bash
# Full rollback
git checkout main -- crackerjack/
git checkout main -- pyproject.toml

# Reinstall ACB
uv sync
```

______________________________________________________________________

#### Risk 2: Adapter Port Overruns Timeline (10+ hours)

**Probability:** MEDIUM
**Impact:** MEDIUM

**Mitigation:**

- Prioritize complex adapters (12) over simple (18)
- Skip workflow adapters (8) if time-constrained
- Mark incomplete as technical debt

**Contingency:**

```python
# If time runs out, stub incomplete adapters
class IncompleteAdapter(AdapterBase):
    def __init__(self, **kwargs):
        raise NotImplementedError("TODO: Port to Oneiric (see issue #123)")
```

______________________________________________________________________

#### Risk 3: Test Suite Failures (100+ tests)

**Probability:** HIGH
**Impact:** MEDIUM

**Mitigation:**

- Automated test migration script
- Pytest skip markers for non-critical tests
- Focus on critical path tests first

**Contingency:**

```python
# Skip failing tests temporarily
@pytest.mark.skip(reason="ACB migration in progress, see issue #124")
def test_workflow_orchestration(): ...
```

______________________________________________________________________

#### Risk 4: Breaking Changes Impact Workflows

**Probability:** LOW
**Impact:** LOW

**Mitigation:**

- We are the only users (no external impact)
- Comprehensive migration guide
- Feature flag for gradual transition

______________________________________________________________________

### Success Metrics

#### Functional Metrics

**Must Have:**

- [ ] `crackerjack start` starts server successfully
- [ ] `crackerjack stop` stops server gracefully
- [ ] `crackerjack status` reports accurate status
- [ ] `crackerjack health` reads runtime snapshot
- [ ] `crackerjack health --probe` runs live health checks
- [ ] Runtime snapshots in `.oneiric_cache/`
- [ ] All QA commands work (`run-tests`, `analyze`, `qa-health`)

**Nice to Have:**

- [ ] Multi-instance support working
- [ ] SIGHUP reload working
- [ ] Systemd integration tested

#### Code Quality Metrics

**Must Have:**

- [ ] 0 ACB imports (`grep -r "from acb" crackerjack/` → empty)
- [ ] 0 @depends.inject (`grep -r "@depends.inject"` → empty)
- [ ] 12/12 complex adapters ported (100%)
- [ ] 95%+ test pass rate (95/100 tests)

**Nice to Have:**

- [ ] 18/18 simple adapters ported (100%)
- [ ] 8/8 workflow adapters ported (100%)
- [ ] 100% test pass rate

#### Timeline Metrics

**Day-by-Day Checkpoints:**

- [ ] **Day 1 End:** Audit complete (2h), WebSocket removed (3h) - 5 hours total
- [ ] **Day 2 End:** ACB removed (6h) - 11 hours total
- [ ] **Day 3 End:** Oneiric integrated (3h), 6 adapters ported (3h) - 17 hours total
- [ ] **Day 4 End:** 12 adapters ported (7h) - 24 hours total
- [ ] **Day 5 End:** Tests fixed (3h), docs updated (1.5h), validation (0.5h) - 29 hours total

**Buffer:** 1 hour (total 30 hours allocated)

______________________________________________________________________

### Critical Files Summary

#### Specification Refinement Files

1. `/Users/les/Projects/mcp-common/docs/ONEIRIC_CLI_FACTORY_IMPLEMENTATION.md` - Spec to refine
1. `/Users/les/Projects/mcp-common/mcp_common/cli/factory.py` - Factory implementation (Phase 1)
1. `/Users/les/Projects/mcp-common/mcp_common/cli/settings.py` - Settings class (Phase 1)
1. `/Users/les/Projects/mcp-common/examples/weather_server.py` - Example with all refinements

#### Crackerjack Migration Files

1. `/Users/les/Projects/crackerjack/crackerjack/__main__.py` - CLI entry (659→150 lines)
1. `/Users/les/Projects/crackerjack/crackerjack/config/settings.py` - New CrackerjackSettings
1. `/Users/les/Projects/crackerjack/crackerjack/server.py` - New CrackerjackServer
1. `/Users/les/Projects/crackerjack/crackerjack/adapters/*.py` - 38 adapters to port
1. `/Users/les/Projects/crackerjack/pyproject.toml` - Remove ACB, add Oneiric
1. `/Users/les/Projects/crackerjack/README.md` - Update CLI docs
1. `/Users/les/Projects/crackerjack/MIGRATION_GUIDE.md` - New migration guide

#### Files to Remove (55 total)

- `/Users/les/Projects/crackerjack/crackerjack/mcp/websocket/` - Entire directory
- `/Users/les/Projects/crackerjack/crackerjack/monitoring/` - Entire directory
- `/Users/les/Projects/crackerjack/crackerjack/services/monitoring/` - Entire directory

______________________________________________________________________

## Next Steps

**For Peer Review:**

1. Review specification refinements (8 items, ~2.5 hours)
1. Review crackerjack migration plan (5 phases, ~30 hours)
1. Validate timeline (Week 2 for crackerjack acceptable?)
1. Approve risks and mitigation strategies
1. Sign off on critical decisions (CLI mapping, adapter categorization)

**After Approval:**

1. **Phase 1 (Week 1):** Build mcp-common CLI factory with refinements
1. **Phase 2 (Week 2):** Execute crackerjack migration
1. **Phase 3 (Week 3+):** Roll out to remaining servers (session-buddy, raindropio, mailgun)

**Questions for Peer Review:**

1. Is the 5-phase crackerjack migration sequencing optimal?
1. Should we port all 38 adapters or prioritize the 12 complex ones?
1. Is the feature flag approach (`USE_ONEIRIC_CLI`) necessary or overkill?
1. Are the 8 specification refinements sufficient or are there gaps?

______________________________________________________________________

**Plan Status:** ✅ READY FOR PEER REVIEW
**Estimated Review Time:** 30-45 minutes
**Approval Required:** YES
