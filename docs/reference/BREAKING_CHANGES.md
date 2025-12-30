# Breaking Changes: Oneiric Migration

**Migration Date:** TBD (after Phase 0 complete)
**Migration Plan:** ONEIRIC_MIGRATION_EXECUTION_PLAN.md
**Audit Report:** MIGRATION_AUDIT.md

______________________________________________________________________

## Executive Summary

The Oneiric migration replaces ACB dependency injection and custom WebSocket monitoring with standardized Oneiric patterns. This brings **breaking changes to CLI commands** but preserves all QA functionality.

**Key Changes:**

1. **CLI Structure:** Options → Commands (e.g., `--start-mcp-server` → `start`)
1. **Health Checks:** New `--probe` flag for live monitoring
1. **WebSocket Removed:** All WebSocket server options deleted
1. **Multi-Instance Support:** New `--instance-id` flag

______________________________________________________________________

## Breaking Changes by Category

### 1. MCP Server Lifecycle Commands ⚠️ HIGH IMPACT

**Before (ACB):**

```bash
# Start server
python -m crackerjack run --start-mcp-server --verbose

# Stop server
python -m crackerjack run --stop-mcp-server

# Restart server
python -m crackerjack run --restart-mcp-server
```

**After (Oneiric):**

```bash
# Start server
python -m crackerjack start --verbose

# Stop server
python -m crackerjack stop

# Restart server
python -m crackerjack restart
```

**Migration Required:**

- Update all startup scripts
- Update systemd service files
- Update documentation
- Update CI/CD pipelines

**Affected Users:** ALL (anyone using MCP server lifecycle)

______________________________________________________________________

### 2. Health Monitoring ⚠️ MEDIUM IMPACT

**Before (ACB):**

```bash
# No dedicated health command
# Health status via WebSocket dashboard
```

**After (Oneiric):**

```bash
# Check health snapshot (passive)
python -m crackerjack health

# Live health probe (active)
python -m crackerjack health --probe
```

**New Capabilities:**

- ✅ Passive health checks via runtime snapshots (`.oneiric_cache/runtime_health.json`)
- ✅ Active health probes for production monitoring
- ✅ Systemd integration via `ExecStartPost`

**Migration Required:**

- Add health check commands to monitoring scripts
- Configure systemd health probes (optional)

**Affected Users:** Production deployments, monitoring setups

______________________________________________________________________

### 3. WebSocket Server REMOVED ⚠️ MEDIUM IMPACT

**Before (ACB):**

```bash
# WebSocket server options
--start-websocket-server
--stop-websocket-server
--restart-websocket-server
--websocket-port 8675
```

**After (Oneiric):**

```bash
# ALL WebSocket options REMOVED
# No replacement - use Oneiric runtime snapshots instead
```

**Replacement Strategy:**

- Use `.oneiric_cache/runtime_health.json` for status monitoring
- Use external dashboards (Grafana, Prometheus) for visualization
- Use `crackerjack health --probe` for live checks

**Migration Required:**

- Remove all WebSocket references from scripts
- Update monitoring to use Oneiric snapshots
- Migrate dashboards to external tools (if needed)

**Affected Users:** Anyone using WebSocket monitoring (low adoption expected)

______________________________________________________________________

### 4. Multi-Instance Support ✅ NEW FEATURE

**Before (ACB):**

```bash
# Single instance only
# No built-in multi-instance support
```

**After (Oneiric):**

```bash
# Multiple instances with isolated runtime directories
python -m crackerjack start --instance-id worker-1
python -m crackerjack start --instance-id worker-2

# Each instance gets:
# .oneiric_cache/worker-1/server.pid
# .oneiric_cache/worker-1/runtime_health.json
# .oneiric_cache/worker-2/server.pid
# .oneiric_cache/worker-2/runtime_health.json
```

**New Capabilities:**

- ✅ Horizontal scaling with multiple instances
- ✅ Isolated PID files and runtime directories
- ✅ Systemd template support (`crackerjack@%i.service`)

**Migration Required:**

- None (new feature, opt-in)

**Affected Users:** Advanced users running multiple instances

______________________________________________________________________

## Detailed Migration Guide

### Step 1: Update Startup Scripts

**Before:**

```bash
#!/bin/bash
# old_start.sh
python -m crackerjack run --start-mcp-server --verbose
```

**After:**

```bash
#!/bin/bash
# new_start.sh
python -m crackerjack start --verbose
```

### Step 2: Update Systemd Service

**Before:**

```ini
[Service]
ExecStart=/opt/crackerjack/.venv/bin/python -m crackerjack run --start-mcp-server
ExecStop=/opt/crackerjack/.venv/bin/python -m crackerjack run --stop-mcp-server
```

**After:**

```ini
[Service]
ExecStart=/opt/crackerjack/.venv/bin/python -m crackerjack start
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5s

# Optional: Health monitoring
ExecStartPost=/bin/sleep 2
ExecStartPost=/opt/crackerjack/.venv/bin/python -m crackerjack health --probe
```

### Step 3: Remove WebSocket References

**Before:**

```bash
# Monitoring script (old)
python -m crackerjack run --start-websocket-server --websocket-port 8675
curl http://localhost:8675/status
```

**After:**

```bash
# Monitoring script (new)
python -m crackerjack start
python -m crackerjack health --probe  # Live health check
cat .oneiric_cache/runtime_health.json  # Passive snapshot
```

### Step 4: Multi-Instance Deployment (Optional)

**New systemd template:**

```ini
# /etc/systemd/system/crackerjack@.service
[Service]
ExecStart=/opt/crackerjack/.venv/bin/python -m crackerjack start --instance-id %i
Environment="INSTANCE_ID=%i"
```

**Usage:**

```bash
sudo systemctl start crackerjack@worker-1
sudo systemctl start crackerjack@worker-2
sudo systemctl status 'crackerjack@*'
```

______________________________________________________________________

## Rollback Strategy

If migration causes issues:

```bash
# Rollback to pre-migration state
git checkout <pre-migration-commit>

# Reinstall ACB dependency
uv sync

# Restore old CLI commands
python -m crackerjack run --start-mcp-server  # Works with ACB
```

**Rollback Risk:** LOW (clean git revert, no data loss)

______________________________________________________________________

## Testing Checklist

Before deploying to production:

- [ ] Start server: `python -m crackerjack start` works
- [ ] Stop server: `python -m crackerjack stop` works
- [ ] Restart server: `python -m crackerjack restart` works
- [ ] Health snapshot: `python -m crackerjack health` works
- [ ] Health probe: `python -m crackerjack health --probe` works
- [ ] Multi-instance: `python -m crackerjack start --instance-id test` works
- [ ] Runtime snapshots created in `.oneiric_cache/`
- [ ] All QA adapters functional
- [ ] All tests passing

______________________________________________________________________

## Support & Questions

**Migration Issues:**

- Check `MIGRATION_AUDIT.md` for baseline state
- Review Phase 5 test results
- File GitHub issue if needed

**Documentation:**

- Full migration plan: `ONEIRIC_MIGRATION_EXECUTION_PLAN.md`
- Audit report: `MIGRATION_AUDIT.md`
- Oneiric docs: `/Users/les/Projects/mcp-common/README.md`

______________________________________________________________________

*This document will be finalized after migration completion.*
