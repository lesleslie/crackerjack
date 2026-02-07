# Crackerjack Admin Shell

The Crackerjack admin shell provides an interactive IPython environment for quality management and testing automation.

## Quick Start

```bash
# Start the admin shell
crackerjack shell
```

## Features

### Quality Check Functions

The shell provides convenient functions for running quality checks:

- **`crack()`** - Run comprehensive quality checks (all checks in sequence)
- **`test()`** - Run test suite with coverage
- **`lint()`** - Run linting (ruff check + format)
- **`scan()`** - Run security scan (bandit)
- **`format_code()`** - Format code with ruff
- **`typecheck()`** - Run type checking (mypy)

### Inspection Functions

- **`show_adapters()`** - Show enabled QA adapters
- **`show_hooks()`** - Show configured pre-commit hooks

## Session Tracking

The admin shell integrates with Session-Buddy MCP to track shell sessions:

- **Component Name**: `crackerjack`
- **Component Type**: `inspector` (validates other components)
- **Metadata**:
  - Version
  - Enabled adapters
  - Project root

## Example Session

```python
$ crackerjack shell

Crackerjack Admin Shell v0.51.0
============================================================
Quality & Testing Automation for Python Projects

Role: Inspector (validates other components)

Session Tracking: Enabled
  Shell sessions tracked via Session-Buddy MCP
  Metadata: version, adapters, quality metrics

Convenience Functions:
  crack()         - Run comprehensive quality checks
  test()          - Run test suite with coverage
  lint()          - Run linting (ruff check + format)
  scan()          - Run security scan (bandit)
  format_code()   - Format code with ruff
  typecheck()     - Run type checking (mypy)
  show_adapters() - Show enabled QA adapters
  show_hooks()    - Show configured pre-commit hooks

Type 'help()' for Python help or %help_shell for shell commands
============================================================

In [1]: crack()  # Run all quality checks
Running comprehensive quality checks...

In [2]: test()  # Run tests only
Running test suite...

In [3]: lint()  # Check code quality
Running linting...
✓ Linting passed

In [4]: exit()  # Exit shell (emits session end event)
```

## Architecture

The admin shell extends the Oneiric `AdminShell` base class with Crackerjack-specific functionality:

```
oneiric.shell.AdminShell
    └── crackerjack.shell.CrackerjackShell
```

### Key Components

1. **Adapter** (`crackerjack/shell/adapter.py`)
   - Extends `AdminShell` with quality management features
   - Implements session tracking via Session-Buddy MCP
   - Provides quality check functions

2. **Session Tracker** (`oneiric/shell/session_tracker.py`)
   - Emits session start/end events
   - Tracks metadata (version, adapters, project root)
   - Integrates with Session-Buddy MCP

3. **Namespace Helpers**
   - Quality functions (crack, test, lint, scan)
   - Inspection functions (show_adapters, show_hooks)
   - Configuration objects

## Configuration

The shell uses the standard Crackerjack settings:

```python
from crackerjack.config import load_settings, CrackerjackSettings

settings = load_settings(CrackerjackSettings)
```

## Requirements

- Python 3.13+
- IPython 8.0+
- Oneiric 0.3.2+
- Rich 14.2.0+

## Integration with Other Tools

### Session-Buddy MCP

Session tracking is automatically enabled when Session-Buddy MCP is available:

```python
# Session start event emitted on shell startup
await session_tracker.emit_session_start(
    shell_type="CrackerjackShell",
    metadata={
        "version": "0.51.0",
        "adapters": ["pytest", "ruff", "mypy", "bandit"],
        "component_type": "inspector",
        "project_root": "/path/to/project",
    }
)

# Session end event emitted on shell exit
await session_tracker.emit_session_end(
    session_id="session_abc123",
    metadata={}
)
```

### QA Adapters

The shell interfaces with these QA adapters:

- **pytest** - Test runner with coverage
- **ruff** - Linter and formatter
- **mypy** - Static type checker
- **bandit** - Security linter

## Development

### Running Tests

```bash
# Run shell tests
pytest tests/unit/shell/

# Run with coverage
pytest --cov=crackerjack.shell tests/unit/shell/
```

### Adding New Helpers

To add a new helper function:

1. Add the function to `_add_crackerjack_namespace()` in `adapter.py`:

```python
def _add_crackerjack_namespace(self) -> None:
    self.namespace.update({
        "my_helper": lambda: asyncio.run(self._my_helper()),
    })
```

2. Implement the async function:

```python
async def _my_helper(self) -> None:
    """Helper implementation."""
    self.console.print("[cyan]Running my helper...[/cyan]")
    # Implementation
```

3. Update the banner to document the new function:

```python
def _get_banner(self) -> str:
    return f"""
    ...
    my_helper()    - Description of helper
    """
```

## Troubleshooting

### Session Tracking Not Working

If session tracking is not working:

1. Check Session-Buddy MCP is running on port 8678
2. Verify oneiric dependency is installed: `pip list | grep oneiric`
3. Check logs for errors: `journalctl -u crackerjack -f`

### Quality Checks Failing

If quality checks fail:

1. Run individual checks to identify the issue:
   ```python
   lint()      # Check linting
   typecheck() # Check types
   scan()      # Check security
   ```
2. Check tool installation:
   ```bash
   which ruff
   which mypy
   which bandit
   ```
3. Run checks directly for more detail:
   ```bash
   ruff check .
   mypy crackerjack/
   bandit -r crackerjack/
   ```

## Future Enhancements

Potential improvements:

- [ ] Add tab completion for quality commands
- [ ] Add magic commands for quick quality checks
- [ ] Add quality metrics dashboard
- [ ] Add historical quality trends
- [ ] Add fix suggestions for failed checks
- [ ] Add parallel check execution
