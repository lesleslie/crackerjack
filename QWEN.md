# Crackerjack Project Overview

## Project Purpose

Crackerjack is an advanced AI-driven Python development platform that transforms Python development from reactive firefighting to proactive excellence. It provides sophisticated automation, comprehensive quality enforcement, and AI-powered assistance to ensure code meets the highest standards before production.

## Core Architecture

The project is built on the **ACB (Asynchronous Component Base)** framework, providing:

- Advanced-grade dependency injection
- Intelligent caching mechanisms
- Parallel execution capabilities
- Async-first design with lifecycle management
- Clean separation of concerns through adapters, orchestrators, and services

## Key Features

### Quality Assurance

- Dual-stage quality checks (fast hooks ~5s, comprehensive hooks ~30s)
- Direct tool invocation with no wrapper overhead (70% faster than legacy pre-commit)
- 17 integrated quality hooks including Ruff, Bandit, Zuban (fast type checker), Skylos (dead code detection)
- AI-powered auto-fixing with 9 specialized agents covering security, refactoring, performance, documentation, etc.

### Development Workflow

- Code cleaning stage between fast and comprehensive hooks for optimal results
- Comprehensive testing with coverage ratchet system targeting 100% coverage
- Interactive quality checks with real-time feedback
- Intelligent configuration management and template systems

### AI Integration

- Model Context Protocol (MCP) server for AI agent integration
- WebSocket-enabled real-time progress monitoring
- 12 specialized AI agents for different aspects (security, refactoring, performance, documentation, etc.)
- Confidence scoring and collaborative multi-agent processing

### Performance Optimizations

- Content-based caching with 70% hit rate
- 11 concurrent adapters for parallel execution (76% speedup)
- Rust-powered tools (Zuban 20-200x faster than Pyright, Skylos 20x faster than Vulture)
- Async-first workflow engine

## Building and Running

### Prerequisites

- Python 3.13+
- UV package manager

### Installation

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Crackerjack
uv tool install crackerjack
```

### Main Commands

```bash
# Quality checks only
python -m crackerjack

# Quality checks + tests
python -m crackerjack --run-tests

# AI-powered auto-fixing + tests (recommended)
python -m crackerjack --ai-fix --run-tests

# Full release workflow
python -m crackerjack --all patch

# MCP server for AI agent integration
python -m crackerjack --start-mcp-server
```

## Development Conventions

### Code Standards

- Python 3.13+ with modern type hints
- Pathlib over os.path
- Protocol-based interfaces
- Cognitive complexity ≤15 per function
- No docstrings (self-documenting code)

### Architecture Patterns

- ACB dependency injection with `@depends.inject` and `Inject[Protocol]`
- Asynchronous adapters for quality tools
- Centralized configuration management
- Type-safe protocols across components

### Testing

- Coverage ratchet system (can only increase, never decrease)
- Parallel test execution with configurable workers
- Benchmark and property-based testing support
- Comprehensive error pattern analysis

## Project Structure

- **adapters/**: Tool adapters for quality checks (formatting, linting, type checking, security, etc.)
- **agents/**: AI agent implementations and coordination
- **cli/**: Command-line interface handlers
- **config/**: Configuration management and settings
- **core/**: Core workflow engines and foundational components
- **mcp/**: Model Context Protocol server and integration
- **orchestration/**: Hook orchestration and execution strategies
- **services/**: Business logic and utility services
- **tools/**: Quality and validation tools
- **workflows/**: Complete workflow definitions

## Security Considerations

- Secure credential management via keyring
- Pattern-based security scanning (tokens, unsafe functions, etc.)
- Shell injection prevention
- Localhost-only MCP server by default
- Input validation and timeout protections

## MCP Integration

The platform includes an MCP (Model Context Protocol) server for AI agent integration:

- WebSocket-based with real-time progress streaming
- Available tools: execute_crackerjack, get_job_progress, analyze_errors, etc.
- Configurable endpoints at ws://localhost:8675

## Troubleshooting

- Check verbose output with --verbose flag
- Verify UV and Python 3.13+ installation
- Use --skip-hooks for temporary bypass of quality checks
- MCP server issues: check localhost:8675 connectivity
