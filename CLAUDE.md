# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crackerjack is an opinionated Python project management tool that streamlines the development lifecycle by combining best-in-class tools into a unified workflow. It manages project setup, enforces code quality standards, runs tests, and assists with publishing Python packages.

## Key Commands

### Environment Setup

```bash
# Install PDM (required dependency manager)
pipx install pdm

# Install project dependencies
pdm install
```

### Running Crackerjack

```bash
# Run basic Crackerjack process (runs pre-commit hooks)
python -m crackerjack

# Clean code, run tests, and commit changes
python -m crackerjack -x -t -c

# Clean code, run tests, bump version (micro), and commit changes
python -m crackerjack -a micro

# Run specific pre-commit hooks interactively
python -m crackerjack -i
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
```

### Linting and Code Quality

```bash
# Run pre-commit hooks to check code quality
pre-commit run --all-files

# Update pre-commit hooks to the latest versions
python -m crackerjack -u

# Clean code by removing docstrings, comments, and extra whitespace
python -m crackerjack -x
```

### Publishing

```bash
# Bump version (micro/minor/major) and publish to PyPI
python -m crackerjack -p micro
python -m crackerjack -p minor
python -m crackerjack -p major

# Bump version without publishing
python -m crackerjack -b micro
python -m crackerjack -b minor
python -m crackerjack -b major
```

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
   - Handles code cleaning
   - Executes tests
   - Manages version bumping and publishing
   - Handles Git operations

2. **CodeCleaner**: Responsible for cleaning code
   - Removes docstrings
   - Removes line comments
   - Removes extra whitespace
   - Reformats code using Ruff

3. **ConfigManager**: Handles configuration file management
   - Updates pyproject.toml settings
   - Manages configuration files (.gitignore, .pre-commit-config.yaml)

4. **ProjectManager**: Manages project-level operations
   - Runs pre-commit hooks
   - Updates package configurations
   - Runs interactive hooks

### Key Design Patterns

- **Protocol-Based Design**: Uses `t.Protocol` for interface definitions
- **Factory Pattern**: Employs a factory function (`create_crackerjack_runner`) for dependency injection
- **Command Pattern**: CLI commands are mapped to specific operations

### Testing Infrastructure

Crackerjack has a robust testing setup with:

- **Test Configuration**: Customizes pytest through conftest.py
- **Benchmark Support**: Special handling for benchmark tests
- **Smart Parallelization**: Adjusts the number of workers based on project size
- **Project Size Detection**: Automatically detects project size to optimize test execution
- **Timeout Protection**: Tests have dynamic timeouts based on project size
- **Deadlock Prevention**: Advanced threading techniques to prevent deadlocks
- **Progress Tracking**: Shows periodic heartbeat messages for long-running tests

## Development Guidelines

1. **Code Style**: Follow the Crackerjack style guide:
   - Use static typing throughout
   - Use pathlib for file operations
   - Prefer Protocol over ABC
   - Use modern Python features (Python 3.13+)

2. **Testing Approach**:
   - Write unit tests for all functionality
   - Add benchmark tests for performance-critical code
   - Tests are run in parallel by default

3. **Dependencies**:
   - PDM for dependency management
   - Ruff for linting and formatting
   - Pytest for testing

4. **Version Management**:
   - Version bumping is handled through PDM
   - Follows semantic versioning
