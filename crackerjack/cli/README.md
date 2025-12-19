> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | [CLI](./README.md)

# CLI

Command-line interface handlers and option processing for the Crackerjack CLI using Click and Typer frameworks.

## Overview

The CLI package provides the primary user interface for Crackerjack, handling command-line arguments, option validation, and routing to appropriate backend handlers. It follows a modular handler-based architecture with 90% ACB compliance, using protocol-based dependency injection for most components.

## Architecture

### Entry Point Flow

```
python -m crackerjack [options]
    ↓
__main__.py
    ↓
options.py (Option parsing & validation)
    ↓
handlers/ (Specialized command handlers)
    ↓
Managers/Orchestration (Backend coordination)
```

### Core Components

- **options.py**: CLI option definitions, validation, and parsing using Pydantic models
- **handlers.py**: Main command handlers for quality workflows
- **facade.py**: CLI facade for simplified command routing
- **interactive.py**: Interactive mode for guided workflows
- **utils.py**: CLI utility functions

### Handler Modules

**handlers/** — Specialized command handlers by feature:

- **main_handlers.py**: Core quality workflow execution (fast, comprehensive, tests)
- **analytics.py**: Coverage analytics, metrics, and reporting
- **monitoring.py**: Health monitoring, watchdog, and status checks
- **documentation.py**: Documentation generation and changelog automation
- **changelog.py**: Changelog management and versioning
- **coverage.py**: Coverage ratchet and improvement workflows
- **ai_features.py**: AI agent integration and auto-fixing
- **advanced.py**: Advanced features and experimental workflows
- **config_handlers.py**: Configuration management and initialization

### Cache Handlers

- **cache_handlers.py**: Basic cache management operations
- **cache_handlers_enhanced.py**: Advanced cache operations with pattern analysis
- **semantic_handlers.py**: Semantic search and code comprehension handlers

## Command Categories

### Quality Workflows

```bash
# Fast hooks (~5s)
python -m crackerjack --fast

# Comprehensive hooks (~30s)
python -m crackerjack --comp

# Full quality + tests
python -m crackerjack --run-tests

# AI-powered auto-fixing
python -m crackerjack --ai-fix --run-tests
```

### Publishing & Versioning

```bash
# Interactive versioning
python -m crackerjack --publish interactive

# Automated bump
python -m crackerjack --publish patch  # or minor, major, auto

# Full release workflow
python -m crackerjack --all patch
```

### MCP Server Management

```bash
# Start MCP server
python -m crackerjack --start-mcp-server

# Restart server
python -m crackerjack --restart-mcp-server

# Health monitoring
python -m crackerjack --watchdog
```

### Coverage & Analytics

```bash
# Coverage report
python -m crackerjack --coverage-report

# Analytics dashboard
python -m crackerjack --analytics

# Benchmark performance
python -m crackerjack --benchmark
```

### Development Modes

```bash
# Fast iteration (skip comprehensive hooks)
python -m crackerjack --fast-iteration

# Run specific tool only
python -m crackerjack --tool ruff

# Changed files only
python -m crackerjack --changed-only

# Debug mode
python -m crackerjack --debug --verbose
```

## Option Processing

### Option Validation

The `Options` Pydantic model provides type-safe option parsing with validation:

```python
from crackerjack.cli.options import Options, BumpOption

# Parse and validate options
options = Options(run_tests=True, ai_fix=True, test_workers=4, publish=BumpOption.patch)
```

### Bump Options

Versioning options with enum validation:

- **patch**: 1.0.0 → 1.0.1 (bug fixes)
- **minor**: 1.0.0 → 1.1.0 (new features)
- **major**: 1.0.0 → 2.0.0 (breaking changes)
- **interactive**: Guided version selection
- **auto**: AI-powered version recommendation

### Test Workers

Parallel test execution configuration:

```bash
--test-workers 0   # Auto-detect (default, recommended)
--test-workers 4   # Explicit worker count
--test-workers 1   # Sequential execution (debugging)
--test-workers -2  # Fractional (half cores)
```

## Handler Architecture

### Protocol-Based Dependency Injection

Most handlers use ACB dependency injection (90% compliance):

```python
from acb.depends import depends, Inject
from crackerjack.models.protocols import Console, CrackerjackCache


@depends.inject
def handle_quality_check(
    console: Inject[Console] = None,
    cache: Inject[CrackerjackCache] = None,
) -> None:
    console.print("[green]Running quality checks...[/green]")
    # ... handler logic
```

### Handler Routing

Handlers are organized by feature domain for maintainability:

```python
# Main quality workflows
from crackerjack.cli.handlers.main_handlers import (
    handle_fast_hooks,
    handle_comprehensive_hooks,
    handle_tests,
)

# Analytics and reporting
from crackerjack.cli.handlers.analytics import (
    handle_coverage_report,
    handle_analytics_dashboard,
)

# MCP server management
from crackerjack.cli.handlers.monitoring import (
    handle_start_mcp_server,
    handle_watchdog,
)
```

## Interactive Mode

Guided workflows with prompts and validation:

```bash
python -m crackerjack --interactive
```

**Features:**

- Step-by-step guidance
- Option validation with helpful errors
- Confirmation prompts for destructive actions
- Progress indicators for long operations

## Facade Pattern

The `CrackerjackCLIFacade` provides simplified command routing:

```python
from crackerjack.cli.facade import CrackerjackCLIFacade

facade = CrackerjackCLIFacade()
result = await facade.run_quality_workflow(fast=True, ai_fix=True, verbose=True)
```

**Note:** Facade needs DI integration (currently manual instantiation).

## Usage Examples

### Adding a New CLI Option

```python
# 1. Add to Options model (options.py)
class Options(BaseModel):
    my_new_option: bool = False


# 2. Add Click/Typer parameter (__main__.py)
@click.option("--my-new-option", is_flag=True, help="Enable new feature")
# 3. Create handler (handlers/my_feature.py)
@depends.inject
def handle_my_feature(console: Inject[Console] = None) -> None:
    console.print("[cyan]Running new feature...[/cyan]")


# 4. Route in main (__main__.py)
if options.my_new_option:
    handle_my_feature()
```

### Adding a New Handler Module

```python
# handlers/my_handlers.py
from acb.depends import depends, Inject
from crackerjack.models.protocols import Console


@depends.inject
async def handle_my_command(
    arg1: str,
    console: Inject[Console] = None,
) -> bool:
    """Handler for my custom command."""
    console.print(f"Processing: {arg1}")
    # ... implementation
    return True
```

## Best Practices

1. **Use Protocol-Based DI**: Import from `models/protocols.py`, not concrete classes
1. **Validate Options Early**: Use Pydantic validators in the `Options` model
1. **Keep Handlers Focused**: Single responsibility per handler
1. **Provide User Feedback**: Use rich console for progress and status
1. **Handle Errors Gracefully**: Catch exceptions and provide helpful error messages
1. **Support --verbose**: Add verbose logging for troubleshooting
1. **Document Options**: Clear help text for all CLI options
1. **Test Interactive Flows**: Verify prompts and validation work correctly

## Anti-Patterns to Avoid

```python
# ❌ Direct console instantiation
from rich.console import Console
console = Console()

# ✅ Use dependency injection
@depends.inject
def handler(console: Inject[Console] = None):
    console.print("...")


# ❌ Complex logic in option parsing
@click.option("--complex")
def command(complex):
    if complex:
        # 50 lines of logic here

# ✅ Delegate to handlers
@click.option("--complex")
def command(complex):
    if complex:
        handle_complex_workflow()


# ❌ Silent failures
def handler():
    try:
        risky_operation()
    except Exception:
        pass  # Don't do this!

# ✅ Inform the user
def handler():
    try:
        risky_operation()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise
```

## Configuration

CLI behavior can be customized via `settings/crackerjack.yaml`:

```yaml
# CLI defaults
verbose: false
interactive: false
test_workers: 0  # Auto-detect
debug: false
ai_debug: false

# Feature flags
experimental_hooks: false
async_mode: true
```

## Troubleshooting

### Option Parsing Issues

```bash
# Enable debug mode for detailed output
python -m crackerjack --debug --verbose

# Check option values
python -m crackerjack --help
```

### Handler Failures

```bash
# Use verbose mode for detailed logs
python -m crackerjack --verbose --run-tests

# Enable AI debugging for agent issues
python -m crackerjack --ai-debug --ai-fix
```

### Test Worker Configuration

```bash
# Sequential execution for debugging flaky tests
python -m crackerjack --run-tests --test-workers 1

# Disable auto-detection globally
export CRACKERJACK_DISABLE_AUTO_WORKERS=1
```

## Related

- [Managers](../managers/README.md) — Backend managers called by CLI handlers
- [Orchestration](../orchestration/README.md) — Workflow orchestration layer
- [Options](./options.py) — Full list of CLI options
- [Main README](../../README.md) — Command examples and workflows
- [CLAUDE.md](../../docs/guides/CLAUDE.md) — Essential commands reference

## Future Enhancements

- [ ] Complete DI integration for CrackerjackCLIFacade
- [ ] Plugin system for custom commands
- [ ] Command auto-completion (shell integration)
- [ ] Configuration profiles (dev, ci, production)
- [ ] Command aliasing and shortcuts
- [ ] Enhanced interactive mode with TUI
