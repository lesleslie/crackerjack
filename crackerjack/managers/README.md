> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | [Managers](./README.md)

# Managers

Manager classes that coordinate components, resources, and state for quality enforcement, testing, and publishing workflows.

## Overview

The managers package provides high-level coordination classes that sit between the orchestration layer and services/adapters. Managers handle domain-specific coordination (hooks, tests, publishing) with protocol-based dependency injection and standardized lifecycle management.

## Core Components

### Hook Management

- **hook_manager.py**: Synchronous hook execution manager

  - Direct adapter invocation (no pre-commit wrapper)
  - Hook lifecycle management (init, execute, cleanup)
  - Result aggregation and reporting
  - Retry logic for formatting hooks
  - Fast (~5s) and comprehensive (~30s) hook stages
  - Protocol-based dependency injection

- **async_hook_manager.py**: Asynchronous hook execution manager

  - Async-first architecture for parallel execution
  - Up to 11 concurrent adapters
  - Non-blocking I/O operations
  - Real-time progress streaming
  - WebSocket integration for monitoring
  - Event-driven coordination

### Publishing

- **publish_manager.py**: PyPI publishing and version management
  - Semantic versioning (patch, minor, major, auto)
  - UV-based publishing workflow
  - Secure authentication (keyring, environment variables)
  - Git tagging and release management
  - Changelog integration
  - Pre-publish validation

## Architecture

### Manager Layer Position

```
CLI Handlers (90% compliant)
    ↓
Managers (80% compliant) ← You are here
    ↓
Services (95% compliant) + Adapters (varies)
    ↓
External Tools (ruff, zuban, pytest, etc.)
```

### ACB Compliance Status

Based on Phase 2-4 refactoring audit:

| Manager | Compliance | Status | Notes |
|---------|-----------|--------|-------|
| HookManager | 85% | ✅ Good | Protocol-based injection, some manual instantiation |
| AsyncHookManager | 80% | ✅ Good | Async patterns, needs protocol standardization |
| PublishManager | 75% | ⚠️ Mixed | Some legacy patterns, mostly good |

**Common Improvements Needed:**

- Remove manual service instantiation
- Standardize protocol imports from `models/protocols.py`
- Eliminate factory functions in favor of DI

### Dependency Injection Pattern

Managers use ACB dependency injection:

```python
from acb.depends import depends, Inject
from crackerjack.models.protocols import Console, TestManagerProtocol


@depends.inject
class HookManager:
    def __init__(
        self,
        console: Inject[Console] = None,
        test_manager: Inject[TestManagerProtocol] = None,
    ) -> None:
        self.console = console
        self.test_manager = test_manager

    async def init(self) -> None:
        # Async initialization
        pass
```

## Usage Examples

### Hook Management

```python
from crackerjack.managers.hook_manager import HookManager
from acb.depends import depends

# Create manager with DI
manager = depends.get(HookManager)
await manager.init()

# Run fast hooks (~5s)
fast_results = await manager.run_fast_hooks()

# Run comprehensive hooks (~30s)
comp_results = await manager.run_comprehensive_hooks()

# Check results
if all(r.passed for r in fast_results):
    print("All fast hooks passed!")
```

### Async Hook Management

```python
from crackerjack.managers.async_hook_manager import AsyncHookManager

manager = AsyncHookManager(max_concurrent=11)
await manager.init()

# Parallel execution with progress tracking
results = await manager.run_hooks_parallel(
    hooks=["ruff", "zuban", "bandit"],
    progress_callback=lambda p: print(f"Progress: {p}%"),
)

# Real-time results as they complete
async for result in manager.stream_hook_results():
    print(f"Hook {result.hook_name}: {'✅' if result.passed else '❌'}")
```

### Publishing

```python
from crackerjack.managers.publish_manager import PublishManager

manager = PublishManager()
await manager.init()

# Bump version and publish
await manager.publish(
    bump_type="patch",  # 1.0.0 → 1.0.1
    create_tag=True,
    push_tag=True,
)

# Check if authentication is configured
if manager.has_pypi_token():
    print("Ready to publish!")
else:
    print("Configure PyPI token first")
```

## Hook Execution Workflow

### Fast Hooks Stage (~5s)

**Purpose:** Rapid feedback for essential checks

**Hooks:**

- Ruff formatting and linting
- Trailing whitespace cleanup
- UV lock file updates
- Security credential detection (gitleaks)
- Spell checking (codespell)

**Retry Logic:**

- Format hooks retry once if they fail (formatting often fixes cascade issues)
- Other hooks don't retry

### Comprehensive Hooks Stage (~30s)

**Purpose:** Thorough static analysis

**Hooks:**

- Zuban type checking (20-200x faster than pyright)
- Bandit security analysis
- Dead code detection (skylos, 20x faster than vulture)
- Dependency analysis (creosote)
- Complexity limits (complexipy ≤15 per function)
- Modern Python patterns (refurb)

**Execution:**

- All hooks run, collecting ALL failures (don't stop on first)
- Results aggregated for batch AI fixing
- Real-time console output

## Publishing Workflow

### Version Bumping

```python
# Semantic versioning
"patch":  1.0.0 → 1.0.1  # Bug fixes
"minor":  1.0.0 → 1.1.0  # New features
"major":  1.0.0 → 2.0.0  # Breaking changes
"auto":   AI recommends based on changelog
```

### Publishing Steps

1. **Pre-validation**

   - All quality hooks must pass
   - Tests must pass
   - No uncommitted changes

1. **Version Bump**

   - Update `pyproject.toml`
   - Update `__version__.py`
   - Generate changelog entry

1. **Git Operations**

   - Commit version bump
   - Create git tag (v1.0.1)
   - Push to remote

1. **Build & Publish**

   - Build package with UV
   - Publish to PyPI
   - Verify upload

### Authentication

```bash
# Method 1: Keyring (most secure)
keyring set https://upload.pypi.org/legacy/ __token__
# Enter: pypi-your-token-here

# Method 2: Environment variable
export UV_PUBLISH_TOKEN=pypi-your-token-here

# Method 3: .env file (local development)
echo "UV_PUBLISH_TOKEN=pypi-your-token-here" > .env
```

## Configuration

Managers are configured via `settings/crackerjack.yaml`:

```yaml
# Hook Management
max_parallel_hooks: 11
hook_timeout: 60
fast_hook_retry: true

# Publishing
auto_git_tag: true
require_clean_working_tree: true
publish_on_tag: false

# Testing
test_workers: 0  # Auto-detect
test_timeout: 300
```

## Best Practices

1. **Use DI**: Always get managers via `depends.get(ManagerClass)`
1. **Initialize Async**: Call `await manager.init()` before use
1. **Handle Results**: Check all hook results, don't assume success
1. **Retry Formatting**: Let format hooks retry once (they fix cascade issues)
1. **Validate Before Publish**: Always run quality + tests before publishing
1. **Secure Tokens**: Use keyring, never commit tokens
1. **Tag Releases**: Always create git tags for versions
1. **Monitor Progress**: Use progress callbacks for long operations
1. **Batch Failures**: Collect all failures before fixing (don't stop on first)
1. **Use Real-time Output**: Async managers provide better UX

## Anti-Patterns to Avoid

```python
# ❌ Manual service instantiation
self.git_service = GitService()


# ✅ Use dependency injection
@depends.inject
def __init__(self, git: Inject[GitServiceProtocol] = None):
    self.git = git


# ❌ Factory functions
self.logger = get_logger()


# ✅ Inject dependencies
@depends.inject
def __init__(self, logger: Inject[Logger] = None):
    self.logger = logger


# ❌ Stopping on first failure
for hook in hooks:
    result = hook.run()
    if not result.passed:
        break  # Don't do this!

# ✅ Collect all failures
results = [hook.run() for hook in hooks]
failures = [r for r in results if not r.passed]
```

## Troubleshooting

### Hooks Timing Out

```python
# Increase timeout for specific hooks
manager.set_hook_timeout("zuban", 120)

# Or globally
manager.hook_timeout = 120
```

### Publishing Failures

```bash
# Check authentication
keyring get https://upload.pypi.org/legacy/ __token__

# Verify package builds
uv build

# Check PyPI connectivity
curl -I https://upload.pypi.org/legacy/
```

### Parallel Execution Issues

```python
# Reduce concurrency
manager.max_concurrent = 5

# Or run sequentially for debugging
manager.max_concurrent = 1
```

## Related

- [Services](../services/README.md) — Services used by managers
- [Adapters](../adapters/README.md) — Adapters managed by hook managers
- [CLI](../cli/README.md) — CLI handlers that use managers
- [Main README](../../README.md) — Overall workflow overview

## Future Enhancements

- [ ] Complete migration to ACB dependency injection (remove manual instantiation)
- [ ] Standardize async/sync patterns
- [ ] Add manager health checks and metrics
- [ ] Implement circuit breaker for external services
- [ ] Add manager benchmarking
- [ ] Create manager plugin system
- [ ] Improve error recovery and rollback
