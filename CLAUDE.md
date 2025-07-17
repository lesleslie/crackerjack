# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crackerjack is an opinionated Python project management tool that streamlines the development lifecycle by combining best-in-class tools into a unified workflow. It manages project setup, enforces code quality standards, runs tests, and assists with publishing Python packages.

## Key Commands

### Environment Setup

```bash
# Install UV (required dependency manager)
pipx install uv

# Install project dependencies
uv sync

# Run individual tools through UV (ensures proper environment isolation)
uv run pytest
uv run pyright
uv run ruff check
uv run pre-commit run --all-files
```

### Running Crackerjack

```bash
# Run basic Crackerjack process (runs pre-commit hooks)
python -m crackerjack

# Clean code, run tests, and commit changes
python -m crackerjack -x -t -c

# Clean code, run tests, bump version (patch), and commit changes
python -m crackerjack -a patch

# Launch interactive workflow interface
python -m crackerjack -i

# Create a pull request
python -m crackerjack -r

# Enable verbose output
python -m crackerjack -v

# Run with fast pre-commit mode (default)
python -m crackerjack

# Run with comprehensive pre-commit checks
python -m crackerjack --comprehensive
```

### Testing

```bash
# Run all tests
python -m crackerjack -t

# Run tests without pre-commit hooks (faster)
python -m crackerjack -t -s

# Run tests with a single worker (no parallelization)
python -m crackerjack -t --test-workers=1

# Run tests with a specific number of workers
python -m crackerjack -t --test-workers=4

# Run tests with a custom timeout (5 minutes per test)
python -m crackerjack -t --test-timeout=300

# Optimize for large projects (fewer workers, longer timeout)
python -m crackerjack -t --test-workers=2 --test-timeout=300

# Run tests in benchmark mode
python -m crackerjack -t --benchmark

# Run tests with benchmark regression detection
python -m crackerjack -t --benchmark-regression

# Run tests with custom benchmark regression threshold
python -m crackerjack -t --benchmark-regression --benchmark-regression-threshold=10.0

# Run tests with AI agent mode for structured output
python -m crackerjack --ai-agent -t
```

### Running a Single Test

```bash
# Run a specific test file
uv run pytest tests/test_crackerjack.py

# Run a specific test function
uv run pytest tests/test_crackerjack.py::test_code_cleaner_remove_docstrings

# Run tests matching a pattern
uv run pytest -k "test_code_cleaner"

# Run with verbose output
uv run pytest -v tests/test_crackerjack.py

# Run with no parallel execution
uv run pytest -n 0 tests/test_crackerjack.py
```

### Benchmark Testing Strategy

Benchmarks should be run automatically at strategic intervals to catch performance regressions early:

#### **Recommended Frequency:**

**🚀 Critical Scenarios (Always Run Benchmarks):**

```bash
# Before major releases
python -m crackerjack -t --benchmark-regression --benchmark-regression-threshold=5.0

# After significant algorithmic changes (manual trigger)
python -m crackerjack -t --benchmark --ai-agent
```

**📊 Regular Monitoring (Weekly):**

```bash
# Weekly automated benchmark monitoring
python -m crackerjack -t --benchmark-regression --benchmark-regression-threshold=10.0
```

**🎲 Random Sampling (10% of commits):**

```bash
# Stochastic performance monitoring (implement in CI/CD)
# Run on ~10% of commits to catch gradual performance drift
python -m crackerjack -t --benchmark
```

#### **When to Run Benchmarks:**

1. **Always:** Before releases, after performance-critical changes
1. **Weekly:** Automated monitoring for performance drift detection
1. **Randomly:** 10% of commits for stochastic performance sampling
1. **On-demand:** When investigating performance issues

#### **Benchmark Thresholds:**

- **5% regression threshold:** For release candidates and critical changes
- **10% regression threshold:** For regular monitoring and development
- **Custom thresholds:** Adjust based on specific performance requirements

### Linting and Code Quality

```bash
# Run pre-commit hooks to check code quality
pre-commit run --all-files

# Update pre-commit hooks to the latest versions
python -m crackerjack -u

# Clean code by removing docstrings, comments, and extra whitespace
python -m crackerjack -x
```

### Documentation Template Management

Crackerjack can automatically propagate its quality standards to other Python projects by creating or updating their CLAUDE.md and RULES.md files. This ensures consistent AI code generation across all projects.

```bash
# Update CLAUDE.md and RULES.md with latest quality standards (only if they don't exist)
python -m crackerjack --update-docs

# Force update CLAUDE.md and RULES.md even if they already exist
python -m crackerjack --force-update-docs
```

**When to Use:**

- **New Projects**: Use `--update-docs` to create initial documentation templates
- **Quality Standard Updates**: Use `--force-update-docs` weekly to keep standards current
- **AI Integration**: Ensures Claude Code generates compliant code on first pass across all projects
- **Team Synchronization**: Keeps all team projects using the same quality standards

**How It Works:**

- Copies the latest Refurb, Pyright, Complexipy, and Bandit standards from Crackerjack
- Customizes project-specific sections (project name, overview)
- Preserves the core quality standards and AI generation guidelines
- Automatically adds files to git for easy committing

### Publishing

```bash
# Bump version (patch/minor/major) and publish to PyPI
python -m crackerjack -p patch
python -m crackerjack -p minor
python -m crackerjack -p major

# Bump version without publishing
python -m crackerjack -b patch
python -m crackerjack -b minor
python -m crackerjack -b major
```

#### PyPI Authentication Setup

Crackerjack provides enhanced PyPI authentication with automatic validation and helpful error messages. Choose one of these authentication methods:

**Method 1: Environment Variable (Recommended)**

```bash
# Set PyPI token as environment variable
export UV_PUBLISH_TOKEN=pypi-your-token-here

# Publish with token authentication
python -m crackerjack -p patch
```

**Method 2: Keyring Integration**

```bash
# Install keyring globally or in current environment
uv tool install keyring

# Store PyPI token in keyring
keyring set https://upload.pypi.org/legacy/ __token__
# Enter your PyPI token when prompted

# Ensure keyring provider is configured in pyproject.toml
[tool.uv]
keyring-provider = "subprocess"

# Publish with keyring authentication
python -m crackerjack -p patch
```

**Method 3: Environment Variable for Keyring Provider**

```bash
# Set keyring provider via environment
export UV_KEYRING_PROVIDER=subprocess

# Publish (will use keyring for authentication)
python -m crackerjack -p patch
```

#### Authentication Validation

Crackerjack automatically validates your authentication setup before publishing and provides helpful feedback:

- ✅ **Token Found**: When UV_PUBLISH_TOKEN is set
- ✅ **Keyring Ready**: When keyring is configured and token is stored
- ⚠️ **Setup Needed**: When authentication needs configuration

If publishing fails due to authentication issues, crackerjack will display helpful setup instructions.

#### PyPI Token Best Practices

1. **Generate Project-Specific Tokens**: Create separate PyPI tokens for each project
1. **Use Scoped Tokens**: Limit token scope to the specific package you're publishing
1. **Secure Storage**: Use environment variables or keyring - never hardcode tokens
1. **Token Format**: PyPI tokens start with `pypi-` (e.g., `pypi-AgEIcHlwaS5vcmcCJGZm...`)

#### Troubleshooting Authentication

If you encounter authentication issues:

1. **Check Token Format**: Ensure your token starts with `pypi-`
1. **Verify Environment Variable**: `echo $UV_PUBLISH_TOKEN` should show your token
1. **Test Keyring**: `keyring get https://upload.pypi.org/legacy/ __token__` should return your token
1. **Check Configuration**: Ensure `keyring-provider = "subprocess"` in pyproject.toml
1. **Install Keyring**: `uv tool install keyring` if using keyring authentication

### Git Operations

```bash
# Commit changes after running pre-commit hooks
python -m crackerjack -c

# Create a pull request to the upstream repository
python -m crackerjack -r
```

## Project Architecture

Crackerjack is designed with modern Python principles and consists of several key components:

### Core Components

1. **Crackerjack** (`crackerjack.py`): Main class that orchestrates the entire workflow

   - Manages configuration updates
   - Runs pre-commit hooks
   - Handles code cleaning (with enhanced error handling)
   - Executes tests with dynamic parallelization
   - Manages version bumping and publishing
   - Handles Git operations
   - Integrates with Rich console for status output

1. **CodeCleaner**: Responsible for cleaning code

   - Removes docstrings (with syntax-aware pass statement insertion)
   - Removes line comments
   - Removes extra whitespace
   - Reformats code using Ruff
   - Handles file encoding issues gracefully

1. **ConfigManager**: Handles configuration file management

   - Updates pyproject.toml settings
   - Manages configuration files (.gitignore, .pre-commit-config.yaml)
   - Supports dynamic configuration based on project size

1. **ProjectManager**: Manages project-level operations

   - Runs pre-commit hooks
   - Updates package configurations
   - Runs interactive hooks
   - Detects project size for optimization

1. **ErrorHandler** (`errors.py`): Structured error handling system

   - Provides consistent error codes and messages
   - Handles graceful degradation on failures
   - Supports both fatal and non-fatal error patterns

### Key Design Patterns

- **Protocol-Based Design**: Uses `t.Protocol` for interface definitions
- **Factory Pattern**: Employs a factory function (`create_crackerjack_runner`) for dependency injection
- **Command Pattern**: CLI commands are mapped to specific operations

### Testing Infrastructure

Crackerjack has a robust testing setup with:

- **Test Configuration**: Customizes pytest through conftest.py with asyncio_mode="auto"
- **Benchmark Support**: Special handling for benchmark tests (disabled in parallel execution)
- **Smart Parallelization**: Adjusts the number of workers based on project size
- **Project Size Detection**: Automatically detects project size to optimize test execution
- **Timeout Protection**: Tests have dynamic timeouts based on project size (default 300s)
- **Deadlock Prevention**: Advanced threading techniques to prevent deadlocks
- **Progress Tracking**: Shows periodic heartbeat messages for long-running tests
- **AI Agent Integration**: Generates structured output files (JUnit XML, JSON coverage, benchmark JSON) when `--ai-agent` flag is used
- **Async Testing**: Configured for asyncio-based tests with automatic mode detection

### Interactive Mode

Crackerjack includes a Rich-based interactive UI that provides:

- **Visual Task Management**: Progress tracking with status indicators (✅❌⏳⏩⏸️)
- **Workflow Confirmation**: Confirm each step in the development workflow
- **Real-time Feedback**: Live updates on task completion with duration tracking
- **Enhanced User Experience**: Modern terminal UI with colors, panels, and tables
- **Task Dependencies**: Visual display of task relationships and execution order

The interactive mode runs a predefined workflow with tasks:

1. **Setup** - Initialize project structure
1. **Config** - Update configuration files
1. **Clean** - Remove docstrings and comments
1. **Hooks** - Run pre-commit hooks
1. **Test** - Execute test suite
1. **Version** - Bump version numbers
1. **Publish** - Publish to PyPI
1. **Commit** - Commit changes to Git

Access interactive mode with: `python -m crackerjack -i`

## Module Organization

Crackerjack follows a single-file architecture for simplicity and maintainability:

### File Structure

- `crackerjack.py` - Main module (~3000 lines) containing all core functionality
- `errors.py` - Structured error handling system
- `interactive.py` - Rich-based interactive UI implementation
- `py313.py` - Python 3.13+ specific feature detection
- `__main__.py` - Entry point for `python -m crackerjack`

### Key Implementation Details

- **Single-file Design**: Most functionality concentrated in `crackerjack.py` for easier maintenance
- **Type Safety**: Extensive use of protocols and type hints throughout
- **Error Handling**: Comprehensive error handling with structured error codes
- **Dynamic Configuration**: Project size detection affects worker count, timeouts, and other settings
- **Rich Integration**: All console output uses Rich for enhanced terminal UI

## CLI Reference

### Core Options

| Flag | Long Form | Description |
|------|-----------|-------------|
| `-c` | `--commit` | Commit changes to Git |
| `-i` | `--interactive` | Launch Rich interactive UI |
| `-t` | `--test` | Run tests |
| `-x` | `--clean` | Remove docstrings, comments, and whitespace |
| `-u` | `--update-precommit` | Update pre-commit hooks |
| | `--update-docs` | Update CLAUDE.md and RULES.md with latest quality standards |
| | `--force-update-docs` | Force update CLAUDE.md and RULES.md even if they exist |
| `-r` | `--pr` | Create pull request |
| `-v` | `--verbose` | Enable verbose output |
| `-s` | `--skip-hooks` | Skip pre-commit hooks |
| `-n` | `--no-config-updates` | Skip configuration updates |
| | `--comprehensive` | Use comprehensive pre-commit hooks (slower but thorough) |

### Version Management

| Flag | Long Form | Description |
|------|-----------|-------------|
| `-p` | `--publish` | Bump version and publish to PyPI |
| `-b` | `--bump` | Bump version only (no publish) |
| `-a` | `--all` | Run full workflow: clean, test, publish, commit |

### Testing Options

| Flag | Description |
|------|-------------|
| `--benchmark` | Run tests in benchmark mode |
| `--benchmark-regression` | Fail on performance regression |
| `--benchmark-regression-threshold` | Set regression threshold (default: 5.0%) |
| `--test-workers` | Number of parallel workers (0=auto, 1=disable) |
| `--test-timeout` | Test timeout in seconds (0=auto) |
| `--ai-agent` | Generate structured output files (hidden flag) |

### Session Progress Tracking

| Flag | Description |
|------|-------------|
| `--track-progress` | Enable session progress tracking with detailed markdown output |
| `--resume-from <file>` | Resume session from existing progress file |
| `--progress-file <path>` | Custom path for progress file (default: SESSION-PROGRESS-{timestamp}.md) |

## Development Guidelines

1. **Code Style**: Follow the Crackerjack style guide (see RULES.md):

   - **Target Python 3.13+** - Use latest Python features
   - **NO DOCSTRINGS** - The codebase standard is to have no docstrings (they are removed by the `-x` flag)
   - Use static typing throughout with modern syntax (import typing as `t`)
   - Use pathlib for file operations
   - Prefer Protocol over ABC
   - Use built-in collection types (`list[str]`, `dict[str, int]`) instead of typing equivalents
   - Leverage Python 3.13+ performance and language improvements

1. **Zen of Python Philosophy**: Follow the Zen of Python principles (PEP 20) in all code:

   - **Beautiful is better than ugly** - Write clean, readable code with clear intent
   - **Explicit is better than implicit** - Be clear about what code does, avoid magic
   - **Simple is better than complex** - Choose simple solutions over complex ones
   - **Complex is better than complicated** - When complexity is needed, keep it organized
   - **Flat is better than nested** - Avoid deep nesting, prefer flat structure
   - **Sparse is better than dense** - Use whitespace and clear formatting
   - **Readability counts** - Prioritize code that humans can easily understand
   - **Special cases aren't special enough to break the rules** - Apply standards consistently
   - **Practicality beats purity** - Favor working solutions over theoretical perfection
   - **Errors should never pass silently** - Handle exceptions explicitly
   - **In the face of ambiguity, refuse the temptation to guess** - Be explicit about assumptions
   - **There should be one obvious way to do it** - Prefer established patterns
   - **Now is better than never** - Don't postpone necessary improvements
   - **If the implementation is hard to explain, it's a bad idea** - Keep solutions understandable
   - **Namespaces are one honking great idea** - Use clear, descriptive names and organization

   **Apply these principles to:**

   - **Crackerjack development**: All contributions should embody Zen principles
   - **Generated code**: AI assistants should generate Zen-compliant code
   - **Project templates**: Code created by crackerjack should follow Zen principles
   - **Documentation**: Examples and templates should demonstrate Zen philosophy
   - **Code reviews**: Evaluate code against Zen principles for quality

1. **Testing Approach**:

   - Write unit tests for all functionality
   - Add benchmark tests for performance-critical code
   - Tests are run in parallel by default
   - **CRITICAL**: Use tempfile module for temporary files in tests (never create files directly on filesystem)
   - Use pytest's `tmp_path` and `tmp_path_factory` fixtures
   - Tests should be isolated and not affect the surrounding environment

1. **Dependencies**:

   - UV for dependency management and tool execution
   - Ruff for linting and formatting
   - Pytest for testing
   - All tools should be run through UV for environment isolation

1. **Python Version**:

   - **Target: Python 3.13+** - Crackerjack requires Python 3.13 or newer
   - Use modern Python 3.13+ features and syntax
   - Code must be compatible with Python 3.13+ only

1. **Version Management**:

   - Version bumping is handled through UV
   - Follows semantic versioning

## Code Quality Compliance

When generating code, AI assistants MUST follow these standards to ensure compliance with Refurb and Bandit pre-commit hooks:

**IMPORTANT: Target Python 3.13+** - All code must be compatible with Python 3.13 or newer. Use the latest Python features and syntax.

**CRITICAL: NO DOCSTRINGS** - Crackerjack's standard is to have NO docstrings in the package code. The `-x` (clean) flag removes all docstrings to reduce noise and keep the codebase clean. When generating code:

- **DO NOT** add docstrings to functions, methods, classes, or modules
- **DO NOT** add triple-quoted string documentation anywhere
- Use inline comments sparingly only when absolutely necessary for complex logic
- The codebase prioritizes clean, self-documenting code over documentation strings

### Refurb Standards (Modern Python Patterns up to 3.13+)

**CRITICAL: Collection and Membership Testing:**

- **FURB109**: Use tuples instead of lists for `in` membership testing

  ```python
  # Bad
  if response in ["y", "yes", "ok"]:

  # Good
  if response in ("y", "yes", "ok"):
  ```

- **FURB120**: Don't pass arguments that are the same as the default value

  ```python
  # Bad
  kwargs.get("resume_from", None)

  # Good
  kwargs.get("resume_from")
  ```

**Use modern syntax and built-ins:**

- Use `pathlib.Path` instead of `os.path` operations
- Use `str.removeprefix()` and `str.removesuffix()` instead of string slicing
- Use `itertools.batched()` for chunking sequences (Python 3.12+)
- Prefer `match` statements over complex `if/elif` chains
- Use `|` for union types instead of `Union` from typing
- Use `dict1 | dict2` for merging instead of `{**dict1, **dict2}`

**Use efficient built-in functions:**

- Use `any()` and `all()` instead of manual boolean loops
- Use list/dict comprehensions over manual loops when appropriate
- Use `enumerate()` instead of manual indexing with `range(len())`
- Use `zip()` for parallel iteration instead of manual indexing

**Resource management:**

- Always use context managers (`with` statements) for file operations
- Use `tempfile` module for temporary files instead of manual paths
- Prefer `subprocess.run()` over `subprocess.Popen()` when possible

**Code Complexity Management (Complexipy):**

- **CRITICAL**: Keep cognitive complexity under 15 per function/method
- Break complex methods into smaller helper functions (3-5 helper functions are better than 1 complex function)
- Use descriptive function names that explain their purpose
- Prefer multiple small functions over one large function
- **Pattern for refactoring complex methods:**
  ```python
  # Bad - High complexity (>15)
  def complex_method(self, data):
      # 50+ lines with multiple nested if/else, loops, etc.

  # Good - Broken into helpers
  def main_method(self, data):
      processed = self._preprocess_data(data)
      result = self._apply_transformations(processed)
      return self._finalize_result(result)

  def _preprocess_data(self, data):
      # Single responsibility

  def _apply_transformations(self, data):
      # Single responsibility

  def _finalize_result(self, data):
      # Single responsibility
  ```

**Example of good patterns:**

```python
# Good: Modern pathlib usage
from pathlib import Path

config_file = Path("config") / "settings.yaml"
if config_file.exists():
    content = config_file.read_text(encoding="utf-8")

# Good: String methods
if name.startswith("test_"):
    name = name.removeprefix("test_")


# Good: Union types (Python 3.13+)
def process_data(data: str | bytes) -> dict[str, Any]:
    pass


# Good: Context managers
with open(file_path, encoding="utf-8") as f:
    data = f.read()
```

### Bandit Security Standards

**Never use dangerous functions:**

- Avoid `eval()`, `exec()`, or `compile()` with any user input
- Never use `subprocess.shell=True` or `os.system()`
- Don't use `pickle` with untrusted data
- Avoid `yaml.load()` - use `yaml.safe_load()` instead

**Cryptography and secrets:**

- Use `secrets` module for cryptographic operations, never `random`
- Never hardcode passwords, API keys, or secrets in source code
- Use environment variables or secure configuration for sensitive data
- Use `hashlib` with explicit algorithms, avoid MD5/SHA1 for security

**File and path security:**

- Always validate file paths to prevent directory traversal
- Use `tempfile.mkstemp()` instead of predictable temporary file names
- Always specify encoding when opening files
- Validate all external inputs before processing

**Database and injection prevention:**

- Use parameterized queries, never string concatenation for SQL
- Validate and sanitize all user inputs
- Use prepared statements for database operations

**Example of secure patterns:**

```python
# Good: Secure random generation
import secrets

token = secrets.token_urlsafe(32)

# Good: Safe subprocess usage
import subprocess

result = subprocess.run(["ls", "-la"], capture_output=True, text=True)

# Good: Secure file operations
import tempfile

with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as f:
    f.write(data)
    temp_path = f.name

# Good: Environment variables for secrets
import os

api_key = os.environ.get("API_KEY")
if not api_key:
    raise ValueError("API_KEY environment variable required")

# Good: Parameterized database queries
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### Pyright Type Safety Standards

**CRITICAL: Complete Type Annotations:**

- **reportMissingParameterType**: ALL function parameters MUST have type hints

  ```python
  # Bad
  def _format_task_detail(self, task) -> str:

  # Good
  def _format_task_detail(self, task: TaskStatus) -> str:
  ```

- **reportArgumentType**: Protocol implementations must match exactly

  ```python
  # Bad - Missing properties in protocol implementation
  class Options(OptionsProtocol):
      verbose = True
      # Missing: resume_from, progress_file


  # Good - Complete protocol implementation
  class Options(OptionsProtocol):
      verbose = True
      resume_from: str | None = None
      progress_file: str | None = None
  ```

**Always use explicit type annotations:**

- Function parameters must have type hints
- Function return types must be annotated
- Class attributes should have type annotations
- Use `from __future__ import annotations` for forward references

**Handle Optional types properly:**

- Use `str | None` instead of `Optional[str]` (required for Python 3.13+)
- Always check for None before using optional values
- Use explicit `assert` statements or type guards when narrowing types

**Generic types and collections:**

- Use `list[str]` instead of `List[str]` (required for Python 3.13+)
- Use `dict[str, Any]` instead of `Dict[str, Any]` (required for Python 3.13+)
- Properly type generic classes with `TypeVar` when needed
- Use `Sequence` or `Iterable` for function parameters when appropriate

**Protocol and ABC usage:**

- Prefer `typing.Protocol` over abstract base classes for duck typing
- Use `@runtime_checkable` when protocols need runtime checks
- Define clear interfaces with protocols
- **CRITICAL**: When implementing protocols, ensure ALL properties are included with correct types

**Python 3.13+ specific features:**

- Leverage improved error messages and performance optimizations
- Use enhanced type system features available in 3.13+
- Take advantage of improved pathlib and asyncio features
- Use any new syntax or standard library improvements

**Import and module organization:**

- Import types in TYPE_CHECKING blocks when needed for forward references
- Use proper module-level `__all__` declarations
- Organize imports: standard library, third-party, local imports

**Example of proper typing:**

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable
from pathlib import Path

if TYPE_CHECKING:
    from collections.abc import Sequence


@runtime_checkable
class Writable(Protocol):
    def write(self, data: str) -> None: ...


def process_files(
    paths: Sequence[Path],
    output: Writable,
    encoding: str = "utf-8",
) -> dict[str, int]:
    """Process files and return statistics."""
    stats: dict[str, int] = {}

    for path in paths:
        if path.exists():
            content = path.read_text(encoding=encoding)
            stats[str(path)] = len(content)
            output.write(f"Processed {path}\n")

    return stats


# Good: Type narrowing with assertion
def validate_config(config: dict[str, str | None]) -> dict[str, str]:
    """Validate that all config values are non-None."""
    validated: dict[str, str] = {}
    for key, value in config.items():
        assert value is not None, f"Config key {key} cannot be None"
        validated[key] = value
    return validated
```

### Integration with Pre-commit Hooks

These standards align with the project's pre-commit hooks:

- **Refurb**: Automatically suggests modern Python patterns
- **Bandit**: Scans for security vulnerabilities
- **Pyright**: Enforces type safety
- **Ruff**: Handles formatting and additional linting
- **pyproject-fmt**: Validates and formats pyproject.toml files
- **Vulture**: Detects unused code (dead code detection)
- **Creosote**: Identifies unused dependencies
- **Complexipy**: Analyzes code complexity
- **Autotyping**: Automatically adds type annotations
- **Codespell**: Fixes common spelling mistakes
- **Detect-secrets**: Prevents credential leaks
- **Standard hooks**: File formatting (trailing whitespace, end-of-file fixes, YAML/TOML validation)

By following these guidelines during code generation, AI assistants will produce code that passes all quality checks without requiring manual fixes.

### AI Code Generation Best Practices

**MANDATORY: Always Apply These Standards When Generating Code**

1. **Zen of Python Compliance**: Ensure all generated code follows Zen principles:

   - **Readability first**: Code should be immediately understandable
   - **Explicit over implicit**: Clear intent, no hidden behavior or magic
   - **Simple solutions**: Choose the most straightforward approach that works
   - **Consistent patterns**: Use established Python idioms and conventions
   - **Proper error handling**: Never ignore exceptions, handle them explicitly
   - **Clear naming**: Use descriptive names that explain purpose and intent
   - **Flat structure**: Avoid deep nesting, prefer early returns and flat logic
   - **One obvious way**: Use well-known Python patterns over clever alternatives

1. **Pre-Generation Checklist:**

   - Use tuples `()` for `in` membership testing, never lists `[]`
   - Don't pass default values that match the function's default (e.g., `None` for optional parameters)
   - Add complete type annotations to ALL function parameters
   - Keep cognitive complexity under 15 per function
   - Implement ALL protocol properties when creating test classes

1. **Common Patterns to Always Follow:**

   ```python
   # Membership testing - ALWAYS use tuples
   if status in ("pending", "completed", "failed"):

   # Optional parameters - Don't pass None when it's the default
   value = kwargs.get("optional_param")  # Good
   value = kwargs.get("optional_param", None)  # Bad

   # Type annotations - ALWAYS complete
   def helper_method(self, task: TaskStatus, datetime_module) -> str:  # Good
   def helper_method(self, task) -> str:  # Bad - missing type

   # Protocol implementation - ALL properties required
   class TestOptions(OptionsProtocol):
       verbose = True
       resume_from: str | None = None  # Required
       progress_file: str | None = None  # Required
   ```

1. **Zen-Inspired Code Examples:**

   ```python
   # Beautiful is better than ugly - Clean, clear intent
   def process_user_data(user_id: str, data: dict[str, Any]) -> ProcessResult:
       if not user_id:
           raise ValueError("User ID is required")

       return ProcessResult(
           user_id=user_id,
           processed_data=_transform_data(data),
           timestamp=datetime.now(UTC),
       )


   # Explicit is better than implicit - Clear about what happens
   def send_notification(user: User, *, force_send: bool = False) -> bool:
       if not user.email:
           if force_send:
               raise ValueError("Cannot force send without email")
           return False

       return _email_service.send(user.email, template="welcome")


   # Simple is better than complex - Direct, understandable logic
   def validate_config(config: dict[str, Any]) -> None:
       required_keys = ("database_url", "api_key", "redis_url")

       for key in required_keys:
           if key not in config:
               raise ConfigError(f"Missing required config: {key}")


   # Flat is better than nested - Early returns, avoid deep nesting
   def process_request(request: Request) -> Response:
       if not request.user.is_authenticated:
           return Response.unauthorized()

       if not request.has_permission("read"):
           return Response.forbidden()

       if not request.data:
           return Response.bad_request("No data provided")

       # Main logic here, not nested 4 levels deep
       result = _process_data(request.data)
       return Response.success(result)
   ```

1. **Quality Gate Strategy:**

   - Write code that would pass `python -m crackerjack --comprehensive` on first try
   - Prioritize these checks: Refurb FURB109, FURB120, Pyright reportMissingParameterType, Complexipy \<20
   - When refactoring complex code, break into 3-5 helper methods with single responsibilities
   - **Apply Zen principles**: Every function should be easily explainable in plain English

1. **Testing Integration:**

   - All generated test classes MUST implement complete protocols
   - Use proper type annotations in test helper classes
   - Follow the same standards in test code as production code

By following these AI-specific guidelines, code generation will consistently pass all pre-commit hooks without manual intervention.

## Self-Maintenance Protocol for AI Assistants

**IMPORTANT: AI assistants should proactively maintain and update these quality standards to stay current with evolving tools.**

### Weekly Standards Update Process

**When to Update (any of these triggers):**

- Weekly basis (if working on the project regularly)
- After pre-commit hook failures reveal new rule violations
- When tools are updated (`pre-commit autoupdate` runs)
- When new error patterns emerge from quality checks

**Update Process:**

1. **Analyze Recent Quality Failures:**

   ```bash
   # Run comprehensive analysis to identify current issues
   python -m crackerjack --comprehensive --ai-agent

   # Check for new Refurb rules
   uv run python -c "import refurb; print('Refurb available')" 2>/dev/null || echo "Check refurb rules manually"

   # Review recent pre-commit failures
   git log --oneline -20 | grep -i "fix.*refurb\|fix.*pyright\|fix.*complex"
   ```

1. **Update CLAUDE.md Standards:**

   - Add any new FURB rules discovered (e.g., FURB150, FURB200, etc.)
   - Include new Pyright error codes (reportXxxType patterns)
   - Update complexity thresholds if Complexipy settings change
   - Add new Bandit security patterns as they emerge

1. **Update RULES.md:**

   - Sync any contradictory patterns between CLAUDE.md and RULES.md
   - Ensure RULES.md reflects the same quality standards
   - Add project-specific patterns that emerge from development

1. **Test Updated Standards:**

   ```bash
   # Verify updates don't conflict with existing code
   python -m crackerjack --comprehensive

   # Ensure documentation examples still work
   python -m crackerjack -t
   ```

### Self-Learning Pattern Recognition

**When encountering pre-commit failures, AI assistants should:**

1. **Pattern Analysis:**

   - Identify the specific tool (Refurb, Pyright, Complexipy, etc.)
   - Extract the error code (FURB109, reportMissingParameterType, etc.)
   - Note the violation pattern and correct pattern

1. **Documentation Update:**

   - Add the new pattern to the appropriate section in CLAUDE.md
   - Include both "bad" and "good" code examples
   - Mark as **CRITICAL** if it's a frequent failure pattern

1. **Validation:**

   - Test the fix resolves the issue
   - Ensure it doesn't conflict with existing standards
   - Update the "AI Code Generation Best Practices" checklist

### Example Update Entry Format

When adding new patterns, use this format:

````markdown
**Tool Update (Date): New Pattern Discovered**

- **ERROR_CODE**: Brief description
  ```python
  # Bad
  problematic_pattern()

  # Good
  correct_pattern()
````

- **Context**: When this typically occurs
- **Priority**: CRITICAL/HIGH/MEDIUM based on frequency

````

### Hook Version Monitoring

**AI assistants should track when these tools are updated:**
- Refurb: New FURB rules often added
- Pyright: New reportXxx error types
- Complexipy: Threshold or analysis changes
- Bandit: New security patterns

**Update Check Command:**
```bash
# Check current versions and available updates
pre-commit autoupdate --config .pre-commit-config.yaml
git diff .pre-commit-config.yaml  # Review what changed
````

By maintaining these standards proactively, AI assistants will stay ahead of quality issues and generate compliant code consistently.

## Recent Bug Fixes and Improvements

### CodeCleaner Docstring Removal Fix (December 2024)

#### Problem Description

The original `remove_docstrings` method in the `CodeCleaner` class had a critical bug where removing docstrings from functions or methods that contained only docstrings would result in syntactically invalid Python code. This caused the `-x` (clean) flag to fail with Ruff formatting errors.

**Example of problematic code:**

```python
def empty_function():
    """This function has only a docstring."""


class TestClass:
    """Class docstring."""

    def method_with_docstring_only(self):
        """Method with only docstring."""
```

**After broken docstring removal:**

```python
def empty_function():
    pass


class TestClass:
    pass

    def method_with_docstring_only(self):
        pass
```

This resulted in syntax errors: `expected an indented block after function definition`.

#### Root Cause Analysis

The issue occurred because the original algorithm:

1. Removed docstrings without checking if they were the only content in function/method bodies
1. Did not track function indentation levels
1. Failed to detect when `pass` statements were needed to maintain valid Python syntax
1. Had a bug in `_handle_docstring_end` that returned `True` instead of `False`

#### Solution Implementation

The fix involved a comprehensive rewrite of the docstring removal algorithm with these enhancements:

1. **Function Context Tracking**: Added `function_indent` and `removed_docstring` to track the context of function/class definitions
1. **Lookahead Logic**: Implemented `_needs_pass_statement()` helper method that analyzes remaining code to determine if a `pass` statement is needed
1. **Automatic Pass Insertion**: Added logic to insert properly indented `pass` statements when removing docstrings leaves empty function bodies
1. **Single vs Multi-line Handling**: Enhanced handling for both single-line and multi-line docstrings
1. **Bug Fixes**: Fixed the `_handle_docstring_end` method to return correct boolean values

#### Key Changes Made

**Enhanced State Management:**

```python
docstring_state = {
    "in_docstring": False,
    "delimiter": None,
    "waiting": False,
    "function_indent": 0,  # NEW: Track function indentation
    "removed_docstring": False,  # NEW: Track if we just removed a docstring
}
```

**New Helper Method:**

```python
def _needs_pass_statement(
    self, lines: list[str], start_index: int, function_indent: int
) -> bool:
    """Check if we need to add a pass statement after removing a docstring."""
    # Looks ahead to see if there are any statements at the correct indentation level
    # Returns True if no statements found (pass needed), False if statements exist
```

**Enhanced Docstring Removal Logic:**

- For single-line docstrings: Check immediately if pass statement needed
- For multi-line docstrings: Check after docstring end is reached
- Proper indentation calculation: `function_indent + 4` spaces for pass statements
- Context-aware pass insertion that respects Python indentation rules

#### Testing Enhancements

Added comprehensive tests to prevent regression:

1. **Enhanced Existing Test**: Added AST parsing validation to `test_code_cleaner_remove_docstrings`
1. **New Comprehensive Test**: Created `test_code_cleaner_remove_docstrings_empty_functions` that specifically tests:
   - Functions with only docstrings get `pass` statements
   - Functions with code after docstrings don't get unnecessary `pass` statements
   - Classes with only docstrings are handled correctly
   - All resulting code is syntactically valid Python

#### Test Cases Covered

```python
# Test cases that now pass:
def empty_function():
    """This function has only a docstring."""
    # Becomes: def empty_function():\n    pass


class TestClass:
    """Class docstring."""

    # Becomes: class TestClass:\n    (no pass needed for classes)

    def method_with_docstring_only(self):
        """Method with only docstring."""
        # Becomes: def method_with_docstring_only(self):\n        pass

    def method_with_code(self):
        """This method has code after docstring."""
        return True
        # Becomes: def method_with_code(self):\n        return True
```

#### Impact and Benefits

- **Immediate Fix**: The `-x` flag now works without causing syntax errors
- **Robust Solution**: Handles all edge cases including nested functions, mixed indentation, and various docstring styles
- **Maintains Functionality**: All existing docstring removal capabilities preserved
- **Future-Proof**: Enhanced test coverage prevents similar issues
- **Performance**: Minimal performance impact due to efficient lookahead algorithm

#### Backward Compatibility

This fix is fully backward compatible:

- All existing functionality is preserved
- No breaking changes to the API
- Existing tests continue to pass
- Only adds pass statements where syntactically required

#### Files Modified

- `crackerjack/crackerjack.py`: Enhanced `remove_docstrings` method and added `_needs_pass_statement` helper
- `tests/test_crackerjack.py`: Added syntax validation and comprehensive test cases

This fix ensures that the code cleaning functionality (`-x` flag) works reliably in all scenarios while maintaining the quality and functionality of the docstring removal feature.

### Enhanced Error Handling (December 2024)

#### Problem Description

The original code cleaner had basic error handling but would stop processing if any individual file encountered an error during cleaning. This could prevent the tool from cleaning other files in the project, particularly in cases involving:

- File permission issues
- Encoding problems (non-UTF-8 files)
- File system errors (file locks, disk space)
- Malformed Python code that causes parsing issues

#### Solution Implementation

Enhanced the `clean_file` method with comprehensive error handling that:

1. **Graceful Degradation**: Each cleaning step (remove comments, remove docstrings, remove whitespace, reformat) is wrapped in individual try-catch blocks
1. **Step-by-Step Recovery**: If one cleaning step fails, the cleaner falls back to the previous state and continues with remaining steps
1. **Detailed Error Reporting**: Uses the structured error handling system with specific error codes:
   - `PERMISSION_ERROR (6002)`: File permission issues
   - `FILE_WRITE_ERROR (6004)`: File system errors
   - `FILE_READ_ERROR (6003)`: Encoding or read errors
   - `UNEXPECTED_ERROR (9999)`: Unexpected errors with detailed context
1. **Non-Fatal Errors**: All errors are handled gracefully without stopping the overall cleaning process (`exit_on_error=False`)
1. **UTF-8 Encoding**: Explicit UTF-8 encoding for file operations to prevent encoding issues

#### Key Improvements

- **Resilient Processing**: The cleaner continues processing other files even if individual files fail
- **Clear Diagnostics**: Detailed error messages with recovery suggestions help users understand and fix issues
- **Fallback Mechanism**: Each cleaning step can fall back to the original code if specific operations fail
- **Step Isolation**: Failure in one cleaning step doesn't prevent other steps from running

#### Example Error Handling Flow

```python
try:
    code = self.remove_line_comments(code)
except Exception as e:
    self.console.print(f"[yellow]Warning: Failed to remove line comments: {e}[/yellow]")
    code = original_code  # Fallback to original

try:
    code = self.remove_docstrings(code)
except Exception as e:
    self.console.print(f"[yellow]Warning: Failed to remove docstrings: {e}[/yellow]")
    code = original_code  # Fallback to original
```

#### Benefits

- **Robustness**: Code cleaning continues even when encountering problematic files
- **Better User Experience**: Clear error messages with actionable recovery suggestions
- **Debugging Support**: Detailed error information helps identify and fix underlying issues
- **Compatibility**: Handles various file encoding and permission scenarios gracefully
- **Project-Wide Cleaning**: Ensures that cleaning doesn't stop due to individual file issues

#### Files Modified

- `crackerjack/crackerjack.py`: Enhanced `clean_file` method with comprehensive error handling

This enhancement ensures that the code cleaner (`-x` flag) can handle edge cases and problematic files while continuing to process the rest of the project successfully.

## Task Completion Requirements

**MANDATORY: Before marking any task as complete, AI assistants MUST:**

1. **Run crackerjack verification**: Execute `python -m crackerjack -t --ai-agent` to run all quality checks and tests with AI-optimized output
1. **Fix any issues found**: Address all formatting, linting, type checking, and test failures
1. **Re-run verification**: Ensure crackerjack passes completely (all hooks pass, all tests pass)
1. **Document verification**: Mention that crackerjack verification was completed successfully

**Why this is critical:**

- Ensures all code meets project quality standards
- Prevents broken code from being committed
- Maintains consistency with project development workflow
- Catches issues early before they become problems

**Never skip crackerjack verification** - it's the project's standard quality gate.

## Pre-commit Hook Maintenance

### Monthly Maintenance Tasks

1. **Update hook versions**: Run `pre-commit autoupdate` to get latest versions
1. **Review security advisories**: Check for vulnerabilities in hook dependencies
1. **Monitor performance**: Watch for hooks taking longer than expected
1. **Check deprecation warnings**: Address any warnings from tools like autotyping

### Performance Optimization

- **Autotyping monitoring**: Currently 7.3s runtime (highest cost hook)
- **Grouping strategy**: Consider grouping related hooks for better failure reporting
- **CI/CD integration**: Move expensive operations to pre-push hooks for CI/CD

### Security Maintenance

- **Regular vulnerability scanning**: Use `pre-commit autoupdate` with caution on untrusted hooks
- **Source verification**: Ensure all hooks come from trusted, actively maintained repositories
- **Dependency monitoring**: Watch for security issues in hook dependencies via Snyk or similar tools

### Quality Metrics to Monitor

- Test coverage should remain ≥90%
- Zero security vulnerabilities (Bandit)
- Zero type errors (Pyright)
- Zero dead code (Vulture)
- Zero unused dependencies (Creosote)
- Low complexity maintained (Complexipy)

### Hook Performance Optimization (Enhanced July 2025)

**🚀 Fast Development Mode (Default):**

- Uses `.pre-commit-config-fast.yaml` for regular commits
- Target execution time: \<5 seconds
- Includes: structure validation, formatting, basic security checks
- Command: `python -m crackerjack` (default behavior)

**🔍 Comprehensive Analysis Mode:**

- Uses `.pre-commit-config.yaml` for thorough analysis
- Target execution time: \<30 seconds
- Includes: all checks + type analysis, complexity, dead code detection
- Command: `python -m crackerjack --comprehensive`

**📦 Pre-push Hooks:**

- Expensive operations automatically moved to pre-push stage
- Runs comprehensive analysis before pushing changes
- Prevents performance bottlenecks during development
- Install: `pre-commit install --hook-type pre-push`

### Hook Configuration Status (Last Audit: July 2025)

✅ All hooks current and secure
✅ Performance optimized with dual-mode configuration
✅ Fast mode: \<5s execution time
✅ Comprehensive mode: \<30s execution time
✅ 90% test coverage achieved
✅ 0 security vulnerabilities found

## Development Memories

- Non-critical type errors are still errors that need to be fixed to pass crackerjack validation
- test directory files need to pass pyright tests as well in order for crackerjack to successfully complete

## AI Agent Integration

When running with `--ai-agent` flag, Crackerjack produces structured output optimized for AI assistants:

### Generated Files

- **`test-results.xml`**: JUnit XML format test results with detailed test outcomes
- **`coverage.json`**: JSON coverage report with line-by-line coverage data
- **`benchmark.json`**: Benchmark results in JSON format (when benchmarks are run)
- **`ai-agent-summary.json`**: Summary of the entire run with status and actions performed

### Example AI-Optimized Commands

```bash
# Run tests with structured output for AI analysis
python -m crackerjack --ai-agent -t

# Run full workflow with AI output
python -m crackerjack --ai-agent -a patch

# Run benchmarks with AI output
python -m crackerjack --ai-agent -t --benchmark
```

See README-AI-AGENT.md for detailed information about AI agent integration.

## Session Progress Tracking

Crackerjack includes robust session progress tracking that helps maintain continuity during long-running development sessions, especially when working with AI assistants that may experience interruptions.

### Key Features

- **Automatic Progress Logging**: Tracks each step of the crackerjack workflow with timestamps
- **Markdown Output**: Generates human-readable progress files with detailed status information
- **Session Recovery**: Resume interrupted sessions from where they left off
- **Task Status Tracking**: Monitors pending, in-progress, completed, failed, and skipped tasks
- **File Change Tracking**: Records which files were modified during each task
- **Error Recovery**: Provides detailed error information and recovery suggestions

### Usage Examples

```bash
# Enable session tracking with automatic detection and recovery
python -m crackerjack --track-progress -x -t -c

# Use custom progress file location
python -m crackerjack --track-progress --progress-file my-session.md -t

# Resume from a specific session file
python -m crackerjack --resume-from SESSION-PROGRESS-20240716-143052.md

# Combine with AI agent mode for structured output
python -m crackerjack --track-progress --ai-agent -a patch
```

### Automatic Session Detection

**🚀 New Feature**: Crackerjack now automatically detects interrupted sessions and offers to resume them!

When you use `--track-progress`, crackerjack will:

1. **Scan for incomplete sessions** in the current directory
1. **Analyze session status** to determine if resumption is possible
1. **Prompt for user confirmation** with session details
1. **Automatically resume** from the most recent incomplete session

Example workflow:

```bash
# First run - session gets interrupted
python -m crackerjack --track-progress -a patch
# ... session interrupted during testing phase ...

# Second run - automatic detection
python -m crackerjack --track-progress -a patch
# 📋 Found incomplete session: SESSION-PROGRESS-20240716-143052.md
#    Session ID: abc123def
#    Progress: 3/8 tasks completed
#    Failed tasks: Run tests
# ❓ Resume this session? [y/N]: y
# 🔄 Resumed session from: SESSION-PROGRESS-20240716-143052.md
```

### Progress File Structure

Progress files are generated in markdown format with the following structure:

````markdown
# Crackerjack Session Progress: {session_id}

**Session ID**: abc123def
**Started**: 2024-07-16 14:30:52
**Status**: In Progress
**Progress**: 3/8 tasks completed

## Session Metadata
- **Working Directory**: /Users/dev/my-project
- **Python Version**: 3.13
- **Crackerjack Version**: 0.19.8
- **CLI Options**: Options(clean=True, test=True, commit=True, ...)

## Task Progress Overview
| Task | Status | Duration | Details |
|------|--------|----------|---------|
| Setup | ✅ completed | 0.15s | Project structure initialized |
| Clean | ⏳ in_progress | - | Removing docstrings and comments |
| Tests | ⏸️ pending | - | - |

## Detailed Task Log
### ✅ Setup - COMPLETED
- **Started**: 2024-07-16 14:30:52
- **Completed**: 2024-07-16 14:30:52
- **Duration**: 0.15s
- **Files Changed**: None
- **Details**: Project structure initialized

### ⏳ Clean - IN PROGRESS
- **Started**: 2024-07-16 14:30:53
- **Current Status**: Removing docstrings and comments

## Session Recovery Information
If this session was interrupted, you can resume from where you left off:

```bash
python -m crackerjack --resume-from SESSION-PROGRESS-20240716-143052.md
````

## Files Modified This Session

- src/main.py
- tests/test_main.py

## Next Steps

🔄 Currently working on:

- Clean project code

````

### Integration with AI Assistants

Session progress tracking is particularly valuable when working with AI assistants:

1. **Continuity**: If an AI session is interrupted, the assistant can read the progress file to understand what was completed
2. **Context**: Progress files provide detailed context about the current state of the project
3. **Recovery**: Clear instructions for resuming work from the exact point of interruption
4. **Transparency**: Detailed logs help both users and AI assistants understand what happened

### Best Practices

1. **Always use progress tracking for complex workflows**:
   ```bash
   python -m crackerjack --track-progress -a patch
   ```

2. **Let automatic detection handle resumption**:
   - Simply use `--track-progress` again after interruption
   - Crackerjack will automatically detect and offer to resume incomplete sessions
   - No need to manually specify `--resume-from` in most cases

3. **Combine with AI agent mode for maximum visibility**:
   ```bash
   python -m crackerjack --track-progress --ai-agent -x -t -c
   ```

4. **Keep progress files for debugging**:
   - Progress files help diagnose issues that occur during workflow execution
   - They provide valuable debugging information for support requests
   - Automatic detection only considers sessions from the last 24 hours

5. **Use custom progress file names for important sessions**:
   ```bash
   python -m crackerjack --track-progress --progress-file release-v1.0.md -p major
   ```

### Error Handling and Recovery

When tasks fail, progress files include:

- Detailed error messages
- Recovery suggestions
- Context about what was being attempted
- Information about which files were being modified

Example failed task entry:

```markdown
### ❌ Pre-commit Hooks - FAILED
- **Started**: 2024-07-16 14:35:22
- **Failed**: 2024-07-16 14:35:45
- **Error**: ruff check failed with exit code 1
- **Recovery Suggestions**: Check error details and retry the failed operation
```

### File Management

- Progress files are automatically named with timestamps: `SESSION-PROGRESS-YYYYMMDD-HHMMSS.md`
- Files are created in the current working directory by default
- Use `--progress-file` to specify custom locations or names
- Progress files are updated in real-time as tasks complete

### Integration with Other Features

Session progress tracking works seamlessly with:

- **AI Agent Mode**: Structured output files reference progress tracking
- **Interactive Mode**: Progress is displayed in the Rich UI
- **Benchmark Mode**: Performance metrics are included in progress files
- **Version Bumping**: Version changes are tracked in session history

## Test Execution Details

### Test Configuration (pytest.ini_options)

- **asyncio_mode**: "auto" - Automatic asyncio test detection and handling
- **testpaths**: ["tests", "crackerjack"] - Directories to search for tests
- **timeout**: 300 seconds default per test
- **timeout_method**: "thread" - Uses thread-based timeout mechanism
- **coverage**: Configured with --cov=crackerjack --cov-fail-under=42

### Special Test Markers

- **unit**: Unit tests
- **benchmark**: Benchmark tests (disables parallel execution)
- **integration**: Integration tests
- **no_leaks**: Detect asyncio task leaks, thread leaks, and event loop blocking

### Test Parallelization

Tests run in parallel by default using pytest-xdist. The number of workers is automatically determined based on:

- Project size (small/medium/large)
- Available CPU cores
- Benchmark mode (disables parallelization)
- User-specified `--test-workers` option

### Benchmark Testing

When running benchmarks:

- Parallel execution is automatically disabled
- pytest-benchmark plugin is configured with optimized settings
- Results can be compared against previous runs for regression detection
- Benchmark results are saved in JSON format when using `--ai-agent`

## Pre-commit Hook Configurations

### Fast Mode (.pre-commit-config-fast.yaml)

Optimized for development speed (\<5s):

- Basic structure validation
- UV lock file updates
- Security checks (detect-secrets)
- Quick formatting (codespell, ruff)
- Markdown formatting (mdformat with ruff integration)

### Comprehensive Mode (.pre-commit-config.yaml)

Full analysis suite (\<30s):

- All fast mode checks
- Type checking (pyright)
- Code modernization (refurb)
- Security scanning (bandit)
- Dead code detection (vulture)
- Unused dependency detection (creosote)
- Code complexity analysis (complexipy)
- Automatic type annotation (autotyping)

### Pre-push Hooks

For expensive operations that should run before pushing:

- Install with: `pre-commit install --hook-type pre-push`
- Runs comprehensive analysis automatically
- Prevents pushing code that doesn't meet quality standards
````
