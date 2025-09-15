# Resilient Hook Architecture Implementation Plan

## Problem Analysis

The current crackerjack architecture has a critical weakness: pre-commit hooks call tools directly (e.g., `uv run zuban check`), bypassing the adapter layer that provides health checks and graceful error handling. This causes the entire workflow to crash when tools like Zuban have parsing bugs.

## Current Architecture

```
Pre-commit Hooks → Direct Tool Calls → Tool Crashes → Workflow Failure
     ↓
[Adapters with health checks are bypassed]
```

## Target Architecture

```
Pre-commit Hooks → Resilient Hook Executor → Adapters → Tools
                       ↓                       ↓
              Health Check & Circuit Breaker  Graceful Fallback
```

## Solution: Resilient Hook Executor

### 1. Core Components

#### A. Tool Proxy Command

Create a unified entry point that intercepts tool calls and routes through adapters:

```python
# crackerjack/executors/tool_proxy.py
class ToolProxy:
    """Proxy that routes tool calls through adapters with health checks."""

    def execute_tool(self, tool_name: str, args: list[str]) -> int:
        # Route through appropriate adapter
        # Handle failures gracefully
        # Provide consistent error reporting
```

#### B. Enhanced LSP-Aware Hook Executor

Extend the existing `LSPAwareHookExecutor` to use the tool proxy:

```python
# crackerjack/executors/lsp_aware_hook_executor.py (enhanced)
class LSPAwareHookExecutor:
    def __init__(self, ..., use_tool_proxy: bool = True):
        self.tool_proxy = ToolProxy() if use_tool_proxy else None

    def _execute_hook_with_proxy(self, hook_config):
        # Replace direct tool calls with proxy calls
        # Maintain pre-commit hook interface
```

#### C. Circuit Breaker Pattern

Implement circuit breaker to temporarily disable failing tools:

```python
class CircuitBreaker:
    """Prevents repeated failures from broken tools."""

    def can_execute(self, tool_name: str) -> bool:
        # Check if tool is in failure state

    def record_failure(self, tool_name: str):
        # Track failures and open circuit if needed

    def record_success(self, tool_name: str):
        # Reset circuit breaker on success
```

### 2. Implementation Strategy

#### Phase 1: Tool Proxy Foundation

1. Create `crackerjack/executors/tool_proxy.py`
1. Implement adapter routing logic
1. Add health check integration
1. Create fallback mechanisms

#### Phase 2: Hook Configuration Updates

1. Modify hook configurations to use proxy
1. Update existing executors to support proxy mode
1. Maintain backward compatibility

#### Phase 3: Circuit Breaker Integration

1. Add circuit breaker logic
1. Implement tool health monitoring
1. Add graceful degradation strategies

#### Phase 4: Enhanced Error Reporting

1. Standardize error messages across tools
1. Add tool status dashboard
1. Implement recovery recommendations

### 3. Hook Configuration Changes

Instead of:

```yaml
- id: zuban
  name: zuban
  entry: uv run zuban check
  language: system
  types: [python]
```

Use:

```yaml
- id: zuban
  name: zuban
  entry: python -m crackerjack.executors.tool_proxy zuban check
  language: system
  types: [python]
```

### 4. Adapter Integration Points

#### A. Health Check Interface

```python
class ToolHealthChecker:
    def check_tool_health(self, tool_name: str) -> ToolHealthStatus:
        """Check if tool is functional."""

    def get_fallback_recommendations(self, tool_name: str) -> list[str]:
        """Get alternative tools when primary fails."""
```

#### B. Graceful Degradation

```python
class GracefulDegradationHandler:
    def handle_tool_failure(self, tool_name: str, error: Exception) -> ToolResult:
        """Provide graceful fallback when tools fail."""

    def suggest_alternatives(self, tool_name: str) -> list[str]:
        """Suggest alternative tools or actions."""
```

### 5. Error Handling Strategies

#### A. Tool-Specific Strategies

- **Zuban**: Fall back to pyright when TOML parsing fails
- **Skylos**: Fall back to vulture when not available
- **Ruff**: Continue without formatting if crashes
- **Bandit**: Skip security checks with warning if fails

#### B. Circuit Breaker Thresholds

- **Open Circuit**: 3 consecutive failures within 5 minutes
- **Half-Open**: Retry after 2 minutes in open state
- **Close Circuit**: 2 consecutive successes after half-open

#### C. User Communication

- Clear error messages explaining what failed and why
- Actionable recommendations for fixing issues
- Progress indication when using fallback tools

### 6. Monitoring and Observability

#### A. Tool Health Dashboard

```python
class ToolHealthDashboard:
    def get_tool_status(self) -> dict[str, ToolStatus]:
        """Get current status of all tools."""

    def get_failure_history(self) -> list[ToolFailure]:
        """Get recent tool failure history."""
```

#### B. Metrics Collection

- Tool execution times
- Failure rates by tool
- Fallback usage statistics
- Circuit breaker state changes

### 7. Benefits of This Architecture

#### A. Resilience

- One broken tool doesn't crash entire workflow
- Automatic fallback to alternative tools
- Circuit breaker prevents repeated failures

#### B. Maintainability

- Centralized tool health management
- Consistent error handling across all tools
- Easy to add new tools with resilience patterns

#### C. User Experience

- Clear feedback when tools fail
- Automatic recovery where possible
- Actionable error messages

#### D. Performance

- Failed tools are quickly bypassed
- Health checks prevent unnecessary executions
- LSP integration still provides speed benefits

### 8. Implementation Checklist

- [ ] Create `ToolProxy` class with adapter routing
- [ ] Implement `CircuitBreaker` pattern
- [ ] Enhance `LSPAwareHookExecutor` with proxy support
- [ ] Update hook configurations to use proxy
- [ ] Add tool health monitoring
- [ ] Implement graceful degradation handlers
- [ ] Create tool health dashboard
- [ ] Add comprehensive error messaging
- [ ] Write tests for failure scenarios
- [ ] Document new architecture patterns

### 9. Backward Compatibility

The new architecture maintains full backward compatibility:

- Existing hook configurations continue to work
- Direct tool calls still supported (bypass proxy)
- Gradual migration path available
- No breaking changes to public APIs

### 10. Future Enhancements

- **Smart Tool Selection**: Automatically choose best tool for context
- **Performance Optimization**: Cache tool health status
- **Distributed Health Checks**: Share tool status across team
- **Auto-Recovery**: Automatic tool updates when fixes available

## Conclusion

This resilient hook architecture transforms crackerjack from a fragile chain that breaks with any tool failure into a robust system that gracefully handles failures while maintaining the benefits of the existing adapter pattern. The tool proxy acts as a circuit breaker and router, ensuring that one broken tool cannot bring down the entire quality workflow.
