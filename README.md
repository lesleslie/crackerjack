# Crackerjack: Elevate Your Python Development

[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)
[![Python: 3.13+](https://img.shields.io/badge/python-3.13%2B-green)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)
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

1. **Code Quality & Consistency**

   - **Challenge**: Maintaining consistent code quality across a project and team requires constant vigilance
   - **Solution**: Crackerjack enforces a unified style through integrated linting, formatting, and pre-commit hooks

1. **Streamlined Publishing**

   - **Challenge**: Publishing Python packages involves many manual, error-prone steps
   - **Solution**: Crackerjack automates the entire release process from testing to version bumping to publishing

Crackerjack integrates powerful tools like Ruff, UV, pre-commit, pytest, and more into a cohesive system that ensures code quality, consistency, and reliability. It's designed for developers who value both productivity and excellence.

______________________________________________________________________

## Getting Started

### Quick Start

If you're new to Crackerjack, follow these steps:

1. **Install Python 3.13:** Ensure you have Python 3.13 or higher installed.

1. **Install UV:**

   ```
   pipx install uv
   ```

1. **Install Crackerjack:**

   ```
   pip install crackerjack
   ```

1. **Initialize a New Project:**
   Navigate to your project's root directory and run:

   ```
   python -m crackerjack
   ```

   Or use the interactive Rich UI:

   ```
   python -m crackerjack -i
   ```

______________________________________________________________________

## The Crackerjack Philosophy

Crackerjack is built on the following core principles:

- **Code Clarity:** Code should be easy to read, understand, and maintain.
- **Automation:** Tedious tasks should be automated, allowing developers to focus on solving problems.
- **Consistency:** Code style, formatting, and project structure should be consistent across projects.
- **Reliability:** Tests are essential, and code should be checked rigorously.
- **Tool Integration:** Leverage powerful existing tools instead of reinventing the wheel.
- **Static Typing:** Static typing is essential for all development.

## Key Features

### Project Management

- **Effortless Project Setup:** Initializes new Python projects with a standard directory structure, `pyproject.toml`, and essential configuration files
- **UV Integration:** Manages dependencies and virtual environments using [UV](https://github.com/astral-sh/uv) for lightning-fast package operations
- **Dependency Management:** Automatically detects and manages project dependencies

### Code Quality

- **Automated Code Cleaning:** Removes unnecessary docstrings, line comments, and trailing whitespace
- **Consistent Code Formatting:** Enforces a unified style using [Ruff](https://github.com/astral-sh/ruff), the lightning-fast Python linter and formatter
- **Comprehensive Pre-commit Hooks:** Installs and manages a robust suite of pre-commit hooks (see the "Pre-commit Hooks" section below)
- **Interactive Checks:** Supports interactive pre-commit hooks (like `refurb`, `bandit`, and `pyright`) to fix issues in real-time
- **Static Type Checking:** Enforces type safety with Pyright integration

### Testing & Deployment

- **Built-in Testing:** Automatically runs tests using `pytest`
- **Easy Version Bumping:** Provides commands to bump the project version (patch, minor, or major)
- **Simplified Publishing:** Automates publishing to PyPI via UV

### Git Integration

- **Intelligent Commit Messages:** Analyzes git changes and suggests descriptive commit messages based on file types and modifications
- **Commit and Push:** Commits and pushes your changes with standardized commit messages
- **Pull Request Creation:** Creates pull requests to upstream repositories on GitHub or GitLab
- **Pre-commit Integration:** Ensures code quality before commits

### Developer Experience

- **Command-Line Interface:** Simple, intuitive CLI with comprehensive options
- **Interactive Rich UI:** Visual workflow with real-time task tracking, progress visualization, and interactive prompts
- **Structured Error Handling:** Clear error messages with error codes, detailed explanations, and recovery suggestions
- **Programmatic API:** Can be integrated into your own Python scripts and workflows
- **AI Agent Integration:** Structured output format for integration with AI assistants, with complete style rules available in [RULES.md](RULES.md) for AI tool customization
- **Celebratory Success Messages:** Trophy emoji (🏆) celebrates achieving crackerjack quality when all checks pass
- **Verbose Mode:** Detailed output for debugging and understanding what's happening
- **Python 3.13+ Features:** Leverages the latest Python language features including PEP 695 type parameter syntax, Self type annotations, and structural pattern matching

## Pre-commit Hooks & Performance Optimization

Crackerjack provides dual-mode pre-commit hook configuration optimized for different development scenarios:

### ⚡ Fast Development Mode (Default)

**Target Execution Time: \<5 seconds**

Uses `.pre-commit-config-fast.yaml` for regular development work:

- **Structure Validation**: Basic file structure checks
- **UV Lock Updates**: Keeps dependency lock files current
- **Security Checks**: Essential security scanning with detect-secrets
- **Quick Formatting**: Fast formatting with codespell and ruff
- **Markdown Formatting**: mdformat with ruff integration

```bash
# Default fast mode (automatically selected)
python -m crackerjack

# Explicitly use fast mode
python -m crackerjack --fast  # Uses fast pre-commit configuration
```

### 🔍 Comprehensive Analysis Mode

**Target Execution Time: \<30 seconds**

Uses `.pre-commit-config.yaml` for thorough analysis before releases or important commits:

- **All Fast Mode Checks**: Includes everything from fast mode
- **Type Checking**: Complete static analysis with Pyright
- **Code Modernization**: Advanced suggestions with Refurb
- **Security Scanning**: Comprehensive vulnerability detection with Bandit
- **Dead Code Detection**: Unused code identification with Vulture
- **Dependency Analysis**: Unused dependency detection with Creosote
- **Complexity Analysis**: Code complexity checking with Complexipy
- **Auto Type Hints**: Automatic type annotation with Autotyping

```bash
# Run comprehensive analysis
python -m crackerjack --comprehensive

# Use comprehensive mode for releases
python -m crackerjack --comprehensive -a patch
```

### 📦 Pre-push Hooks (CI/CD Integration)

For expensive operations that should run before pushing to remote repositories:

```bash
# Install pre-push hooks for comprehensive checks
pre-commit install --hook-type pre-push

# Manual pre-push validation
python -m crackerjack --comprehensive --test
```

### Performance Comparison

| Mode | Execution Time | Use Case | Hooks Count |
|------|---------------|----------|-------------|
| **Fast** | \<5s | Regular development | 8 essential hooks |
| **Comprehensive** | \<30s | Pre-release, important commits | 15+ thorough hooks |
| **Pre-push** | Variable | CI/CD, remote push | All hooks + extended analysis |

### Hook Categories

**Fast Mode Hooks:**

1. **uv-lock:** Ensures the `uv.lock` file is up to date
1. **Core pre-commit-hooks:** Essential hooks (trailing-whitespace, end-of-file-fixer)
1. **Ruff:** Fast linting and formatting
1. **Detect-secrets:** Security credential detection
1. **Codespell:** Spelling mistake correction
1. **mdformat:** Markdown formatting

**Additional Comprehensive Mode Hooks:**
7\. **Vulture:** Dead code detection
8\. **Creosote:** Unused dependency detection
9\. **Complexipy:** Code complexity analysis
10\. **Autotyping:** Automatic type hint generation
11\. **Refurb:** Code modernization suggestions
12\. **Bandit:** Security vulnerability scanning
13\. **Pyright:** Static type checking
14\. **Extended Ruff:** Additional formatting passes

### Smart Hook Selection

Crackerjack automatically selects the appropriate hook configuration based on:

- **Operation Type**: Fast for regular development, comprehensive for releases
- **User Preference**: Explicit `--fast` or `--comprehensive` flags
- **CI/CD Context**: Pre-push hooks for remote operations
- **Project Size**: Larger projects may benefit from fast mode during development

## The Crackerjack Style Guide

Crackerjack projects adhere to these guidelines:

- **Static Typing:** Use type hints consistently throughout your code.
- **Modern Type Hints:** Use the pipe operator (`|`) for union types (e.g., `Path | None` instead of `Optional[Path]`).
- **Explicit Naming:** Choose clear, descriptive names for classes, functions, variables, and other identifiers.
- **Markdown for Documentation:** Use Markdown (`.md`) for all documentation, READMEs, etc.
- **Pathlib:** Use `pathlib.Path` for handling file and directory paths instead of `os.path`.
- **Consistent Imports:** Use `import typing as t` for type hinting and prefix all typing references with `t.`.
- **Protocol-Based Design:** Use `t.Protocol` for interface definitions instead of abstract base classes.
- **Constants and Config:** Do not use all-caps for constants or configuration settings.
- **Path Parameters:** Functions that handle file operations should accept `pathlib.Path` objects as parameters.
- **Dependency Management:** Use UV for dependency management, package building, and publishing.
- **Testing:** Use pytest as your testing framework.
- **Python Version:** Crackerjack projects target Python 3.13+ and use the latest language features.
- **Clear Code:** Avoid overly complex code.
- **Modular:** Functions should do one thing well.

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

### Benchmark Testing & Performance Monitoring

Crackerjack includes comprehensive benchmark testing capabilities designed for continuous performance monitoring and regression detection:

#### 📊 Core Benchmark Features

- **Performance Measurement:** Accurately measure execution time, memory usage, and function calls
- **Regression Detection:** Automatic detection of performance degradation between code changes
- **Statistical Analysis:** Statistical validation of performance differences with confidence intervals
- **Historical Tracking:** Track performance trends across commits and releases
- **CI/CD Integration:** Seamless integration with continuous integration pipelines
- **AI Agent Output:** JSON format benchmark results for automated analysis

#### 🚀 Benchmark Execution Modes

**Basic Benchmarking:**

```bash
# Run tests with performance measurement
python -m crackerjack -t --benchmark

# Combine with AI agent mode for structured output
python -m crackerjack -t --benchmark --ai-agent
```

**Regression Testing:**

```bash
# Run benchmarks with regression detection (5% threshold)
python -m crackerjack -t --benchmark-regression

# Custom regression threshold (fail if >10% slower)
python -m crackerjack -t --benchmark-regression --benchmark-regression-threshold=10.0

# Strict regression testing for critical performance paths (2% threshold)
python -m crackerjack -t --benchmark-regression --benchmark-regression-threshold=2.0
```

#### 📈 Strategic Benchmark Scheduling

**🚀 Critical Scenarios (Always Run Benchmarks):**

- Before major releases
- After significant algorithmic changes
- When performance-critical code is modified

**📊 Regular Monitoring (Weekly):**

- Automated CI/CD pipeline execution
- Performance drift detection
- Long-term trend analysis

**🎲 Random Sampling (10% of commits):**

- Stochastic performance monitoring
- Gradual performance regression detection
- Statistical baseline maintenance

#### ⚙️ Technical Implementation

When benchmarks are executed, Crackerjack:

1. **Disables Parallel Execution**: Ensures accurate timing measurements (pytest-benchmark incompatible with pytest-xdist)
1. **Optimizes Configuration**: Configures pytest-benchmark with performance-optimized settings
1. **Baseline Comparison**: Compares results against previous runs for regression detection
1. **Statistical Validation**: Uses statistical methods to determine significant performance changes
1. **JSON Export**: Generates machine-readable results for automated analysis (with `--ai-agent`)

#### 🎯 Benchmark Best Practices

**Threshold Guidelines:**

- **2-5% threshold**: For release candidates and critical performance paths
- **5-10% threshold**: For regular development and monitoring
- **10%+ threshold**: For experimental features and early development

**Execution Strategy:**

```bash
# Development workflow with benchmarks
python -m crackerjack -t --benchmark --test-workers=1

# Release validation with strict thresholds
python -m crackerjack -t --benchmark-regression --benchmark-regression-threshold=2.0

# CI/CD integration with structured output
python -m crackerjack --ai-agent -t --benchmark-regression --benchmark-regression-threshold=5.0
```

#### 📁 Benchmark Output Files

When using `--ai-agent` mode, benchmark results are exported to:

- **`benchmark.json`**: Detailed performance metrics and statistical analysis
- **`test-results.xml`**: JUnit XML format with benchmark integration
- **`ai-agent-summary.json`**: Summary including benchmark status and regression analysis

This comprehensive approach ensures that performance regressions are caught early while maintaining development velocity.

## Installation

1. **Python:** Ensure you have Python 3.13 or higher installed.

1. **UV:** Install [UV](https://github.com/astral-sh/uv) using `pipx`:

   ```
   pipx install uv
   ```

1. **Crackerjack:** Install Crackerjack and initialize in your project root using:

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

```
python -m crackerjack
```

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
        self.commit = False  # Commit changes to Git
        self.interactive = True  # Run pre-commit hooks interactively
        self.verbose = True  # Enable verbose output

        # Configuration options
        self.no_config_updates = False  # Skip updating config files
        self.update_precommit = False  # Update pre-commit hooks

        # Process options
        self.clean = True  # Clean code (remove docstrings, comments, etc.)
        self.test = True  # Run tests using pytest
        self.skip_hooks = False  # Skip running pre-commit hooks

        # Test execution options
        self.test_workers = 2  # Number of parallel workers (0 = auto-detect, 1 = disable parallelization)
        self.test_timeout = 120  # Timeout in seconds for individual tests (0 = use default based on project size)

        # Benchmark options
        self.benchmark = False  # Run tests in benchmark mode
        self.benchmark_regression = (
            False  # Fail tests if benchmarks regress beyond threshold
        )
        self.benchmark_regression_threshold = (
            5.0  # Threshold percentage for benchmark regression
        )

        # Version and publishing options
        self.publish = None  # Publish to PyPI (patch, minor, major)
        self.bump = "patch"  # Bump version (patch, minor, major)
        self.all = None  # Run with -x -t -p <version> -c

        # Git options
        self.create_pr = False  # Create a pull request

        # Integration options
        self.ai_agent = False  # Enable AI agent structured output


# Create a Crackerjack runner with custom settings
runner = create_crackerjack_runner(
    console=Console(force_terminal=True),  # Rich console for pretty output
    pkg_path=Path.cwd(),  # Path to your project
    python_version="3.13",  # Target Python version
    dry_run=False,  # Set to True to simulate without changes
)

# Run Crackerjack with your options
runner.process(MyOptions())
```

## Intelligent Commit Messages

Crackerjack includes a smart commit message generation system that analyzes your git changes and suggests descriptive commit messages based on the files modified and the type of changes made.

### How It Works

When you use the `-c` (commit) flag, Crackerjack automatically:

1. **Analyzes Changes**: Scans `git diff` to understand what files were added, modified, deleted, or renamed
1. **Categorizes Files**: Groups changes by type (documentation, tests, core functionality, configuration, dependencies)
1. **Suggests Message**: Generates a descriptive commit message with appropriate action verbs and categorization
1. **Interactive Choice**: Offers options to use the suggestion, edit it, or write a custom message

### Message Format

Generated commit messages follow this structure:

```
[Action] [primary changes] and [secondary changes]

- Added N file(s)
  * path/to/new/file.py
  * path/to/another/file.py
- Modified N file(s)
  * path/to/changed/file.py
- Deleted N file(s)
- Renamed N file(s)
```

### Examples

**Documentation Updates:**

```
Update documentation

- Modified 3 file(s)
  * README.md
  * CLAUDE.md
  * docs/guide.md
```

**New Feature Addition:**

```
Add core functionality and tests

- Added 2 file(s)
  * src/new_feature.py
  * tests/test_feature.py
- Modified 1 file(s)
  * README.md
```

**Configuration Changes:**

```
Update configuration

- Modified 2 file(s)
  * pyproject.toml
  * .pre-commit-config.yaml
```

### Usage Options

When committing, you'll see:

```bash
🔍 Analyzing changes...

 README.md | 10 ++++
 tests/test_new.py | 50 ++++
 2 files changed, 60 insertions(+)

📋 Suggested commit message:
Update documentation and tests

- Modified 1 file(s)
  * README.md
- Added 1 file(s)
  * tests/test_new.py

Use suggested message? [Y/n/e to edit]:
```

**Options:**

- **Y** or **Enter**: Use the suggested message as-is
- **n**: Enter a completely custom commit message
- **e**: Edit the suggested message in your default editor (`$EDITOR`)

### Smart Categorization

The system intelligently categorizes files:

- **Documentation**: `README.md`, `CLAUDE.md`, `docs/`, `.md` files
- **Tests**: `test_`, `tests/`, `conftest.py`
- **Configuration**: `pyproject.toml`, `.yaml`, `.yml`, `.json`, `.gitignore`
- **CI/CD**: `.github/`, `ci/`, `.pre-commit`
- **Dependencies**: `requirements`, `pyproject.toml`, `uv.lock`
- **Core**: All other Python files and application code

This intelligent commit message system helps maintain consistent, descriptive commit history while saving time during development workflows.

### Command-Line Options

#### Core Workflow Options

- `-c`, `--commit`: Commit changes to Git
- `-i`, `--interactive`: Launch the interactive Rich UI with visual progress tracking
- `-v`, `--verbose`: Enable detailed verbose output for debugging
- `-a`, `--all <patch|minor|major>`: Run complete workflow: clean, test, publish, commit

#### Configuration & Setup

- `-n`, `--no-config-updates`: Skip updating configuration files (e.g., `pyproject.toml`)
- `-u`, `--update-precommit`: Update pre-commit hooks to the latest versions
- `--update-docs`: Create CLAUDE.md and RULES.md templates (only if they don't exist)
- `--force-update-docs`: Force update CLAUDE.md and RULES.md even if they exist

#### Code Quality & Testing

- `-x`, `--clean`: Clean code by removing docstrings, line comments, and extra whitespace
- `-t`, `--test`: Run tests using pytest with intelligent parallelization
- `-s`, `--skip-hooks`: Skip running pre-commit hooks (useful with `-t`)
- `--comprehensive`: Use comprehensive pre-commit analysis mode (\<30s, thorough)

#### Test Execution Control

- `--test-workers <N>`: Set parallel workers (0=auto-detect, 1=disable, N=specific count)
- `--test-timeout <seconds>`: Set timeout per test (0=auto-detect based on project size)

#### Performance & Benchmarking

- `--benchmark`: Run tests in benchmark mode (disables parallel execution)
- `--benchmark-regression`: Fail tests if benchmarks regress beyond threshold
- `--benchmark-regression-threshold <percentage>`: Set regression threshold (default: 5.0%)

#### Version Management & Publishing

- `-p`, `--publish <patch|minor|major>`: Bump version and publish to PyPI with enhanced authentication
- `-b`, `--bump <patch|minor|major>`: Bump version without publishing

#### Git Integration

- `-r`, `--pr`: Create a pull request to the upstream repository

#### Session Management

- `--track-progress`: Enable session progress tracking with automatic recovery
- `--progress-file <path>`: Custom path for progress file (default: SESSION-PROGRESS-{timestamp}.md)
- `--resume-from <file>`: Resume session from existing progress file

#### AI & Integration

- `--ai-agent`: Enable AI agent mode with structured JSON output
- `--help`: Display comprehensive help information

#### Example Flag Combinations

```bash
# Complete development workflow with session tracking
python -m crackerjack --track-progress -a patch

# Fast development cycle
python -m crackerjack -x -t -c

# Comprehensive pre-release validation
python -m crackerjack --comprehensive --benchmark-regression -p minor

# AI-optimized workflow with progress tracking
python -m crackerjack --ai-agent --track-progress -t --benchmark

# Interactive mode with comprehensive analysis
python -m crackerjack -i --comprehensive
```

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

#### Version Management & PyPI Publishing

Crackerjack provides comprehensive PyPI publishing with enhanced authentication and validation.

**🔐 PyPI Authentication Setup**

Crackerjack automatically validates your authentication setup before publishing and provides helpful error messages. Choose one of these authentication methods:

**Method 1: Environment Variable (Recommended)**

```bash
# Set PyPI token as environment variable
export UV_PUBLISH_TOKEN=pypi-your-token-here

# Publish with automatic token authentication
python -m crackerjack -p patch
```

**Method 2: Keyring Integration**

```bash
# Install keyring globally or in current environment
uv tool install keyring

# Store PyPI token in keyring (you'll be prompted for the token)
keyring set https://upload.pypi.org/legacy/ __token__

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

**Authentication Validation**

Crackerjack automatically validates your authentication setup before publishing:

- ✅ **Token Found**: When `UV_PUBLISH_TOKEN` is set
- ✅ **Keyring Ready**: When keyring is configured and token is stored
- ⚠️ **Setup Needed**: When authentication needs configuration

If publishing fails due to authentication issues, crackerjack displays helpful setup instructions.

**PyPI Token Best Practices**

1. **Generate Project-Specific Tokens**: Create separate PyPI tokens for each project
1. **Use Scoped Tokens**: Limit token scope to the specific package you're publishing
1. **Secure Storage**: Use environment variables or keyring - never hardcode tokens
1. **Token Format**: PyPI tokens start with `pypi-` (e.g., `pypi-AgEIcHlwaS5vcmcCJGZm...`)

**Troubleshooting Authentication**

If you encounter authentication issues:

1. **Check Token Format**: Ensure your token starts with `pypi-`
1. **Verify Environment Variable**: `echo $UV_PUBLISH_TOKEN` should show your token
1. **Test Keyring**: `keyring get https://upload.pypi.org/legacy/ __token__` should return your token
1. **Check Configuration**: Ensure `keyring-provider = "subprocess"` in pyproject.toml
1. **Install Keyring**: `uv tool install keyring` if using keyring authentication

**Version Management Commands**

- **Bump and Publish** - Bump version and publish to PyPI:

  ```bash
  python -m crackerjack -p patch  # For patch version
  python -m crackerjack -p minor  # For minor version
  python -m crackerjack -p major  # For major version
  ```

- **Version Bump Only** - Bump version without publishing:

  ```bash
  python -m crackerjack -b major
  ```

#### Documentation Template Management

Crackerjack can automatically propagate its quality standards to other Python projects by creating or updating their CLAUDE.md and RULES.md files. This ensures consistent AI code generation across all projects.

**📄 Template Propagation Commands**

```bash
# Update CLAUDE.md and RULES.md with latest quality standards (only if they don't exist)
python -m crackerjack --update-docs

# Force update CLAUDE.md and RULES.md even if they already exist
python -m crackerjack --force-update-docs
```

**When to Use Documentation Templates**

- **New Projects**: Use `--update-docs` to create initial documentation templates
- **Quality Standard Updates**: Use `--force-update-docs` weekly to keep standards current
- **AI Integration**: Ensures Claude Code generates compliant code on first pass across all projects
- **Team Synchronization**: Keeps all team projects using the same quality standards

**How Template Management Works**

- **Quality Standards**: Copies the latest Refurb, Pyright, Complexipy, and Bandit standards from Crackerjack
- **Project Customization**: Customizes project-specific sections (project name, overview)
- **Standard Preservation**: Preserves the core quality standards and AI generation guidelines
- **Git Integration**: Automatically adds files to git for easy committing

This feature is particularly valuable for teams maintaining multiple Python projects, ensuring that AI assistants generate consistent, high-quality code across all repositories.

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

## Session Progress Tracking

Crackerjack includes robust session progress tracking to maintain continuity during long-running development sessions and enable seamless collaboration with AI assistants.

### Key Features

- **Automatic Progress Logging:** Tracks each step of the crackerjack workflow with detailed timestamps and status information
- **Markdown Output:** Generates human-readable progress files with comprehensive task status and file change tracking
- **Session Recovery:** Automatically detects and resumes interrupted sessions from where they left off
- **Task Status Tracking:** Monitors pending, in-progress, completed, failed, and skipped tasks with detailed context
- **File Change Tracking:** Records which files were modified during each task for easy debugging and rollback
- **Error Recovery:** Provides detailed error information with recovery suggestions and continuation instructions
- **AI Assistant Integration:** Optimized for AI workflows with structured progress information and session continuity

### Usage Examples

**Enable automatic session tracking:**

```bash
# Basic session tracking with automatic detection
python -m crackerjack --track-progress -x -t -c

# Session tracking with custom progress file
python -m crackerjack --track-progress --progress-file my-session.md -a patch

# Resume from interrupted session (automatic detection)
python -m crackerjack --track-progress -a patch
# 📋 Found incomplete session: SESSION-PROGRESS-20240716-143052.md
# ❓ Resume this session? [y/N]: y

# Manual session resumption
python -m crackerjack --resume-from SESSION-PROGRESS-20240716-143052.md

# Combine with AI agent mode for maximum visibility
python -m crackerjack --track-progress --ai-agent -x -t -c
```

### Automatic Session Detection

**🚀 Smart Recovery:** Crackerjack automatically detects interrupted sessions and offers to resume them! When you use `--track-progress`, crackerjack will:

1. **Scan for incomplete sessions** in the current directory (last 24 hours)
1. **Analyze session status** to determine if resumption is possible
1. **Prompt for user confirmation** with detailed session information
1. **Automatically resume** from the most recent incomplete task

### Progress File Structure

Progress files are generated in markdown format with comprehensive information:

````markdown
# Crackerjack Session Progress: abc123def

**Session ID**: abc123def
**Started**: 2024-07-16 14:30:52
**Status**: In Progress
**Progress**: 3/8 tasks completed

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

## Files Modified This Session
- src/main.py
- tests/test_main.py

## Session Recovery Information
If this session was interrupted, you can resume from where you left off:
```bash
python -m crackerjack --resume-from SESSION-PROGRESS-20240716-143052.md
````

### Benefits for Development Workflows

- **Long-running Sessions:** Perfect for complex development workflows that may be interrupted
- **Team Collaboration:** Share session files with team members to show exactly what was done
- **Debugging Support:** Detailed logs help diagnose issues and understand workflow execution
- **AI Assistant Continuity:** AI assistants can read progress files to understand current project state
- **Audit Trail:** Complete record of all changes and operations performed during development

### Integration with Other Features

Session progress tracking works seamlessly with:

- **AI Agent Mode:** Structured output files reference progress tracking for enhanced AI workflows
- **Interactive Mode:** Progress is displayed in the Rich UI with real-time updates
- **Benchmark Mode:** Performance metrics are included in progress files for analysis
- **Version Bumping:** Version changes are tracked in session history for rollback support

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
1. Confirm each task before execution
1. Get detailed status information for running tasks
1. See a summary of completed, failed, and skipped tasks
1. Visualize error details with recovery suggestions

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

## Performance Optimization

Crackerjack is optimized for performance across different project sizes and development scenarios:

### ⚡ Development Speed Optimization

**Fast Mode Execution:**

- **Target Time**: \<5 seconds for most operations
- **Smart Hook Selection**: Essential hooks only during development
- **Parallel Processing**: Intelligent worker allocation based on system resources
- **Incremental Updates**: Only processes changed files when possible

**Adaptive Configuration:**

```bash
# Automatic optimization based on project size
python -m crackerjack  # Auto-detects and optimizes

# Force fast mode for development
python -m crackerjack --fast

# Override for large projects
python -m crackerjack --test-workers=2 --test-timeout=300
```

### 🔍 Quality vs Speed Balance

| Operation | Fast Mode (\<5s) | Comprehensive Mode (\<30s) | Use Case |
|-----------|----------------|---------------------------|----------|
| **Pre-commit** | Essential hooks | All hooks + analysis | Development vs Release |
| **Testing** | Parallel execution | Full suite + benchmarks | Quick check vs Validation |
| **Code Cleaning** | Basic formatting | Deep analysis + refactoring | Daily work vs Refactoring |

### 📊 Project Size Adaptation

**Small Projects (\<1000 lines):**

- Default: Maximum parallelization
- Fast hooks with minimal overhead
- Quick test execution

**Medium Projects (1000-10000 lines):**

- Balanced worker allocation
- Selective comprehensive checks
- Optimized timeout settings

**Large Projects (>10000 lines):**

- Conservative parallelization
- Extended timeouts
- Strategic hook selection
- Session progress tracking recommended

### 🚀 CI/CD Optimization

**Pre-push Hooks:**

```bash
# Install optimized pre-push hooks
pre-commit install --hook-type pre-push

# Comprehensive validation before push
python -m crackerjack --comprehensive --ai-agent -t
```

**Performance Monitoring:**

- Benchmark regression detection
- Statistical performance analysis
- Automated performance alerts
- Long-term trend tracking

This multi-layered optimization approach ensures that Crackerjack remains fast during development while providing thorough analysis when needed.

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
uv add --dev crackerjack
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

Crackerjack stands on the shoulders of giants. We're grateful to the maintainers and contributors of these outstanding tools that make modern Python development possible:

### Core Development Tools

- **[UV](https://docs.astral.sh/uv/)** - Next-generation Python package and project management
- **[Ruff](https://docs.astral.sh/ruff/)** - Lightning-fast Python linter and formatter written in Rust
- **[pyright](https://microsoft.github.io/pyright/)** - Fast, feature-rich static type checker for Python
- **[pytest](https://pytest.org/)** - Flexible and powerful testing framework

### Code Quality & Security

- **[pre-commit](https://pre-commit.com/)** - Multi-language pre-commit hooks framework
- **[bandit](https://bandit.readthedocs.io/)** - Security vulnerability scanner for Python
- **[vulture](https://github.com/jendrikseipp/vulture)** - Dead code detection tool
- **[refurb](https://github.com/dosisod/refurb)** - Code modernization and improvement suggestions
- **[codespell](https://github.com/codespell-project/codespell)** - Spelling mistake detection and correction
- **[detect-secrets](https://github.com/Yelp/detect-secrets)** - Prevention of secrets in repositories

### Dependencies & Project Management

- **[creosote](https://github.com/fredrikaverpil/creosote)** - Unused dependency detection
- **[autotyping](https://github.com/JelleZijlstra/autotyping)** - Automatic type hint generation
- **[complexipy](https://github.com/rohaquinlop/complexipy)** - Code complexity analysis

### CLI & User Interface

- **[Typer](https://typer.tiangolo.com/)** - Modern CLI framework for building command-line interfaces
- **[Rich](https://rich.readthedocs.io/)** - Rich text and beautiful formatting in the terminal
- **[click](https://click.palletsprojects.com/)** - Python package for creating command line interfaces

### Performance & Development Tools

- **[icecream](https://github.com/gruns/icecream)** - Sweet and creamy print debugging
- **[bevy](https://github.com/ZeroIntensity/bevy)** - Lightweight dependency injection framework
- **[msgspec](https://github.com/jcrist/msgspec)** - High-performance message serialization
- **[attrs](https://github.com/python-attrs/attrs)** - Classes without boilerplate

### Development Environment

- **[PyCharm](https://www.jetbrains.com/pycharm/)** - The premier Python IDE that powered the development of Crackerjack
- **[Claude Code](https://claude.ai/code)** - AI-powered development assistant that accelerated development and ensured code quality

### Legacy Inspiration

- **[PDM](https://pdm.fming.dev/)** - Original inspiration for modern Python dependency management patterns

### Special Recognition

We extend special thanks to the **Astral team** for their groundbreaking work on UV and Ruff, which have revolutionized Python tooling. Their commitment to performance, reliability, and developer experience has set new standards for the Python ecosystem.

The integration of these tools into Crackerjack's unified workflow demonstrates the power of the modern Python toolchain when thoughtfully combined. Each tool excels in its domain, and together they create a development experience that is both powerful and delightful.

We're honored to build upon this foundation and contribute to the Python community's continued evolution toward better development practices and tools.

______________________________________________________________________
