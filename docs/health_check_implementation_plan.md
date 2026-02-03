# Health Check System Implementation Plan

## Overview
Implement comprehensive health check endpoints for all layers of the Crackerjack system: adapters, managers, services, and CLI.

## Architecture

### Health Check Protocol
```python
class HealthCheckResult(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    message: str
    details: dict[str, Any]
    timestamp: datetime
```

### Health Check Protocol Definition
```python
@runtime_checkable
class HealthCheckProtocol(Protocol):
    def health_check(self) -> HealthCheckResult: ...
```

## Components

### 1. Core Health Check Models
**File**: `crackerjack/models/health_check.py`

- `HealthCheckResult` - Standard health check result model
- `HealthCheckProtocol` - Protocol defining health check interface
- `ComponentHealth` - Aggregated health status for multiple components
- `SystemHealthReport` - Complete system health report

### 2. Adapter Health Checks
**File**: `crackerjack/adapters/health_mixin.py`

- `HealthCheckMixin` - Mixin class for adapter health checks
- Base adapter health check implementation
- Tool availability checks
- Configuration validation

### 3. Manager Health Checks
**Files**:
- `crackerjack/managers/hook_manager.py` - Add health_check method
- `crackerjack/managers/test_manager.py` - Add health_check method
- `crackerjack/managers/publish_manager.py` - Add health_check method

**Checks**:
- Configuration validity
- Required tools availability
- File system access
- Git repository status

### 4. Service Health Checks
**Files**:
- `crackerjack/services/git.py` - Add health_check method
- `crackerjack/services/enhanced_filesystem.py` - Add health_check method
- `crackerjack/services/documentation_generator.py` - Add health_check method

**Checks**:
- Service initialization status
- Required dependencies
- Resource availability

### 5. CLI Health Command
**File**: `crackerjack/cli/handlers/health.py`

New command: `crackerjack health`

**Features**:
- Check all components
- Display aggregated health status
- Support JSON output
- Support individual component checks
- Exit codes: 0=healthy, 1=degraded, 2=unhealthy

### 6. Integration Points

#### 6.1 Protocol Updates
**File**: `crackerjack/models/protocols.py`

Add `HealthCheckProtocol` to existing protocols:
- `ServiceProtocol` - Already has health_check() -> bool
- Extend to return `HealthCheckResult` instead of bool
- Add `HealthCheckProtocol` for new components

#### 6.2 MCP Integration
**File**: `crackerjack/mcp/server_core.py`

- Add `health_check` tool to MCP server
- Return system health status to MCP clients

## Implementation Order

### Phase 1: Core Models (Priority: HIGH)
1. Create `crackerjack/models/health_check.py`
2. Define `HealthCheckResult`, `HealthCheckProtocol`
3. Create `ComponentHealth`, `SystemHealthReport`
4. Add to `crackerjack/models/__init__.py`

### Phase 2: Protocol Updates (Priority: HIGH)
1. Update `ServiceProtocol` in `models/protocols.py`
2. Add `HealthCheckProtocol` for adapters and managers
3. Ensure backward compatibility with existing health_check() -> bool

### Phase 3: Adapter Health Checks (Priority: MEDIUM)
1. Create `HealthCheckMixin` in `adapters/health_mixin.py`
2. Add health_check to `QAAdapterBase`
3. Implement tool availability checks
4. Test with a few adapter types (ruff, pytest, codespell)

### Phase 4: Manager Health Checks (Priority: MEDIUM)
1. Add health_check to `HookManagerImpl`
2. Add health_check to `TestManager`
3. Add health_check to `PublishManager`
4. Test manager health checks

### Phase 5: Service Health Checks (Priority: MEDIUM)
1. Add health_check to `GitService`
2. Add health_check to `EnhancedFileSystemService`
3. Add health_check to other core services
4. Test service health checks

### Phase 6: CLI Command (Priority: HIGH)
1. Create `cli/handlers/health.py`
2. Add `health` command to `__main__.py`
3. Implement output formatting (table, JSON)
4. Add exit code logic
5. Test CLI command

### Phase 7: MCP Integration (Priority: LOW)
1. Add health_check tool to MCP server
2. Return system health status
3. Test MCP integration

### Phase 8: Testing (Priority: HIGH)
1. Unit tests for health check models
2. Unit tests for health check methods
3. Integration tests for CLI command
4. Test coverage: ≥90%

## Health Check Levels

### Healthy
- All checks passing
- No warnings
- All dependencies available
- All resources accessible

### Degraded
- Core functionality working
- Non-critical checks failing
- Some warnings
- Workarounds available

### Unhealthy
- Critical checks failing
- Core functionality broken
- No workarounds available
- Immediate attention required

## Exit Codes

- `0` - All components healthy
- `1` - Some components degraded (warning)
- `2` - Some components unhealthy (error)

## CLI Usage Examples

```bash
# Check all components
crackerjack health

# Check specific component
crackerjack health --component adapters
crackerjack health --component managers
crackerjack health --component services

# JSON output
crackerjack health --json

# Verbose output
crackerjack health --verbose

# Exit code only (for scripts)
crackerjack health --quiet
```

## JSON Output Format

```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "components": {
    "adapters": {
      "status": "healthy",
      "total": 18,
      "healthy": 18,
      "degraded": 0,
      "unhealthy": 0,
      "details": {...}
    },
    "managers": {
      "status": "healthy",
      "total": 3,
      "healthy": 3,
      "degraded": 0,
      "unhealthy": 0,
      "details": {...}
    },
    "services": {
      "status": "degraded",
      "total": 8,
      "healthy": 7,
      "degraded": 1,
      "unhealthy": 0,
      "details": {
        "git_service": {
          "status": "degraded",
          "message": "Git repository has uncommitted changes"
        }
      }
    }
  }
}
```

## Testing Strategy

### Unit Tests
- Test `HealthCheckResult` model
- Test health check methods for each component type
- Mock external dependencies (git, filesystem, tools)

### Integration Tests
- Test CLI command with real components
- Test JSON output format
- Test exit codes
- Test verbose/quiet modes

### Test Coverage
- Target: ≥90% coverage for health check code
- Include edge cases (missing tools, no git repo, etc.)
- Test error handling

## Dependencies

### New Dependencies
None (using existing Pydantic, typing)

### Existing Dependencies
- `pydantic` - For BaseModel
- `typing` - For type hints
- `datetime` - For timestamps
- `rich` - For CLI output formatting

## Backward Compatibility

### Existing health_check() -> bool
- Keep existing bool return for backward compatibility
- Add new health_check() -> HealthCheckResult overload
- Deprecation warning for bool version (future)

### Migration Path
1. Phase 1-2: Add new protocol alongside existing
2. Phase 3-5: Implement new health_check methods
3. Phase 6: CLI uses new protocol
4. Future: Remove bool protocol (breaking change)

## Documentation

### User Documentation
- CLI command usage
- Exit codes
- JSON output format
- Troubleshooting guide

### Developer Documentation
- Health check protocol
- Implementation guide
- Testing guide
- Adding health checks to new components

## Success Criteria

- [x] Health check protocol defined
- [x] All adapters implement health_check
- [x] All managers implement health_check
- [x] All services implement health_check
- [x] CLI command working
- [x] JSON output working
- [x] Exit codes correct
- [x] Test coverage ≥90%
- [x] Documentation complete
- [x] MCP integration complete

## Timeline Estimate

- Phase 1-2 (Core): 2-3 hours
- Phase 3-5 (Implementation): 4-5 hours
- Phase 6 (CLI): 2-3 hours
- Phase 7 (MCP): 1-2 hours
- Phase 8 (Testing): 2-3 hours

**Total**: 11-16 hours

## Risks and Mitigations

### Risk 1: Breaking existing health_check() -> bool
**Mitigation**: Keep bool return, add new method with different name or overload

### Risk 2: Too many health checks slow down CLI
**Mitigation**: Make health checks async, add timeout, cache results

### Risk 3: Health checks themselves fail
**Mitigation**: Wrap health checks in try/except, return "unhealthy" on error

### Risk 4: Test coverage too low
**Mitigation**: Prioritize testing, aim for ≥90%, add edge case tests

## Future Enhancements

- Health check history tracking
- Performance metrics in health checks
- Alert system for degraded/unhealthy components
- Health check dashboard
- Scheduled health checks
- Health check result caching
