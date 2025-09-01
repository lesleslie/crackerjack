# Crackerjack: Proactive AI-Powered Python Project Management

[![Python: 3.13+](https://img.shields.io/badge/python-3.13%2B-green)](https://www.python.org/downloads/)
[![pytest](https://img.shields.io/badge/pytest-coverage%20ratchet-blue)](https://pytest.org)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

## 🎯 Mission Statement

**Crackerjack** transforms Python development from reactive firefighting to proactive excellence. We believe every line of code should be deliberate, every bug should be prevented rather than fixed, and every developer should write flawless code from the start.

### What is "Crackerjack"?

**crackerjack** (noun): *A person or thing of marked excellence or ability; first-rate; exceptional.*

Just as the name suggests, Crackerjack makes your Python projects first-rate through:

- **🧠 Proactive AI Architecture**: 10+ specialized AI agents prevent issues before they occur
- **⚡ Autonomous Quality**: Intelligent auto-fixing with architectural planning
- **🛡️ Zero-Compromise Standards**: 100% test coverage, complexity ≤15, security-first patterns
- **🔄 Learning System**: Gets smarter with every project, caching successful patterns
- **🌟 One Command Excellence**: From setup to PyPI publishing with a single command

**The Crackerjack Philosophy**: If your code needs fixing after it's written, you're doing it wrong. We prevent problems through intelligent architecture and proactive patterns, making exceptional code the natural outcome, not a lucky accident.

## What Problem Does Crackerjack Solve?

**Instead of configuring multiple tools separately:**

```bash
# Traditional workflow
pip install black isort flake8 mypy pytest pre-commit
# Configure each tool individually
# Set up pre-commit hooks manually
# Remember different commands for each tool
```

**Crackerjack provides unified commands:**

```bash
pip install crackerjack
python -m crackerjack        # Setup + quality checks
python -m crackerjack -t     # Add testing
python -m crackerjack -a patch  # Full release workflow
```

**Key differentiators:**

- **Single command** replaces 6+ separate tools
- **Pre-configured** with Python best practices
- **UV integration** for fast dependency management
- **Automated publishing** with PyPI authentication
- **MCP server** for AI agent integration

## The Crackerjack Philosophy

Crackerjack is built on the following core principles:

- **Code Clarity:** Code should be easy to read, understand, and maintain
- **Automation:** Tedious tasks should be automated, allowing developers to focus on solving problems
- **Consistency:** Code style, formatting, and project structure should be consistent across projects
- **Reliability:** Tests are essential, and code should be checked rigorously
- **Tool Integration:** Leverage powerful existing tools instead of reinventing the wheel
- **Static Typing:** Static typing is essential for all development

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [AI Auto-Fix Features](#ai-auto-fix-features)
- [Core Features](#core-features)
- [MCP Server Configuration](#mcp-server-configuration)
- [Pre-commit Hook Modes](#pre-commit-hook-modes)
- [Testing Features](#testing-features)
- [Command Reference](#command-reference)
- [Style Guide](#style-guide)
- [Publishing & Version Management](#publishing--version-management)
- [Developer Experience](#developer-experience)

## Installation

### Prerequisites

- Python 3.13+
- [UV](https://github.com/astral-sh/uv) package manager

### Install UV

```bash
pipx install uv
```

### Install Crackerjack

```bash
pip install crackerjack
# or
uv add crackerjack
```

## Quick Start

### Initialize a Project

```bash
# Navigate to your project directory
cd your-project

# Initialize with Crackerjack
python -m crackerjack

# Or use interactive mode
python -m crackerjack -i
```

## AI Auto-Fix Features

Crackerjack provides two distinct approaches to automatic error fixing:

### 1. Hook Auto-Fix Modes (Basic Formatting)

Limited tool-specific auto-fixes for simple formatting issues:

- `ruff --fix`: Import sorting, basic formatting
- `trailing-whitespace --fix`: Removes trailing whitespace
- `end-of-file-fixer --fix`: Ensures files end with newline

**Limitations:** Only handles simple style issues, cannot fix type errors, security issues, test failures, or complex code quality problems.

### 2. AI Agent Auto-Fixing (Comprehensive Intelligence)

**Revolutionary AI-powered code quality enforcement** that automatically fixes ALL types of issues:

#### How AI Agent Auto-Fixing Works

1. **🚀 Run All Checks**: Fast hooks, comprehensive hooks, full test suite
1. **🔍 Analyze Failures**: AI parses error messages, identifies root causes
1. **🤖 Intelligent Fixes**: AI reads source code and makes targeted modifications
1. **🔄 Repeat**: Continue until ALL checks pass (up to 10 iterations)
1. **🎉 Perfect Quality**: Zero manual intervention required

#### Comprehensive Coverage

The AI agent intelligently fixes:

- **Type Errors (pyright)**: Adds missing annotations, fixes type mismatches
- **Security Issues (bandit)**: Removes hardcoded paths, fixes vulnerabilities
- **Dead Code (vulture)**: Removes unused imports, variables, functions
- **Performance Issues**: Transforms inefficient patterns (list concatenation, string building, nested loops)
- **Documentation Issues**: Auto-generates changelogs, maintains consistency across .md files
- **Test Failures**: Fixes missing fixtures, import errors, assertions
- **Code Quality (refurb)**: Applies refactoring, reduces complexity
- **All Hook Failures**: Formatting, linting, style issues

#### AI Agent Commands

```bash
# Standard AI agent mode (recommended)
python -m crackerjack --ai-agent -t -v

# MCP server with WebSocket support (localhost:8675)
python -m crackerjack --start-mcp-server

# Progress monitoring via WebSocket
python -m crackerjack.mcp.progress_monitor <job_id> ws://localhost:8675
```

#### Key Benefits

- **Zero Configuration**: No complex flag combinations needed
- **Complete Automation**: Handles entire quality workflow automatically
- **Intelligent Analysis**: Understands code context and business logic
- **Comprehensive Coverage**: Fixes ALL error types, not just formatting
- **Perfect Results**: Achieves 100% code quality compliance

#### Security & Safety Features

- **Command Validation**: All AI modifications are validated for safety
- **No Shell Injection**: Uses secure subprocess execution
- **Rollback Support**: All changes can be reverted via git
- **Human Review**: Review AI-generated changes before commit

## Core Workflow

**Two-stage quality enforcement:**

1. **Fast Hooks** (~5 seconds): Essential formatting and security checks
1. **Comprehensive Hooks** (~30 seconds): Complete static analysis

**With AI integration:**

- `--ai-agent` flag enables automatic error resolution
- MCP server allows AI agents to run crackerjack commands
- Structured error output for programmatic fixes

## Core Features

### Project Management

- **Effortless Project Setup:** Initializes new Python projects with a standard directory structure, `pyproject.toml`, and essential configuration files
- **UV Integration:** Manages dependencies and virtual environments using [UV](https://github.com/astral-sh/uv) for lightning-fast package operations
- **Dependency Management:** Automatically detects and manages project dependencies

### Code Quality

- **Automated Code Cleaning:** Removes unnecessary docstrings, line comments, and trailing whitespace
- **Consistent Code Formatting:** Enforces a unified style using [Ruff](https://github.com/astral-sh/ruff), the lightning-fast Python linter and formatter
- **Comprehensive Pre-commit Hooks:** Installs and manages a robust suite of pre-commit hooks
- **Interactive Checks:** Supports interactive pre-commit hooks (like `refurb`, `bandit`, and `pyright`) to fix issues in real-time
- **Static Type Checking:** Enforces type safety with Pyright integration

### Testing & Coverage Ratchet System

- **Built-in Testing:** Automatically runs tests using `pytest` with intelligent parallelization
- **Coverage Ratchet:** Revolutionary coverage system that targets 100% - coverage can only increase, never decrease
- **Milestone Celebrations:** Progress tracking with milestone achievements (15%, 20%, 25%... → 100%)
- **No Arbitrary Limits:** Replaced traditional hard limits with continuous improvement toward perfection
- **Visual Progress:** Rich terminal displays showing journey to 100% coverage
- **Benchmark Testing:** Performance regression detection and monitoring
- **Easy Version Bumping:** Provides commands to bump the project version (patch, minor, or major)
- **Simplified Publishing:** Automates publishing to PyPI via UV with enhanced authentication

#### Coverage Ratchet Philosophy

🎯 **Target: 100% Coverage** - Not an arbitrary number, but true comprehensive testing
📈 **Continuous Improvement** - Each test run can only maintain or improve coverage
🏆 **Milestone System** - Celebrate achievements at 15%, 25%, 50%, 75%, 90%, and 100%
🚫 **No Regression** - Once you achieve a coverage level, you can't go backward

```bash
# Show coverage progress
python -m crackerjack --coverage-status

# Run tests with ratchet system
python -m crackerjack -t

# Example output:
# 🎉 Coverage improved from 10.11% to 15.50%!
# 🏆 Milestone achieved: 15% coverage!
# 📈 Progress: [███░░░░░░░░░░░░░░░░░] 15.50% → 100%
# 🎯 Next milestone: 20% (+4.50% needed)
```

### Git Integration

- **Intelligent Commit Messages:** Analyzes git changes and suggests descriptive commit messages based on file types and modifications
- **Commit and Push:** Commits and pushes your changes with standardized commit messages
- **Pull Request Creation:** Creates pull requests to upstream repositories on GitHub or GitLab
- **Pre-commit Integration:** Ensures code quality before commits

## MCP Server Configuration

### What is MCP?

Model Context Protocol (MCP) enables AI agents to interact directly with Crackerjack's CLI tools for autonomous code quality fixes.

### Setup MCP Server

1. **Install MCP dependencies:**

   ```bash
   uv sync --group mcp
   ```

1. **Start the MCP server:**

   ```bash
   # Starts WebSocket server on localhost:8675 with MCP protocol support
   python -m crackerjack --start-mcp-server
   ```

1. **Configure your MCP client (e.g., Claude Desktop):**

   Add to your MCP configuration file (`mcp.json`):

   **For installed crackerjack (from PyPI):**

   ```json
   {
     "mcpServers": {
       "crackerjack": {
         "command": "uvx",
         "args": [
           "crackerjack",
           "--start-mcp-server"
         ],
         "env": {
           "UV_KEYRING_PROVIDER": "subprocess",
           "EDITOR": "code --wait"
         }
       }
     }
   }
   ```

   **For local development version:**

   ```json
   {
     "mcpServers": {
       "crackerjack": {
         "command": "uvx",
         "args": [
           "--from",
           "/path/to/crackerjack",
           "crackerjack",
           "--start-mcp-server"
         ],
         "env": {
           "UV_KEYRING_PROVIDER": "subprocess",
           "EDITOR": "code --wait"
         }
       }
     }
   }
   ```

### Environment Variables & Security

Crackerjack supports several environment variables for configuration:

- **`UV_PUBLISH_TOKEN`**: PyPI authentication token for publishing ⚠️ **Keep secure!**
- **`UV_KEYRING_PROVIDER`**: Keyring provider for secure credential storage (e.g., "subprocess")
- **`EDITOR`**: Default text editor for interactive commit message editing (e.g., "code --wait")
- **`AI_AGENT`**: Set to "1" to enable AI agent mode with structured JSON output

#### 🔒 Security Best Practices

**Token Security:**

- **Never commit tokens to version control**
- Use `.env` files (add to `.gitignore`)
- Prefer keyring over environment variables
- Rotate tokens regularly

**Recommended setup:**

```bash
# Create .env file (add to .gitignore)
echo "UV_PUBLISH_TOKEN=pypi-your-token-here" > .env
echo ".env" >> .gitignore

# Or use secure keyring storage
keyring set https://upload.pypi.org/legacy/ __token__
```

**Example MCP configuration with environment variables:**

```json
{
  "mcpServers": {
    "crackerjack": {
      "command": "uvx",
      "args": [
        "--from",
        "/path/to/crackerjack",
        "crackerjack",
        "--start-mcp-server"
      ],
      "env": {
        "UV_KEYRING_PROVIDER": "subprocess",
        "EDITOR": "code --wait",
        "UV_PUBLISH_TOKEN": "pypi-your-token-here"
      }
    }
  }
}
```

### Available MCP Tools

**Job Execution & Monitoring:**

- **`execute_crackerjack`**: Start iterative auto-fixing with job tracking
- **`get_job_progress`**: Real-time progress for running jobs
- **`run_crackerjack_stage`**: Execute specific quality stages (fast, comprehensive, tests)

**Error Analysis:**

- **`analyze_errors`**: Analyze and categorize code quality errors
- **`smart_error_analysis`**: AI-powered error analysis with cached patterns

**Session Management:**

- **`get_stage_status`**: Check current status of quality stages
- **`get_next_action`**: Get optimal next action based on session state
- **`session_management`**: Manage sessions with checkpoints and resume capability

**WebSocket Endpoints:**

- **Server URL**: `ws://localhost:8675`
- **Progress Streaming**: `/ws/progress/{job_id}` for real-time updates

### Slash Commands

**`/crackerjack:run`**: Autonomous code quality enforcement with AI agent

```bash
# Through MCP
{
  "command": "/crackerjack:run",
  "args": []
}
```

**`/crackerjack:init`**: Initialize or update project configuration

```bash
# Through MCP
{
  "command": "/crackerjack:init",
  "args": ["--force"]  # Optional: force reinitialize
}
```

## Pre-commit Hook Modes

Crackerjack runs hooks in a two-stage process for optimal development workflow:

### Hook Details

**Fast Hooks (~5 seconds):**

- Ruff formatting and linting
- Trailing whitespace cleanup
- UV lock file updates
- Security credential detection
- Spell checking

**Comprehensive Hooks (~30 seconds):**

- Pyright type checking
- Bandit security analysis
- Dead code detection (vulture)
- Dependency analysis (creosote)
- Complexity limits (complexipy)
- Modern Python patterns (refurb)

```bash
# Default behavior runs comprehensive hooks
python -m crackerjack

# Skip hooks if you only want setup/cleaning
python -m crackerjack -s
```

### Common Commands

```bash
# Quality checks only
python -m crackerjack

# With testing
python -m crackerjack -t

# Full release workflow
python -m crackerjack -a patch

# AI agent mode
python -m crackerjack --ai-agent
```

## Command Reference

**Core Commands:**

```bash
python -m crackerjack          # Quality checks
python -m crackerjack -t       # With testing
python -m crackerjack -a patch # Release workflow
```

**Options:**

- `-i, --interactive`: Rich UI interface
- `-v, --verbose`: Detailed output
- `-s, --skip-hooks`: Skip quality checks
- `-c, --commit`: Auto-commit changes
- `-x, --clean`: Remove docstrings/comments

## Style Guide

**Code Standards:**

- Python 3.13+ with modern type hints (`|` unions, PEP 695)
- No docstrings (self-documenting code)
- Pathlib over os.path
- Protocol-based interfaces
- Cognitive complexity ≤15 per function
- UV for dependency management

## Publishing & Version Management

### 🔐 Secure PyPI Authentication

**Keyring Storage (Most Secure):**

```bash
# Install keyring support
uv add keyring

# Store token securely
keyring set https://upload.pypi.org/legacy/ __token__
# Enter your PyPI token when prompted
```

**Environment Variable (Alternative):**

```bash
# For CI/CD or temporary use
export UV_PUBLISH_TOKEN=pypi-your-token-here

# ⚠️ Security Warning: Never commit this to git
```

**Environment File (Local Development):**

```bash
# Create .env file (must be in .gitignore)
echo "UV_PUBLISH_TOKEN=pypi-your-token-here" > .env
echo ".env" >> .gitignore
```

### Version Management

```bash
python -m crackerjack -p patch  # 1.0.0 -> 1.0.1
python -m crackerjack -p minor  # 1.0.0 -> 1.1.0
python -m crackerjack -p major  # 1.0.0 -> 2.0.0
```

### 🛡️ Security Considerations

- **Token Rotation**: Rotate PyPI tokens every 90 days
- **Scope Limitation**: Use project-scoped tokens when possible
- **Access Review**: Regularly audit who has publish access
- **Backup Tokens**: Keep backup tokens in secure location

## MCP Integration

**AI Agent Support:**
Crackerjack provides a WebSocket-enabled MCP server for AI agent integration:

```bash
# Start WebSocket MCP server on localhost:8675
python -m crackerjack --start-mcp-server

# Monitor job progress via WebSocket
python -m crackerjack.mcp.progress_monitor <job_id> ws://localhost:8675
```

**MCP client configuration (stdio-based):**

```json
{
  "mcpServers": {
    "crackerjack": {
      "command": "uvx",
      "args": [
        "--from",
        "/path/to/crackerjack",
        "crackerjack",
        "--start-mcp-server"
      ]
    }
  }
}
```

**WebSocket MCP client configuration:**

- **Server URL**: `ws://localhost:8675`
- **Protocol**: WebSocket-based MCP with real-time progress streaming
- **Endpoints**: `/ws/progress/{job_id}` for live job monitoring

**Available tools:** `execute_crackerjack`, `get_job_progress`, `run_crackerjack_stage`, `analyze_errors`, `smart_error_analysis`, `get_next_action`, `session_management`

## 🔧 Troubleshooting

### Common Issues

#### Installation Problems

```bash
# UV not found
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Python 3.13+ required
uv python install 3.13
uv python pin 3.13
```

#### Authentication Errors

```bash
# PyPI token issues
keyring get https://upload.pypi.org/legacy/ __token__  # Verify stored token
keyring set https://upload.pypi.org/legacy/ __token__  # Reset if needed

# Permission denied
chmod +x ~/.local/bin/uv
```

#### Hook Failures

```bash
# Pre-commit hooks failing
python -m crackerjack --skip-hooks  # Skip hooks temporarily
pre-commit clean                     # Clear hook cache
pre-commit install --force          # Reinstall hooks

# Update hooks
python -m crackerjack --update-precommit

# Type checking errors
python -m crackerjack               # Run quality checks
```

#### MCP Server Issues

```bash
# Server won't start
python -m crackerjack --start-mcp-server --verbose

# WebSocket connection issues
# Check if server is running on localhost:8675
netstat -an | grep :8675

# Test WebSocket connectivity
curl -s "http://localhost:8675/" || echo "Server not responding"
```

#### Performance Issues

```bash
# Slow execution
python -m crackerjack --test-workers 1    # Reduce parallelism
python -m crackerjack --skip-hooks        # Skip time-consuming checks

# Memory issues
export UV_CACHE_DIR=/tmp/uv-cache         # Use different cache location
```

### Debug Mode

```bash
# Enable verbose output
python -m crackerjack --verbose

# Check debug logs (in XDG cache directory)
ls ~/.cache/crackerjack/logs/debug/

# MCP debugging
python -m crackerjack --start-mcp-server --verbose
```

### Getting Help

- **GitHub Issues**: [Report bugs](https://github.com/lesleslie/crackerjack/issues)
- **Command Help**: `python -m crackerjack --help`
- **MCP Tools**: Use `get_next_action` tool for guidance

## Contributing

1. Fork and clone the repository
1. Run `uv sync --all-groups` to install dependencies
1. Ensure `python -m crackerjack` passes all checks
1. Submit pull request

**Requirements:** Python 3.13+, UV package manager, all quality checks must pass

## License

BSD 3-Clause License - see [LICENSE](LICENSE) file.

______________________________________________________________________

**Issues:** [GitHub Issues](https://github.com/lesleslie/crackerjack/issues)
**Repository:** [GitHub](https://github.com/lesleslie/crackerjack)
