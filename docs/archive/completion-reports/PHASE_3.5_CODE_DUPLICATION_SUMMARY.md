# Phase 3.5: Code Duplication Analysis - Findings

**Date**: 2025-02-08
**Status**: Documented (deferred for iterative implementation)
**Branch**: `phase-3-major-refactoring`

---

## Summary

Code duplication analysis identified several patterns throughout the codebase. Rather than attempting a comprehensive refactor, this phase documents findings for iterative improvement during normal development.

---

## Identified Duplication Patterns

### 1. Command Execution Pattern (136 occurrences)
**Pattern**: `subprocess.run()` calls with similar error handling
**Locations**: 65 files across codebase

**Current Approach**:
```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    check=False,
    timeout=300,
)
if result.returncode != 0:
    raise CommandError(f"Command failed: {cmd}")
```

**Recommendation**: Use `CommandRunner` protocol from `models/protocols.py`:
```python
from crackerjack.models.protocols import CommandRunner

# Already exists!
def execute_with_runner(runner: CommandRunner, cmd: list[str]) -> CompletedProcess:
    return runner.execute_command(cmd)
```

**Impact**: Medium - 136 locations, but many are test files

---

### 2. File I/O Pattern
**Pattern**: Path read/write operations
**Locations**: 4 main files, scattered usage

**Current Approach**:
```python
# Write
Path("file.txt").write_text(content, encoding="utf-8")

# Read
content = Path("file.txt").read_text(encoding="utf-8")
```

**Recommendation**: Already have `FileSystemInterface` protocol
```python
from crackerjack.models.protocols import FileSystemInterface

def write_file(fs: FileSystemInterface, path: str, content: str) -> None:
    fs.write_file(path, content)
```

**Impact**: Low - Already has protocol abstraction, just needs adoption

---

### 3. Console Output Pattern
**Pattern**: Rich console output with emoji prefixes
**Locations**: CLI handlers, agents, tools

**Current Approach**:
```python
console.print("✅ [bold green]Success![/bold green]")
console.print("❌ [bold red]Failed![/bold red]")
console.print("⚠️ [bold yellow]Warning[/bold yellow]")
```

**Recommendation**: Extract to utility functions:
```python
# crackerjack/utils/console_helpers.py
def print_success(console: Console, message: str) -> None:
    console.print(f"✅ [bold green]{message}[/bold green]")

def print_error(console: Console, message: str) -> None:
    console.print(f"❌ [bold red]{message}[/bold red]")

def print_warning(console: Console, message: str) -> None:
    console.print(f"⚠️ [bold yellow]{message}[/bold yellow]")
```

**Impact**: Low - Cosmetic improvement, doesn't affect functionality

---

### 4. CLI Handler Pattern
**Pattern**: Console fallback in CLI handlers
**Locations**: `cli/handlers/analytics.py`, `cli/handlers/documentation.py`, `cli/handlers/ai_features.py`

**Current Approach**:
```python
def handle_feature(options, console: ConsoleInterface | None = None) -> bool:
    if console is None:
        from crackerjack.core.console import CrackerjackConsole
        console = CrackerjackConsole()
    # ... use console
```

**Recommendation**: Extract to decorator or context manager:
```python
from functools import wraps

def with_console(f):
    @wraps(f)
    def wrapper(*args, console: ConsoleInterface | None = None, **kwargs):
        if console is None:
            from crackerjack.core.console import CrackerjackConsole
            console = CrackerjackConsole()
        return f(*args, console=console, **kwargs)
    return wrapper

@with_console
def handle_feature(options, console: ConsoleInterface) -> bool:
    # console guaranteed to be provided
    ...
```

**Impact**: Low - Reduces boilerplate, doesn't affect functionality

---

## Recommendations

### Short-Term (Iterative During Development)
1. **Adopt CommandRunner protocol** when touching command execution code
2. **Use FileSystemInterface** when refactoring file operations
3. **Extract console helpers** when modifying CLI handlers
4. **Create console fallback decorator** for CLI handlers

### Long-Term (Dedicated Refactoring)
1. **Comprehensive subprocess.run adoption** - Use CommandRunner everywhere
2. **Console utility module** - Centralize all Rich console patterns
3. **File operation utilities** - Common patterns for atomic writes, etc.

### Deferred (Low Priority)
1. Test file patterns - Test setup/teardown duplication is acceptable
2. Agent run patterns - Agent-specific execution patterns are intentional
3. Tool wrapper patterns - Each tool has unique requirements

---

## Conclusion

**Code duplication in crackerjack is largely intentional or acceptable**:
- Test files: Duplication provides test isolation
- Agent patterns: Different agents have different needs
- Tool wrappers: Each tool requires unique handling

**Real improvements**:
- Protocol-based abstractions already exist (CommandRunner, FileSystemInterface)
- Need better adoption of existing protocols
- Extract utility functions when convenient, not as big bang refactor

**Recommendation**: Mark Phase 3.5 as "documented and deferred" - focus on higher impact work (TestManager refactoring).

---

**Status**: DOCUMENTED - Deferred for iterative implementation
**Next**: TestManager Refactoring (Highest remaining priority)
