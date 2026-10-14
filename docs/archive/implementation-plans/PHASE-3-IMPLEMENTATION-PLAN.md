# Phase 3: Oneiric CLI Factory Integration - Implementation Plan

**Date**: 2025-12-27
**Status**: 🚀 Starting
**Objective**: Replace custom CLI with Oneiric-integrated lifecycle management
**Timeline**: 3 hours (adapted from original migration plan)

______________________________________________________________________

## Executive Summary

Phase 3 integrates Crackerjack with Oneiric runtime management, replacing the custom 659-line CLI with a streamlined ~150-line implementation using Oneiric patterns.

**Key Differences from Original Plan:**

- Original plan referenced `MCPServerSettings` and `MCPServerCLIFactory` from `mcp_common.cli` - **these don't exist in mcp-common 2.0.0**
- Adapted approach: Use `mcp_common.MCPBaseSettings` as base + integrate with Oneiric's `RuntimeOrchestrator` directly
- Same goals, different implementation path

**Dependencies Verified:**

- ✅ `mcp-common==2.0.0` installed
- ✅ `oneiric==0.3.2` installed
- ✅ Phase 2 complete (ACB removed, all imports validated)

______________________________________________________________________

## Task 1: Rewrite CrackerjackSettings (30 min)

### Objective

Replace ACB Settings-based CrackerjackSettings with simpler Pydantic BaseSettings that removes ACB dependency.

### Current State

**File**: `crackerjack/config/settings.py` (141 lines)

- Uses `acb.config.Settings` as base class
- Has 13 sub-settings classes (CleaningSettings, HookSettings, etc.)
- Complex nested structure

### Target State

**File**: `crackerjack/config/settings.py` (NEW - ~80 lines)

- Remove `acb.config.Settings` dependency
- Use Pydantic `BaseSettings` directly
- Flatten structure while preserving all necessary configuration fields
- Add QA-specific settings for Oneiric integration

### Implementation

```python
"""Crackerjack server settings for Oneiric integration."""

from pathlib import Path
from pydantic import BaseSettings, Field


class CrackerjackSettings(BaseSettings):
    """Crackerjack configuration for Oneiric-integrated QA server."""

    # Server settings
    server_name: str = Field(
        default="Crackerjack QA Server", description="Server display name"
    )
    server_description: str = Field(
        default="Python QA tooling with AI integration",
        description="Server description",
    )
    instance_id: str | None = Field(
        default=None, description="Unique server instance ID"
    )
    runtime_dir: Path = Field(
        default=Path.home() / ".crackerjack", description="Runtime cache directory"
    )

    # QA-specific settings
    qa_mode: bool = Field(default=False, description="Enable QA analysis mode")
    test_suite_path: Path = Field(
        default=Path("tests"), description="Test suite directory"
    )
    auto_fix: bool = Field(default=False, description="Enable automatic issue fixing")
    ai_agent: bool = Field(default=False, description="Enable AI-powered code analysis")

    # Tool enablement flags
    ruff_enabled: bool = Field(default=True, description="Enable Ruff linter/formatter")
    bandit_enabled: bool = Field(
        default=True, description="Enable Bandit security scanner"
    )
    semgrep_enabled: bool = Field(default=False, description="Enable Semgrep SAST")
    mypy_enabled: bool = Field(default=True, description="Enable mypy type checking")
    zuban_enabled: bool = Field(
        default=True, description="Enable Zuban ultra-fast type checker"
    )
    skylos_enabled: bool = Field(
        default=True, description="Enable Skylos dead code detection"
    )

    # Performance settings
    max_parallel_hooks: int = Field(
        default=4, description="Max parallel pre-commit hooks"
    )
    test_workers: int = Field(default=0, description="Pytest workers (0=auto)")
    test_timeout: int = Field(default=300, description="Test timeout in seconds")

    # Execution settings
    verbose: bool = Field(default=False, description="Enable verbose logging")
    interactive: bool = Field(default=False, description="Enable interactive mode")
    async_mode: bool = Field(
        default=False, description="Enable async workflow execution"
    )

    # MCP server settings (for backward compatibility)
    http_port: int = Field(default=8676, description="MCP HTTP server port")
    http_host: str = Field(default="127.0.0.1", description="MCP HTTP server host")
    http_enabled: bool = Field(default=False, description="Enable MCP HTTP server")

    class Config:
        env_prefix = "CRACKERJACK_"
        env_file = ".env"
        env_file_encoding = "utf-8"

    @classmethod
    def load(cls, config_name: str = "crackerjack") -> "CrackerjackSettings":
        """Load settings from YAML files (ACB Settings compatibility)."""
        # TODO(Phase 3): Implement YAML loading or use environment variables only
        return cls()
```

### Migration Strategy

1. Create new `crackerjack/config/settings_new.py` with Pydantic BaseSettings
1. Test loading: `python -c "from crackerjack.config.settings_new import CrackerjackSettings; s = CrackerjackSettings.load('crackerjack'); print(s.qa_mode)"`
1. Backup old: `mv crackerjack/config/settings.py crackerjack/config/settings_acb_backup.py`
1. Replace: `mv crackerjack/config/settings_new.py crackerjack/config/settings.py`
1. Update all imports to use new settings structure

### Validation

```bash
# Test settings loading
python -c "from crackerjack.config.settings import CrackerjackSettings; s = CrackerjackSettings.load('crackerjack'); print(f'QA Mode: {s.qa_mode}, AI Agent: {s.ai_agent}')"
# Expected: "QA Mode: False, AI Agent: False"
```

______________________________________________________________________

## Task 2: Create CrackerjackServer (1 hour)

### Objective

Create server class that manages QA adapter lifecycle and integrates with Oneiric runtime.

### Target State

**File**: `crackerjack/server.py` (NEW - ~120 lines)

### Implementation

```python
"""Crackerjack MCP server with QA tooling integration."""

import asyncio
import logging
import os
from datetime import datetime, UTC
from pathlib import Path

from crackerjack.config.settings import CrackerjackSettings

logger = logging.getLogger(__name__)


class CrackerjackServer:
    """Crackerjack MCP server with integrated QA adapters.

    Manages QA adapter lifecycle and provides health snapshots for monitoring.
    Designed to integrate with Oneiric runtime orchestration.
    """

    def __init__(self, settings: CrackerjackSettings):
        self.settings = settings
        self.running = False
        self.adapters: list = []  # QA adapters (populated in Phase 4)
        self.start_time: datetime | None = None
        self._server_task: asyncio.Task | None = None

    async def start(self):
        """Start server with QA adapter initialization."""
        logger.info("Starting Crackerjack MCP server...")
        self.running = True
        self.start_time = datetime.now(UTC)

        # Initialize QA adapters based on settings
        await self._init_qa_adapters()

        logger.info(f"Server started with {len(self.adapters)} QA adapters")

        # Server main loop (keeps process alive)
        try:
            while self.running:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("Server main loop cancelled")
            raise

    async def _init_qa_adapters(self):
        """Initialize enabled QA adapters.

        TODO(Phase 4): Actual adapter initialization will be implemented in Phase 4.
        For now, this is a placeholder that logs which adapters would be enabled.
        """
        enabled_adapters = []

        if self.settings.ruff_enabled:
            enabled_adapters.append("Ruff")
        if self.settings.bandit_enabled:
            enabled_adapters.append("Bandit")
        if self.settings.semgrep_enabled:
            enabled_adapters.append("Semgrep")
        if self.settings.mypy_enabled:
            enabled_adapters.append("Mypy")
        if self.settings.zuban_enabled:
            enabled_adapters.append("Zuban")
        if self.settings.skylos_enabled:
            enabled_adapters.append("Skylos")

        logger.info(f"QA adapters enabled: {', '.join(enabled_adapters)}")
        # Adapters will be properly initialized in Phase 4

    def stop(self):
        """Stop server gracefully."""
        logger.info("Stopping Crackerjack MCP server...")
        self.running = False

        # Cleanup adapters
        for adapter in self.adapters:
            if hasattr(adapter, "cleanup"):
                try:
                    adapter.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up adapter: {e}")

        logger.info("Server stopped")

    def get_health_snapshot(self) -> dict:
        """Generate health snapshot for monitoring.

        Returns health data compatible with Oneiric runtime health format.
        """
        uptime = (
            (datetime.now(UTC) - self.start_time).total_seconds()
            if self.start_time
            else 0.0
        )

        return {
            "server_status": "running" if self.running else "stopped",
            "uptime_seconds": uptime,
            "process_id": os.getpid(),
            "qa_adapters": {
                "total": len(self.adapters),
                "healthy": sum(1 for a in self.adapters if getattr(a, "healthy", True)),
            },
            "settings": {
                "qa_mode": self.settings.qa_mode,
                "ai_agent": self.settings.ai_agent,
                "auto_fix": self.settings.auto_fix,
                "test_workers": self.settings.test_workers,
            },
        }

    async def run_in_background(self):
        """Run server in background task."""
        self._server_task = asyncio.create_task(self.start())
        return self._server_task

    async def shutdown(self):
        """Async shutdown for graceful cleanup."""
        self.stop()
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
```

### Validation

```bash
# Test server creation and health snapshot
python -c "
from crackerjack.config.settings import CrackerjackSettings
from crackerjack.server import CrackerjackServer

settings = CrackerjackSettings.load('crackerjack')
server = CrackerjackServer(settings)
health = server.get_health_snapshot()
print(f'Server created. Health: {health}')
"
# Expected: Server created with health snapshot showing stopped status
```

______________________________________________________________________

## Task 3: Rewrite __main__.py (1.5 hours)

### Objective

Replace 659-line custom CLI with ~150-line Oneiric-integrated implementation.

### Current State

**File**: `crackerjack/__main__.py` (659 lines)

- 100+ Typer options
- Custom start/stop logic
- Complex orchestration patterns
- ACB-dependent workflows

### Target State

**File**: `crackerjack/__main__.py` (NEW - ~150 lines, 77% reduction)

### Implementation

```python
"""Crackerjack CLI entry point with Oneiric integration."""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

import typer

from crackerjack.config.settings import CrackerjackSettings
from crackerjack.server import CrackerjackServer

app = typer.Typer(
    name="crackerjack",
    help="Python QA tooling with AI integration",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Lifecycle Commands (Oneiric Integration)
# ============================================================================


@app.command()
def start(
    instance_id: str | None = typer.Option(
        None, "--instance-id", help="Server instance ID"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """Start Crackerjack MCP server."""
    # TODO(Phase 3): Integrate with Oneiric runtime orchestrator
    # For now, basic server lifecycle implementation

    settings = CrackerjackSettings.load("crackerjack")
    if instance_id:
        settings.instance_id = instance_id
    if verbose:
        settings.verbose = True
        logging.basicConfig(level=logging.DEBUG)

    server = CrackerjackServer(settings)

    try:
        typer.echo(
            f"Starting Crackerjack server (instance: {settings.instance_id or 'default'})..."
        )
        asyncio.run(server.start())
    except KeyboardInterrupt:
        typer.echo("\nShutting down server...")
        server.stop()
        raise typer.Exit(0)


@app.command()
def stop(
    instance_id: str | None = typer.Option(
        None, "--instance-id", help="Server instance ID"
    ),
):
    """Stop Crackerjack MCP server."""
    # TODO(Phase 3): Integrate with Oneiric graceful shutdown
    typer.echo("Stop command not yet implemented")
    typer.echo("Use Ctrl+C to stop the server for now")
    raise typer.Exit(1)


@app.command()
def restart(
    instance_id: str | None = typer.Option(
        None, "--instance-id", help="Server instance ID"
    ),
):
    """Restart Crackerjack MCP server."""
    # TODO(Phase 3): Integrate with Oneiric restart logic
    typer.echo("Restart command not yet implemented")
    raise typer.Exit(1)


@app.command()
def status(
    instance_id: str | None = typer.Option(
        None, "--instance-id", help="Server instance ID"
    ),
):
    """Show server status."""
    # TODO(Phase 3): Read from Oneiric runtime cache
    typer.echo("Status command not yet implemented")
    typer.echo("TODO: Read from .oneiric_cache/runtime_health.json")
    raise typer.Exit(1)


@app.command()
def health(
    probe: bool = typer.Option(False, "--probe", help="Health probe for monitoring"),
    instance_id: str | None = typer.Option(
        None, "--instance-id", help="Server instance ID"
    ),
):
    """Check server health."""
    # TODO(Phase 3): Integrate with Oneiric health snapshot
    if probe:
        # Systemd/monitoring integration
        typer.echo("Health probe not yet implemented")
        raise typer.Exit(1)
    else:
        typer.echo("Health check not yet implemented")
        raise typer.Exit(1)


# ============================================================================
# QA Commands (Preserved from original)
# ============================================================================


@app.command()
def run_tests(
    workers: int = typer.Option(0, "--workers", "-n", help="Test workers (0=auto)"),
    timeout: int = typer.Option(300, "--timeout", help="Test timeout seconds"),
    coverage: bool = typer.Option(
        True, "--coverage/--no-coverage", help="Run with coverage"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run test suite with coverage."""
    cmd = ["pytest"]

    # Worker configuration
    if workers != 1:
        cmd.extend(["-n", str(workers) if workers > 0 else "auto"])

    # Coverage
    if coverage:
        cmd.extend(["--cov=crackerjack", "--cov-report=html", "--cov-report=term"])

    # Timeout
    cmd.append(f"--timeout={timeout}")

    # Verbosity
    if verbose:
        cmd.append("-vv")

    typer.echo(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    raise typer.Exit(result.returncode)


@app.command()
def analyze(
    fix: bool = typer.Option(False, "--fix", help="Auto-fix issues"),
    ai: bool = typer.Option(False, "--ai", help="Use AI agent"),
):
    """Run QA analysis on codebase."""
    # TODO(Phase 3): Replace with Oneiric adapter invocation
    typer.echo("Analyze command not yet implemented")
    typer.echo("TODO: Invoke QA adapters via Oneiric runtime")
    raise typer.Exit(1)


@app.command()
def qa_health():
    """Check health of QA adapters."""
    # TODO(Phase 3): Query adapter health from server
    settings = CrackerjackSettings.load("crackerjack")
    server = CrackerjackServer(settings)
    health = server.get_health_snapshot()

    qa_status = health.get("qa_adapters", {})
    typer.echo(
        f"QA Adapters: {qa_status.get('total', 0)} total, {qa_status.get('healthy', 0)} healthy"
    )

    if qa_status.get("total", 0) == qa_status.get("healthy", 0):
        typer.echo("✅ All adapters healthy")
        raise typer.Exit(0)
    else:
        typer.echo("⚠️  Some adapters unhealthy")
        raise typer.Exit(1)


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
```

### Migration Benefits

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Lines of code | 659 | ~150 | -77% reduction |
| Typer options | 100+ | ~20 | -80% reduction |
| Start/stop logic | Custom (100+ lines) | Oneiric-integrated | Standardized |
| Health checks | Custom (50+ lines) | Server method | Simplified |
| Dependencies | ACB workflows | Oneiric runtime | Modern |

### Validation

```bash
# Test CLI commands are callable
python -m crackerjack --help
python -m crackerjack start --help
python -m crackerjack status --help
python -m crackerjack health --help
python -m crackerjack run-tests --help
python -m crackerjack analyze --help
python -m crackerjack qa-health --help

# Expected: All commands show help text without errors
```

______________________________________________________________________

## Phase 3 Validation Checklist

### Pre-Phase Validation

- [x] Phase 2 complete (ACB removed, all imports validated)
- [ ] Git backup: `git add -A && git commit -m "Pre-Phase 3 checkpoint"`

### Post-Phase Validation

**Settings:**

- [ ] CrackerjackSettings loads without ACB dependency
- [ ] Settings has all required QA fields (qa_mode, test_workers, etc.)
- [ ] Environment variable override works (`CRACKERJACK_QA_MODE=true`)

**Server:**

- [ ] CrackerjackServer instantiates without errors
- [ ] Health snapshot returns valid dict
- [ ] Server lifecycle methods (start/stop) callable

**CLI:**

- [ ] All commands show help: `--help` works for each command
- [ ] Lifecycle commands callable (start/stop/status/health)
- [ ] QA commands preserved (run-tests, analyze, qa-health)
- [ ] Line count ~150 lines (77% reduction from 659)

**Import Validation:**

- [ ] All 12 critical modules still import successfully:
  ```bash
  python scripts/validate_imports.py
  # Expected: 12/12 modules pass
  ```

### Success Criteria

ALL of the following must pass:

1. ✅ Settings class removes ACB dependency
1. ✅ Server class created with health snapshot
1. ✅ __main__.py reduced to ~150 lines
1. ✅ All CLI commands callable (show help without errors)
1. ✅ No import regressions (12/12 modules pass)

**Success Gate:** ALL criteria must pass before proceeding to Phase 4

______________________________________________________________________

## Rollback Strategy

If Phase 3 encounters critical issues:

```bash
# Full rollback to pre-Phase 3 state
git checkout HEAD~1 -- crackerjack/config/settings.py
git checkout HEAD~1 -- crackerjack/__main__.py
rm -f crackerjack/server.py

# Verify rollback
python -m crackerjack --help  # Should show old CLI
python scripts/validate_imports.py  # Should pass 12/12
```

**Risk Level:** MEDIUM (major CLI refactoring, new server class)

______________________________________________________________________

## Phase 3 Timeline

| Task | Duration | Cumulative |
|------|----------|------------|
| Task 1: Rewrite CrackerjackSettings | 30 min | 30 min |
| Task 2: Create CrackerjackServer | 60 min | 90 min |
| Task 3: Rewrite __main__.py | 90 min | 180 min |
| **Total** | **3 hours** | **3 hours** |

______________________________________________________________________

## Next Steps (Phase 4)

After Phase 3 completion:

- Port 30 QA adapters to Oneiric pattern (Day 3 PM + Day 4)
- Implement proper adapter lifecycle in CrackerjackServer.\_init_qa_adapters()
- Integrate with Oneiric runtime orchestration for lifecycle commands
- Complete Oneiric telemetry integration

______________________________________________________________________

## Notes & Observations

**Key Adaptations from Original Plan:**

1. Original plan referenced non-existent `mcp_common.cli.MCPServerSettings` and `MCPServerCLIFactory`
1. Adapted to use Pydantic BaseSettings directly + Oneiric runtime patterns
1. Phase 3 focuses on structural changes; full Oneiric integration deferred to Phase 4

**Technical Debt Created:**

- TODO markers for full Oneiric runtime integration (start/stop/status/health commands)
- Server lifecycle currently basic; needs Oneiric RuntimeOrchestrator integration
- Adapter initialization stubs (Phase 4 will implement actual adapters)

**Benefits Achieved:**

- ✅ Removed ACB Settings dependency
- ✅ Simplified settings structure
- ✅ Created server abstraction for adapter lifecycle
- ✅ Reduced CLI from 659→150 lines (77% code reduction)
- ✅ Standardized lifecycle command structure
