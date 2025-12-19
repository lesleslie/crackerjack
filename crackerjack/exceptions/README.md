> Crackerjack Docs: [Main](../../README.md) | [Crackerjack Package](../README.md) | [Exceptions](./README.md)

# Exceptions

Custom exception types with rich formatting and context-aware error reporting. Provides enhanced UX for tool execution failures and configuration issues.

## Exception Hierarchy

```
BaseException
└── Exception
    ├── ToolExecutionError         # Rich tool execution failures
    └── ConfigIntegrityError       # Configuration validation issues
```

## Custom Exception Types

### ToolExecutionError

Enhanced error with rich formatting for failed tool executions. Provides detailed context including exit codes, stdout/stderr, duration, and actionable suggestions.

**Features:**

- Rich console formatting with syntax highlighting
- Automatic output truncation for readability
- Actionable error messages with suggestions
- Context tracking (command, cwd, duration)
- Integration with Crackerjack's console system

**Constructor:**

```python
ToolExecutionError(
    tool: str,              # Tool name that failed
    exit_code: int,         # Process exit code
    stdout: str = "",       # Standard output
    stderr: str = "",       # Standard error
    command: list[str] | None = None,   # Full command executed
    cwd: Path | None = None,            # Working directory
    duration: float | None = None,      # Execution duration (seconds)
)
```

**Usage Example:**

```python
from crackerjack.exceptions import ToolExecutionError
from pathlib import Path

try:
    result = subprocess.run(
        ["ruff", "check", "."], capture_output=True, text=True, cwd=project_dir
    )
    if result.returncode != 0:
        raise ToolExecutionError(
            tool="ruff",
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            command=["ruff", "check", "."],
            cwd=project_dir,
            duration=2.5,
        )
except ToolExecutionError as e:
    # Rich formatted output
    console.print(e.format_rich())

    # Or get actionable message
    print(e.get_actionable_message())
```

**Rich Formatting:**

```python
from acb.console import Console

console = Console()

# Create error
error = ToolExecutionError(
    tool="pytest",
    exit_code=1,
    stderr="test_example.py::test_feature FAILED",
    duration=3.2,
)

# Display with rich formatting
panel = error.format_rich(console)
console.print(panel)
```

**Output:**

```
╭─ ❌ Tool Execution Failed: pytest ─────────────╮
│ Tool: pytest                                   │
│ Exit Code: 1                                   │
│ Duration: 3.20s                                │
│                                                │
│ Error Output:                                  │
│   test_example.py::test_feature FAILED         │
╰────────────────────────────────────────────────╯
```

**Actionable Messages:**

The `get_actionable_message()` method provides smart error pattern detection:

```python
error = ToolExecutionError(
    tool="ruff", exit_code=1, stderr="ModuleNotFoundError: No module named 'requests'"
)

print(error.get_actionable_message())
# Output:
# Tool 'ruff' failed with exit code 1
# → Check Python dependencies are installed (try: uv sync)
```

**Common Patterns Detected:**

- Permission denied → Check file permissions
- Command not found → Ensure tool is installed
- Timeout errors → Increase timeout setting
- Syntax errors → Check code syntax
- Import errors → Run dependency sync
- Type errors → Fix type annotations
- Out of memory → Reduce batch size

### ConfigIntegrityError

Simple exception for configuration validation and integrity issues.

**Usage Example:**

```python
from crackerjack.exceptions import ConfigIntegrityError


def validate_config(config: dict) -> None:
    if "required_field" not in config:
        raise ConfigIntegrityError(
            "Missing required field 'required_field' in configuration"
        )

    if config.get("version") != "1.0":
        raise ConfigIntegrityError(
            f"Unsupported config version: {config.get('version')}"
        )
```

## Error Handling Patterns

### Pattern 1: Tool Execution with Context

```python
from crackerjack.exceptions import ToolExecutionError
import subprocess
import time


def run_tool(tool: str, args: list[str], cwd: Path) -> bool:
    """Run tool with comprehensive error reporting."""
    start = time.time()

    try:
        result = subprocess.run(
            [tool] + args, capture_output=True, text=True, cwd=cwd, timeout=300
        )

        if result.returncode != 0:
            raise ToolExecutionError(
                tool=tool,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                command=[tool] + args,
                cwd=cwd,
                duration=time.time() - start,
            )

        return True

    except subprocess.TimeoutExpired as e:
        raise ToolExecutionError(
            tool=tool,
            exit_code=-1,
            stderr=f"Tool execution timed out after {e.timeout}s",
            command=[tool] + args,
            cwd=cwd,
            duration=e.timeout,
        ) from e
```

### Pattern 2: Graceful Error Display

```python
from crackerjack.exceptions import ToolExecutionError
from acb.console import Console
from acb.depends import depends


@depends.inject
def execute_with_nice_errors(func: callable, console: Console = depends()) -> bool:
    """Execute function with rich error formatting."""
    try:
        return func()
    except ToolExecutionError as e:
        console.print(e.format_rich())
        console.print(f"\n[yellow]{e.get_actionable_message()}[/yellow]")
        return False
```

### Pattern 3: Config Validation

```python
from crackerjack.exceptions import ConfigIntegrityError
from pathlib import Path
import yaml


def load_and_validate_config(path: Path) -> dict:
    """Load config with integrity validation."""
    if not path.exists():
        raise ConfigIntegrityError(f"Configuration file not found: {path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    required = ["version", "project_name", "settings"]
    missing = [k for k in required if k not in config]

    if missing:
        raise ConfigIntegrityError(
            f"Missing required config fields: {', '.join(missing)}"
        )

    return config
```

## Best Practices

### Use ToolExecutionError for All Tool Failures

Provides consistent, rich error reporting across the codebase:

```python
# ✅ Good - Rich error context
if exit_code != 0:
    raise ToolExecutionError(
        tool="mypy", exit_code=exit_code, stderr=stderr, duration=duration
    )

# ❌ Bad - Generic exception
if exit_code != 0:
    raise RuntimeError(f"mypy failed: {stderr}")
```

### Include All Available Context

More context enables better error messages:

```python
# ✅ Good - Full context
raise ToolExecutionError(
    tool="pytest",
    exit_code=1,
    stdout=result.stdout,
    stderr=result.stderr,
    command=full_command,
    cwd=project_dir,
    duration=elapsed,
)

# ⚠️ Minimal - Missing helpful context
raise ToolExecutionError(tool="pytest", exit_code=1)
```

### Use format_rich() for User-Facing Errors

Provides best UX with Rich console integration:

```python
try:
    run_checks()
except ToolExecutionError as e:
    console.print(e.format_rich())  # Beautiful formatting
    console.print(f"\n{e.get_actionable_message()}")  # Smart suggestions
```

## Implementation Files

- **`tool_execution_error.py`** - ToolExecutionError with rich formatting
- **`config.py`** - ConfigIntegrityError for configuration validation

## Related

- [Decorators](../decorators/README.md) - Error handling decorators
- [MCP](../mcp/README.md) - Error caching and pattern analysis
- [Console Integration](https://github.com/Textualize/rich) - Rich console formatting
