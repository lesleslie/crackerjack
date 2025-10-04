______________________________________________________________________

## id: 01K6K1AYRBPF8CGY95H0RMV9C4

# Crackerjack: AI-Powered Python Development Platform

## Project Overview

Crackerjack is a sophisticated, AI-driven platform designed to enhance Python development by enforcing high code quality standards through intelligent automation. It streamlines the development process by integrating a comprehensive suite of tools for linting, formatting, testing, and security analysis into a single, powerful command-line interface.

The core philosophy of Crackerjack is to proactively prevent issues rather than reactively fixing them. It employs a multi-agent AI system to automatically identify and resolve code quality problems, including type errors, security vulnerabilities, performance bottlenecks, and style inconsistencies. This allows developers to focus on writing high-quality code, confident that Crackerjack will handle the rest.

**Key Technologies:**

- **Python 3.13+:** The project is built on the latest version of Python, leveraging modern language features.
- **`uv`:** Used for high-performance package management and virtual environment creation.
- **`typer`:** Powers the command-line interface, providing a user-friendly experience with a rich set of options.
- **`ruff`:** A fast Python linter and code formatter that ensures consistent code style.
- **`pytest`:** The testing framework used to run the project's extensive test suite.
- **`pyright` and `zuban`:** Used for static type checking, with the custom Rust-based `zuban` providing significant performance improvements.
- **`bandit`:** A tool for finding common security issues in Python code.
- **AI Agents:** A team of specialized AI agents, coordinated by an `EnhancedAgentCoordinator`, that can automatically fix a wide range of code quality issues.
- **MCP (Model Context Protocol):** A WebSocket-based protocol that allows AI agents to interact with the Crackerjack CLI.

**Architecture:**

The project follows a modular architecture, with a clear separation of concerns between the CLI, core workflow orchestration, and various services.

- **`crackerjack/__main__.py`:** The main entry point for the CLI, which uses `typer` to define the available commands and options.
- **`crackerjack/cli/handlers.py`:** Contains the logic for handling the different CLI commands, delegating the actual work to the appropriate services and managers.
- **`crackerjack/core/workflow_orchestrator.py`:** The heart of the application, which defines the `WorkflowOrchestrator` and `WorkflowPipeline` classes that manage the execution of the code quality workflow.
- **`crackerjack/services/`:** A collection of services that provide specific functionality, such as Git integration, documentation generation, and AI-powered code analysis.
- **`crackerjack/agents/`:** Contains the implementation of the specialized AI agents that are responsible for fixing code quality issues.
- **`crackerjack/mcp/`:** Implements the Model Context Protocol server, which enables communication between the Crackerjack CLI and external AI agents.

## Building and Running

**Installation:**

1. Install `uv` (if not already installed):
   ```bash
   # Recommended: Official installer script
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Alternative: Using pipx
   pipx install uv
   ```
1. Install Crackerjack and its dependencies:
   ```bash
   uv sync --group dev
   ```

**Running the Main Workflow:**

The primary way to use Crackerjack is through its command-line interface. The main command is `python -m crackerjack`.

- **Run all quality checks:**
  ```bash
  python -m crackerjack
  ```
- **Run quality checks and tests:**
  ```bash
  python -m crackerjack --run-tests
  ```
- **Enable AI-powered auto-fixing:**
  ```bash
  python -m crackerjack --ai-fix
  ```
- **Run the full release workflow (including version bumping and publishing):**
  ```bash
  python -m crackerjack --all patch
  ```

**Starting the MCP Server:**

To enable AI agent integration, you can start the MCP server:

```bash
python -m crackerjack --start-mcp-server
```

This will start a WebSocket server on `localhost:8675`, allowing AI agents to connect and interact with the Crackerjack CLI.

## Development Conventions

- **Code Style:** The project uses `ruff` to enforce a consistent code style. All code should be formatted according to the rules defined in `pyproject.toml`.
- **Testing:** The project has an extensive test suite that is run using `pytest`. The "coverage ratchet" system ensures that test coverage can only increase over time, with a goal of 100% coverage.
- **Type Hinting:** The project uses modern Python type hints (e.g., `|` for unions) and enforces strict type checking with `pyright` and `zuban`.
- **Self-Documenting Code:** The project favors self-documenting code over extensive docstrings.
- **Commit Messages:** The project uses a standardized format for commit messages, which are automatically generated based on the changes made.
- **Pre-commit Hooks:** The project uses a comprehensive set of pre-commit hooks to ensure that all code is formatted, linted, and tested before it is committed.
