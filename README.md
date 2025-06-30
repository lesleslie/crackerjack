# Crackerjack: Elevate Your Python Development

[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)
[![Python: 3.13+](https://img.shields.io/badge/python-3.13%2B-green)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

**Crackerjack** (`ˈkra-kər-ˌjak`): *a person or thing of marked excellence.*

## What is Crackerjack?

Crackerjack is an opinionated Python project management tool that streamlines the entire development lifecycle. It combines best-in-class tools into a unified workflow, allowing you to focus on writing code rather than configuring tools.

### Why Choose Crackerjack?

Crackerjack solves three critical challenges in Python development:

1. **Project Setup & Configuration**
   - **Challenge**: Setting up Python projects with best practices requires knowledge of numerous tools and configurations
   - **Solution**: Crackerjack automates project initialization with pre-configured templates and industry best practices

2. **Code Quality & Consistency**
   - **Challenge**: Maintaining consistent code quality across a project and team requires constant vigilance
   - **Solution**: Crackerjack enforces a unified style through integrated linting, formatting, and pre-commit hooks

3. **Streamlined Publishing**
   - **Challenge**: Publishing Python packages involves many manual, error-prone steps
   - **Solution**: Crackerjack automates the entire release process from testing to version bumping to publishing

Crackerjack integrates powerful tools like Ruff, PDM, pre-commit, pytest, and more into a cohesive system that ensures code quality, consistency, and reliability. It's designed for developers who value both productivity and excellence.

---

## Getting Started

### Quick Start

If you're new to Crackerjack, follow these steps:
1. **Install Python 3.13:** Ensure you have Python 3.13 or higher installed.
2. **Install PDM:**
    ```
    pipx install pdm
    ```
3. **Install Crackerjack:**
    ```
    pip install crackerjack
    ```

4. **Initialize a New Project:**
    Navigate to your project's root directory and run:
    ```
    python -m crackerjack
    ```

    Or use the interactive Rich UI:
    ```
    python -m crackerjack -i
    ```

---

## The Crackerjack Philosophy

Crackerjack is built on the following core principles:

-   **Code Clarity:** Code should be easy to read, understand, and maintain.
-   **Automation:** Tedious tasks should be automated, allowing developers to focus on solving problems.
-   **Consistency:** Code style, formatting, and project structure should be consistent across projects.
-   **Reliability:** Tests are essential, and code should be checked rigorously.
-   **Tool Integration:** Leverage powerful existing tools instead of reinventing the wheel.
-   **Static Typing:** Static typing is essential for all development.

## Key Features

### Project Management
- **Effortless Project Setup:** Initializes new Python projects with a standard directory structure, `pyproject.toml`, and essential configuration files
- **PDM Integration:** Manages dependencies and virtual environments using [PDM](https://pdm.fming.dev/) with [uv](https://github.com/astral-sh/uv) for lightning-fast package operations
- **Dependency Management:** Automatically detects and manages project dependencies

### Code Quality
- **Automated Code Cleaning:** Removes unnecessary docstrings, line comments, and trailing whitespace
- **Consistent Code Formatting:** Enforces a unified style using [Ruff](https://github.com/astral-sh/ruff), the lightning-fast Python linter and formatter
- **Comprehensive Pre-commit Hooks:** Installs and manages a robust suite of pre-commit hooks (see the "Pre-commit Hooks" section below)
- **Interactive Checks:** Supports interactive pre-commit hooks (like `refurb`, `bandit`, and `pyright`) to fix issues in real-time
- **Static Type Checking:** Enforces type safety with Pyright integration

### Testing & Deployment
- **Built-in Testing:** Automatically runs tests using `pytest`
- **Easy Version Bumping:** Provides commands to bump the project version (micro, minor, or major)
- **Simplified Publishing:** Automates publishing to PyPI via PDM

### Git Integration
- **Commit and Push:** Commits and pushes your changes with standardized commit messages
- **Pull Request Creation:** Creates pull requests to upstream repositories on GitHub or GitLab
- **Pre-commit Integration:** Ensures code quality before commits

### Developer Experience
- **Command-Line Interface:** Simple, intuitive CLI with comprehensive options
- **Interactive Rich UI:** Visual workflow with real-time task tracking, progress visualization, and interactive prompts
- **Structured Error Handling:** Clear error messages with error codes, detailed explanations, and recovery suggestions
- **Programmatic API:** Can be integrated into your own Python scripts and workflows
- **AI Agent Integration:** Structured output format for integration with AI assistants, with complete style rules available in [RULES.md](RULES.md) for AI tool customization
- **Verbose Mode:** Detailed output for debugging and understanding what's happening
- **Python 3.13+ Features:** Leverages the latest Python language features including PEP 695 type parameter syntax, Self type annotations, and structural pattern matching

## Pre-commit Hooks

Crackerjack automatically installs and manages these pre-commit hooks:

1.  **pdm-lock-check:** Ensures the `pdm.lock` file is up to date.
2.  **Core pre-commit-hooks:** Essential hooks from [pre-commit-hooks](https://github.com/pre-commit/pre-commit-hooks) (e.g., `trailing-whitespace`, `end-of-file-fixer`).
3.  **Ruff:** [Ruff](https://github.com/astral-sh/ruff) for linting, code formatting, and general code style enforcement.
4.  **Vulture:** [Vulture](https://github.com/jendrikseipp/vulture) to identify dead code.
5.  **Creosote:** [Creosote](https://github.com/fredrikaverpil/creosote) to detect unused dependencies.
6.  **Complexipy:** [Complexipy](https://github.com/rohaquinlop/complexipy-pre-commit) for analyzing code complexity.
7.  **Codespell:** [Codespell](https://github.com/codespell-project/codespell) for correcting typos in the code.
8.  **Autotyping:** [Autotyping](https://github.com/JelleZijlstra/autotyping) for adding type hints.
9.  **Refurb:** [Refurb](https://github.com/dosisod/refurb) to suggest code improvements.
10. **Bandit:** [Bandit](https://github.com/PyCQA/bandit) to identify potential security vulnerabilities.
11. **Pyright:** [Pyright](https://github.com/RobertCraigie/pyright-python) for static type checking.
12. **Ruff (again):** A final Ruff pass to ensure all changes comply with the enforced style.

## The Crackerjack Style Guide

Crackerjack projects adhere to these guidelines:

-   **Static Typing:** Use type hints consistently throughout your code.
-   **Modern Type Hints:** Use the pipe operator (`|`) for union types (e.g., `Path | None` instead of `Optional[Path]`).
-   **Explicit Naming:** Choose clear, descriptive names for classes, functions, variables, and other identifiers.
-   **Markdown for Documentation:** Use Markdown (`.md`) for all documentation, READMEs, etc.
-   **Pathlib:** Use `pathlib.Path` for handling file and directory paths instead of `os.path`.
-   **Consistent Imports:** Use `import typing as t` for type hinting and prefix all typing references with `t.`.
-   **Protocol-Based Design:** Use `t.Protocol` for interface definitions instead of abstract base classes.
-   **Constants and Config:** Do not use all-caps for constants or configuration settings.
-   **Path Parameters:** Functions that handle file operations should accept `pathlib.Path` objects as parameters.
-   **Dependency Management:** Use PDM for dependency management, package building, and publishing.
-   **Testing:** Use pytest as your testing framework.
-   **Python Version:** Crackerjack projects target Python 3.13+ and use the latest language features.
-   **Clear Code:** Avoid overly complex code.
-   **Modular:** Functions should do one thing well.

## Testing Features

Crackerjack provides advanced testing capabilities powered by pytest:

### Standard Testing

- **Parallel Test Execution:** Tests run in parallel by default using pytest-xdist for faster execution
- **Smart Parallelization:** Automatically adjusts the number of worker processes based on project size
- **Timeout Protection:** Tests have dynamic timeouts based on project size to prevent hanging tests
- **Coverage Reports:** Automatically generates test coverage reports with configurable thresholds

### Advanced Test Configuration

Crackerjack offers fine-grained control over test execution:

- **Worker Control:** Set the number of parallel workers with `--test-workers` (0 = auto-detect, 1 = disable parallelization)
- **Timeout Control:** Customize test timeouts with `--test-timeout` (in seconds)
- **Project Size Detection:** Automatically detects project size and adjusts timeout and parallelization settings
- **Deadlock Prevention:** Uses advanced threading techniques to prevent deadlocks in test output processing
- **Progress Tracking:** Shows periodic heartbeat messages for long-running tests

Example test execution options:
```bash
# Run tests with a single worker (no parallelization)
python -m crackerjack -t --test-workers=1

# Run tests with a specific number of workers (e.g., 4)
python -m crackerjack -t --test-workers=4

# Run tests with a custom timeout (5 minutes per test)
python -m crackerjack -t --test-timeout=300

# Combine options for maximum control
python -m crackerjack -t --test-workers=2 --test-timeout=600
```

### Benchmark Testing

Crackerjack includes benchmark testing capabilities:

- **Performance Measurement:** Run tests with `--benchmark` to measure execution time and performance
- **Regression Testing:** Use `--benchmark-regression` to detect performance regressions
- **Configurable Thresholds:** Set custom regression thresholds with `--benchmark-regression-threshold`
- **Compatibility Management:** Automatically disables parallel execution when running benchmarks
- **CI Integration:** Track performance across commits with benchmark history

When benchmarks are run, Crackerjack:
1. Disables parallel test execution (as pytest-benchmark is incompatible with pytest-xdist)
2. Configures the pytest-benchmark plugin with optimized settings
3. Compares benchmark results against previous runs when regression testing is enabled
4. Fails tests if performance decreases beyond the specified threshold

Example benchmark usage:
```bash
# Run benchmarks
python -m crackerjack -t --benchmark

# Run benchmarks with regression testing (fail if >5% slower)
python -m crackerjack -t --benchmark-regression

# Run benchmarks with custom regression threshold (10%)
python -m crackerjack -t --benchmark-regression --benchmark-regression-threshold=10.0
```

## Installation

1.  **Python:** Ensure you have Python 3.13 or higher installed.
2.  **PDM:** Install [PDM](https://pdm.fming.dev/) using `pipx`:

    ```
    pipx install pdm
    ```

3.  **Crackerjack:** Install Crackerjack and initialize in your project root using:
    ```
    pip install crackerjack
    cd your_project_root
    python -m crackerjack
    ```

    Or with the interactive Rich UI:
    ```
    python -m crackerjack -i
    ```

## Usage

### Command Line

Run Crackerjack from the root of your Python project using:

    python -m crackerjack

### Programmatic API

You can also use Crackerjack programmatically in your Python code:

```python
import typing as t
from pathlib import Path
from rich.console import Console
from crackerjack import create_crackerjack_runner

# Create a custom options object
class MyOptions:
    def __init__(self):
        # Core options
        self.commit = False          # Commit changes to Git
        self.interactive = True      # Run pre-commit hooks interactively
        self.verbose = True          # Enable verbose output

        # Configuration options
        self.no_config_updates = False  # Skip updating config files
        self.update_precommit = False   # Update pre-commit hooks

        # Process options
        self.clean = True            # Clean code (remove docstrings, comments, etc.)
        self.test = True             # Run tests using pytest
        self.skip_hooks = False      # Skip running pre-commit hooks

        # Test execution options
        self.test_workers = 2        # Number of parallel workers (0 = auto-detect, 1 = disable parallelization)
        self.test_timeout = 120      # Timeout in seconds for individual tests (0 = use default based on project size)

        # Benchmark options
        self.benchmark = False       # Run tests in benchmark mode
        self.benchmark_regression = False  # Fail tests if benchmarks regress beyond threshold
        self.benchmark_regression_threshold = 5.0  # Threshold percentage for benchmark regression

        # Version and publishing options
        self.publish = None          # Publish to PyPI (micro, minor, major)
        self.bump = "micro"          # Bump version (micro, minor, major)
        self.all = None              # Run with -x -t -p <version> -c

        # Git options
        self.create_pr = False       # Create a pull request

        # Integration options
        self.ai_agent = False        # Enable AI agent structured output

# Create a Crackerjack runner with custom settings
runner = create_crackerjack_runner(
    console=Console(force_terminal=True),  # Rich console for pretty output
    pkg_path=Path.cwd(),                   # Path to your project
    python_version="3.13",                 # Target Python version
    dry_run=False                          # Set to True to simulate without changes
)

# Run Crackerjack with your options
runner.process(MyOptions())
```


### Command-Line Options

-   `-c`, `--commit`: Commit changes to Git.
-   `-i`, `--interactive`: Run pre-commit hooks interactively when possible.
-   `-n`, `--no-config-updates`: Skip updating configuration files (e.g., `pyproject.toml`).
-   `-u`, `--update-precommit`: Update pre-commit hooks to the latest versions.
-   `-v`, `--verbose`: Enable verbose output.
-   `-p`, `--publish <micro|minor|major>`: Bump the project version and publish to PyPI using PDM.
-   `-b`, `--bump <micro|minor|major>`: Bump the project version without publishing.
-   `-r`, `--pr`: Create a pull request to the upstream repository.
-   `-s`, `--skip-hooks`: Skip running pre-commit hooks (useful with `-t`).
-   `-x`, `--clean`: Clean code by removing docstrings, line comments, and extra whitespace.
-   `-t`, `--test`: Run tests using `pytest`.
-   `--test-workers`: Set the number of parallel workers for testing (0 = auto-detect, 1 = disable parallelization).
-   `--test-timeout`: Set the timeout in seconds for individual tests (0 = use default based on project size).
-   `--benchmark`: Run tests in benchmark mode (disables parallel execution).
-   `--benchmark-regression`: Fail tests if benchmarks regress beyond threshold.
-   `--benchmark-regression-threshold`: Set threshold percentage for benchmark regression (default 5.0%).
-   `-a`, `--all`: Run with `-x -t -p <micro|minor|major> -c` development options.
-   `-i`, `--interactive`: Enable the interactive Rich UI for a more user-friendly experience with visual progress tracking and interactive prompts.
-   `--ai-agent`: Enable AI agent mode with structured output (see [AI Agent Integration](#ai-agent-integration)).
-   `--help`: Display help.

### Example Workflows

#### Development Workflows

- **Quick Check** - Run basic checks on your code:
  ```bash
  python -m crackerjack
  ```

- **Full Development Cycle** - Clean, test, bump version, publish, and commit:
  ```bash
  python -m crackerjack -a minor  # All-in-one command

  # Equivalent to:
  python -m crackerjack -x -t -p minor -c
  ```

- **Development with Tests** - Clean code, run checks, run tests, then commit:
  ```bash
  python -m crackerjack -c -x -t
  ```

- **Fast Testing** - Run tests without running pre-commit hooks:
  ```bash
  python -m crackerjack -t -s
  ```

#### Test Execution Options

- **Single-Process Testing** - Run tests sequentially (no parallelization):
  ```bash
  python -m crackerjack -t --test-workers=1
  ```

- **Customized Parallel Testing** - Run tests with a specific number of workers:
  ```bash
  python -m crackerjack -t --test-workers=4
  ```

- **Long-Running Tests** - Increase test timeout for complex tests:
  ```bash
  python -m crackerjack -t --test-timeout=600
  ```

- **Optimized for Large Projects** - Reduce workers and increase timeout for large codebases:
  ```bash
  python -m crackerjack -t --test-workers=2 --test-timeout=300
  ```

#### Version Management

- **Bump and Publish** - Bump version and publish to PyPI:
  ```bash
  python -m crackerjack -p micro  # For patch version
  python -m crackerjack -p minor  # For minor version
  python -m crackerjack -p major  # For major version
  ```

- **Version Bump Only** - Bump version without publishing:
  ```bash
  python -m crackerjack -b major
  ```

#### Configuration Management

- **Skip Config Updates** - Run checks without updating configuration files:
  ```bash
  python -m crackerjack -n
  ```

- **Update Hooks** - Update pre-commit hooks to latest versions:
  ```bash
  python -m crackerjack -u
  ```

#### Git Operations

- **Commit Changes** - Run checks and commit changes:
  ```bash
  python -m crackerjack -c
  ```

- **Create PR** - Create a pull request to the upstream repository:
  ```bash
  python -m crackerjack -r
  ```

#### Other Operations

- **Interactive Mode** - Run pre-commit hooks interactively:
  ```bash
  python -m crackerjack -i
  ```

- **Rich Interactive Mode** - Run with the interactive Rich UI:
  ```bash
  python -m crackerjack -i
  ```

- **AI Integration** - Run with structured output for AI tools:
  ```bash
  python -m crackerjack --ai-agent --test
  ```

- **Help** - Display command help:
  ```bash
  python -m crackerjack --help
  ```

## AI Agent Integration

Crackerjack includes special features for integration with AI agents like Claude, ChatGPT, and other LLM-based assistants:

- **Structured JSON Output:** When run with `--ai-agent`, Crackerjack outputs results in JSON format that's easy for AI agents to parse
- **Clear Status Indicators:** Provides clear status indicators (running, success, failed, complete) to track progress
- **Action Tracking:** Includes a list of actions performed to help AI agents understand what happened

### Example AI Agent Usage

```bash
python -m crackerjack --ai-agent --test
```

For detailed information about using Crackerjack with AI agents, including the structured output format and programmatic usage, see [README-AI-AGENT.md](README-AI-AGENT.md).

## Interactive Rich UI

Crackerjack now offers an enhanced interactive experience through its Rich UI:

- **Visual Workflow:** See a visual representation of the entire task workflow with dependencies
- **Real-time Progress:** Track task progress with interactive progress bars and status indicators
- **Task Management:** Confirm tasks before execution and view detailed status information
- **Error Visualization:** Errors are presented in a structured, easy-to-understand format with recovery suggestions
- **File Selection:** Interactive file browser for operations that require selecting files

To use the Rich UI, run Crackerjack with the `-i` flag:

```bash
python -m crackerjack -i
```

This launches an interactive terminal interface where you can:
1. View all available tasks and their dependencies
2. Confirm each task before execution
3. Get detailed status information for running tasks
4. See a summary of completed, failed, and skipped tasks
5. Visualize error details with recovery suggestions

## Structured Error Handling

Crackerjack implements a comprehensive error handling system that provides:

- **Error Categories:** Errors are categorized by type (configuration, execution, testing, etc.)
- **Error Codes:** Each error has a unique numeric code for easy reference
- **Detailed Messages:** Clear, descriptive messages explain what went wrong
- **Recovery Suggestions:** Where possible, errors include recovery suggestions to help resolve issues
- **Rich Formatting:** Errors are presented with clear visual formatting (when using Rich UI or verbose mode)

Error types include:
- Configuration errors (1000-1999)
- Execution errors (2000-2999)
- Test errors (3000-3999)
- Publishing errors (4000-4999)
- Git errors (5000-5999)
- File operation errors (6000-6999)
- Code cleaning errors (7000-7999)
- Generic errors (9000-9999)

Use the `-v` or `--verbose` flag to see more detailed error information:

```bash
python -m crackerjack -v
```

For the most comprehensive error details with visual formatting, combine verbose mode with the Rich UI:

```bash
python -m crackerjack -i -v
```

## Python 3.13+ Features

Crackerjack is designed to leverage the latest Python 3.13+ language features:

- **Type Parameter Syntax (PEP 695):** Uses the new, more concise syntax for generic type parameters
- **Self Type:** Leverages the `Self` type for better method chaining and builder patterns
- **Structural Pattern Matching:** Uses pattern matching for cleaner code, especially in configuration and command processing
- **Enhanced Type Hints:** More precise type hints with union types using the pipe operator
- **Modern Dictionary Patterns:** Leverages structural pattern matching with dictionaries for cleaner data handling

These modern Python features contribute to:
- More readable and maintainable code
- Better static type checking with tools like pyright
- Cleaner, more concise implementations
- Enhanced error handling and pattern recognition

Crackerjack provides examples of these features in action, serving as a reference for modern Python development practices.

## Contributing

Crackerjack is an evolving project. Contributions are welcome! Please open a pull request or issue.

To contribute:

1. Add Crackerjack as a development dependency to your project:
  ```
  pdm add -G dev crackerjack
  ```

2. Run checks and tests before submitting:
  ```
  python -m crackerjack -x -t
  ```

This ensures your code meets all quality standards before submission.

## License

This project is licensed under the terms of the BSD 3-Clause license.

## Architecture

Crackerjack is designed with modern Python principles in mind:

- **Factory Pattern:** Uses a factory function (`create_crackerjack_runner`) to create instances with proper dependency injection
- **Protocol-Based Design:** Defines clear interfaces using `t.Protocol` for better flexibility and testability
- **Dependency Injection:** Components can be easily replaced with custom implementations
- **Separation of Concerns:** CLI interface is separate from core logic
- **Type Safety:** Comprehensive type hints throughout the codebase
- **Testability:** Designed to be easily testable with mock objects

## Acknowledgments

-   **PDM:** For excellent dependency and virtual environment management.
-   **Ruff:** For lightning-fast linting and code formatting.
-   **pre-commit:** For the robust hook management system.
-   **pytest:** For the flexible and powerful testing framework.
-   **uv:** For greatly improving PDM speeds.
-   **bandit:** For finding security vulnerabilities.
-   **vulture:** For dead code detection.
-   **creosote:** For unused dependency detection.
-   **complexipy:** For code complexity analysis.
-   **codespell:** For spelling correction.
-   **autotyping:** For automatically adding type hints.
-   **refurb:** For code improvement suggestions.
-   **pyright:** For static type checking.
-   **Typer:** For the creation of the CLI.

---
