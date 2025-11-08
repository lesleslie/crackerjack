# Crackerjack Project Context

## Project Overview

**Crackerjack** is an advanced AI-driven Python development platform that transforms Python development from reactive firefighting to proactive excellence. It's an opinionated tool that enforces high code quality standards through intelligent automation, comprehensive quality enforcement, and AI-powered assistance.

### Key Features

1. **AI-Powered Code Quality**: 10+ specialized AI agents that prevent issues before they occur
1. **Autonomous Quality Enforcement**: Intelligent auto-fixing with architectural planning
1. **Zero-Compromise Standards**: 100% test coverage, complexity ≤15, security-first patterns
1. **Unified Toolchain**: Replaces 6+ separate tools with a single command interface
1. **MCP Integration**: Model Context Protocol server for AI agent integration

### Core Philosophy

The Crackerjack philosophy is "If your code needs fixing after it's written, you're doing it wrong." The tool prevents problems through intelligent architecture and proactive patterns, making exceptional code the natural outcome.

## Project Structure

```
crackerjack/
├── crackerjack/                 # Main source code
│   ├── __main__.py             # Entry point
│   ├── agents/                 # AI agent implementations
│   ├── cli/                    # Command-line interface
│   ├── config/                 # Configuration management
│   ├── core/                   # Core workflow orchestration
│   ├── intelligence/           # AI intelligence system
│   ├── mcp/                    # Model Context Protocol integration
│   ├── models/                 # Data models and protocols
│   ├── monitoring/             # Progress monitoring
│   ├── orchestration/          # Advanced workflow orchestration
│   ├── services/               # Core services
│   └── ...
├── tests/                      # Test suite
├── docs/                       # Documentation
├── examples/                   # Example configurations
└── ...
```

## Technology Stack

- **Python 3.13+**: Primary language with modern type hints
- **UV**: Package manager for fast dependency management
- **Typer**: CLI framework
- **Rich**: Terminal UI library
- **Pydantic**: Data validation
- **FastAPI**: Web framework for MCP server
- **MCP**: Model Context Protocol integration
- **Ruff**: Code formatting and linting
- **Pyright**: Static type checking
- **Pytest**: Testing framework

## Core Components

### 1. Workflow Orchestration

The `WorkflowOrchestrator` in `crackerjack/core/workflow_orchestrator.py` is the central component that coordinates the entire development workflow:

- **Cleaning Phase**: Removes unnecessary code elements
- **Quality Phase**: Runs fast and comprehensive hooks
- **Testing Phase**: Executes test suite with coverage ratchet
- **Publishing Phase**: Handles version bumping and package publishing
- **Commit Phase**: Manages Git operations

### 2. AI Agent System

Located in `crackerjack/agents/`, the AI agent system includes:

- **AgentCoordinator**: Manages multiple specialized agents
- **Specialized Agents**:
  - ArchitectAgent: High-level architectural planning
  - FormattingAgent: Code formatting fixes
  - SecurityAgent: Security vulnerability detection and fixes
  - PerformanceAgent: Performance optimization
  - TestCreationAgent: Test generation
  - RefactoringAgent: Code refactoring for complexity reduction

### 3. MCP Integration

The Model Context Protocol integration in `crackerjack/mcp/` enables AI agents to interact directly with Crackerjack's CLI tools:

- **MCP Server**: WebSocket server on port 8675
- **Progress Monitoring**: Real-time job tracking
- **Tool Integration**: Exposes Crackerjack functionality to AI agents

### 4. Coverage Ratchet System

A revolutionary coverage system in `crackerjack/services/coverage_ratchet.py` that targets 100% coverage with these principles:

- Coverage can only increase, never decrease
- Milestone celebrations at 15%, 25%, 50%, 75%, 90%, and 100%
- 2% tolerance margin to prevent flaky test failures

## Key Commands

### Basic Usage

```bash
# Initialize a new project
python -m crackerjack

# Run quality checks only
python -m crackerjack

# Run with testing
python -m crackerjack -t

# Full release workflow
python -m crackerjack -a patch

# Interactive mode
python -m crackerjack -i
```

### AI Agent Mode

```bash
# Enable AI agent auto-fixing
python -m crackerjack --ai-agent -t -v

# Enable AI agent fixing with structured logging to stderr
python -m crackerjack --ai-fix --verbose

# Enable AI debugging with detailed structured logs
python -m crackerjack --ai-debug --run-tests

# Enable both AI fixing and debugging with maximum logging
python -m crackerjack --ai-fix --ai-debug --run-tests

# Start MCP server for AI integration
python -m crackerjack --start-mcp-server

# Monitor progress via WebSocket
python -m crackerjack.mcp.progress_monitor <job_id> ws://localhost:8675
```

### Monitoring and Dashboard

```bash
# Start multi-project progress monitor
python -m crackerjack --monitor

# Start enhanced progress monitor
python -m crackerjack --enhanced-monitor

# Start comprehensive dashboard
python -m crackerjack --dashboard
```

## Development Conventions

### Code Standards

- Python 3.13+ with modern type hints (`|` unions, PEP 695)
- No docstrings (self-documenting code)
- Pathlib over os.path
- Protocol-based interfaces
- Cognitive complexity ≤15 per function
- UV for dependency management

### Testing Practices

- **100% Test Coverage Goal**: Using the coverage ratchet system
- **Pytest**: Primary testing framework
- **Hypothesis**: Property-based testing
- **Benchmark Testing**: Performance regression detection
- **Parallel Execution**: Using pytest-xdist for faster test runs

### Quality Enforcement

1. **Fast Hooks** (~5 seconds):

   - Ruff formatting and linting
   - Trailing whitespace cleanup
   - UV lock file updates

1. **Comprehensive Hooks** (~30 seconds):

   - Pyright type checking
   - Bandit security analysis
   - Dead code detection (vulture)
   - Dependency analysis (creosote)
   - Complexity limits (complexipy)
   - Modern Python patterns (refurb)

## Configuration

### Environment Variables

- `UV_PUBLISH_TOKEN`: PyPI authentication token
- `UV_KEYRING_PROVIDER`: Keyring provider for secure credential storage
- `EDITOR`: Default text editor for interactive commit message editing
- `AI_AGENT`: Set to "1" to enable AI agent mode with structured JSON output

### PyProject.toml Structure

The project uses a comprehensive pyproject.toml configuration that includes:

- Build system configuration (Hatchling)
- Project metadata and dependencies
- Tool configurations (Ruff, Pytest, Pyright, etc.)
- Dependency groups for different functionalities

## Security Considerations

### Token Management

- **Keyring Storage**: Most secure method for PyPI tokens
- **Environment Variables**: Acceptable for CI/CD
- **.env Files**: For local development (must be in .gitignore)

### Best Practices

- Rotate PyPI tokens every 90 days
- Use project-scoped tokens when possible
- Regularly audit who has publish access
- Keep backup tokens in secure location

## Common Development Tasks

### Adding a New Feature

1. Create feature branch
1. Implement functionality following code standards
1. Add comprehensive tests
1. Run `python -m crackerjack -t` to ensure quality
1. Create pull request

### Running Tests

```bash
# Run all tests
python -m crackerjack -t

# Run tests in benchmark mode
python -m crackerjack --benchmark

# Run specific test file
python -m pytest tests/test_specific.py
```

### Debugging

```bash
# Enable verbose output
python -m crackerjack --verbose

# Enable AI agent debugging
python -m crackerjack --ai-debug

# Check debug logs
ls ~/.cache/crackerjack/logs/debug/
```

## Troubleshooting

### Common Issues

1. **Installation Problems**: Ensure Python 3.13+ and UV are installed
1. **Authentication Errors**: Check PyPI token storage and permissions
1. **Hook Failures**: Run with `--skip-hooks` temporarily to isolate issues
1. **MCP Server Issues**: Check if server is running on localhost:8675

### Performance Issues

- Reduce parallelism with `--test-workers 1`
- Skip time-consuming checks with `--skip-hooks`
- Use different cache location with `UV_CACHE_DIR`

## Contributing Guidelines

1. Fork and clone the repository
1. Run `uv sync --group dev` to install dependencies
1. Ensure `python -m crackerjack` passes all checks
1. Submit pull request

Requirements: Python 3.13+, UV package manager, all quality checks must pass
