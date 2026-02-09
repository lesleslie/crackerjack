# Crackerjack Architecture

## Overview

Crackerjack is a quality control and CI/CD automation platform designed to enforce code quality standards across the development ecosystem. It provides a unified interface for running quality checks, managing test suites, and integrating with CI/CD pipelines.

## Core Principles

1. **Quality-First**: Enforce standards before code reaches production
2. **Developer Experience**: Fast, intuitive, and non-intrusive
3. **Extensibility**: Easy to add custom checks and quality gates
4. **Integration**: Works with existing tools and CI/CD platforms
5. **AI-Assisted**: Optional AI-powered auto-fix capabilities

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Crackerjack                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │     CLI       │  │  MCP Server  │  │   Web UI        │  │
│  │  Interface    │  │  (FastMCP)   │  │   (Optional)    │  │
│  └───────┬───────┘  └──────┬───────┘  └────────┬────────┘  │
│          │                  │                   │            │
│          └──────────────────┼───────────────────┘            │
│                             │                                │
│                  ┌──────────▼──────────┐                     │
│                  │   Command Router    │                     │
│                  └──────────┬──────────┘                     │
│                             │                                │
│    ┌────────────────────────┼────────────────────────┐      │
│    │                        │                        │      │
│    │                        │                        │      │
│┌───▼────┐  ┌─────────────┐  │  ┌──────────────────┐ │      │
│Config  │  │  Quality    │  │  │    Check         │ │      │
│Manager │  │   Gates     │  │  │    Coordinator   │ │      │
│└───┬────┘  └──────┬─────┘  │  └────────┬─────────┘ │      │
│    │              │         │           │           │      │
│    └──────────────┼─────────┴───────────┼───────────┘      │
│                   │                     │                   │
│    ┌──────────────▼─────────────────────▼───────────┐      │
│    │               Core Engine                      │      │
│    │  ┌─────────────────────────────────────────┐  │      │
│    │  │  Test Manager (pytest, unittest, etc.)  │  │      │
│    │  └─────────────────────────────────────────┘  │      │
│    │  ┌─────────────────────────────────────────┐  │      │
│    │  │  Linter Manager (ruff, flake8, etc.)    │  │      │
│    │  └─────────────────────────────────────────┘  │      │
│    │  ┌─────────────────────────────────────────┐  │      │
│    │  │  Security Manager (bandit, safety)      │  │      │
│    │  └─────────────────────────────────────────┘  │      │
│    │  ┌─────────────────────────────────────────┐  │      │
│    │  │  Coverage Manager (coverage.py)         │  │      │
│    │  └─────────────────────────────────────────┘  │      │
│    └───────────────────────────────────────────────┘      │
│                   │                                      │
│    ┌──────────────▼───────────────────────────────┐      │
│    │          AI Auto-Fix Engine (Optional)        │      │
│    │  ┌─────────────────────────────────────────┐  │      │
│    │  │  Agent Orchestration                    │  │      │
│    │  └─────────────────────────────────────────┘  │      │
│    └───────────────────────────────────────────────┘      │
│                   │                                      │
│    ┌──────────────▼───────────────────────────────┐      │
│    │            Reporting & Analytics              │      │
│    │  ┌─────────────────────────────────────────┐  │      │
│    │  │  Results Aggregator                      │  │      │
│    │  └─────────────────────────────────────────┘  │      │
│    │  ┌─────────────────────────────────────────┐  │      │
│    │  │  Metrics Storage                         │  │      │
│    │  └─────────────────────────────────────────┘  │      │
│    └───────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. CLI Interface

**Location**: `crackerjack/cli/`

The CLI provides the primary user interface for interacting with Crackerjack:

- **Command routing**: Typer-based command parsing
- **Configuration management**: Load and validate settings
- **Output formatting**: Human-readable and machine-readable output
- **Progress tracking**: Real-time progress updates

**Key Commands**:
- `crackerjack run` - Execute quality checks
- `crackerjack status` - View quality metrics
- `crackerjack config` - Manage configuration
- `crackerjack gate` - Manage quality gates
- `crackerjack mcp` - MCP server control

### 2. MCP Server

**Location**: `crackerjack/mcp/`

FastMCP-based server for integration with AI tools and IDEs:

- **Tool exposure**: Expose checks as MCP tools
- **AI agent integration**: Enable AI agents to run quality checks
- **IDE integration**: Real-time quality feedback in editors
- **Protocol compliance**: Standard MCP protocol implementation

**MCP Tools**:
- `run_check` - Execute specific quality check
- `run_all_checks` - Execute all configured checks
- `get_status` - Get current quality status
- `get_metrics` - Get quality metrics
- `ai_fix` - Apply AI-powered fixes

### 3. Configuration System

**Location**: `crackerjack/config/`

Hierarchical configuration management:

**Configuration Layers** (highest to lowest priority):
1. Command-line arguments
2. Environment variables (`CRACKERJACK_*`)
3. User config (`~/.crackerjack/config.toml`)
4. Project config (`crackerjack.toml`)
5. Default values

**Key Features**:
- Type validation with Pydantic
- Environment variable interpolation
- Profile-based configuration
- Runtime validation

### 4. Quality Gates

**Location**: `crackerjack/gates/`

Quality gate management and enforcement:

**Gate Components**:
- **Checks**: Required quality checks
- **Thresholds**: Minimum quality thresholds (coverage, complexity, etc.)
- **Dependencies**: Check execution order
- **Actions**: Pass/fail actions

**Gate Types**:
- `default` - Standard quality requirements
- `strict` - Enforced for production branches
- `minimal` - Basic checks only
- `custom` - User-defined gates

### 5. Check Coordinator

**Location**: `crackerjack/checks/`

Orchestrates execution of quality checks:

**Check Types**:

**Linting**:
- `ruff` - Fast Python linter and formatter
- `flake8` - Style guide enforcement
- `black` - Code formatting
- `isort` - Import sorting

**Testing**:
- `pytest` - Test framework
- `unittest` - Standard library testing
- `hypothesis` - Property-based testing

**Security**:
- `bandit` - Security linter
- `safety` - Dependency vulnerability scanning
- `creosote` - Unused dependency detection

**Quality**:
- `coverage` - Code coverage reporting
- `complexipy` - Cyclomatic complexity analysis
- `refurb` - Modern Python suggestions
- `codespell` - Typo detection

**Execution Features**:
- Parallel execution
- Dependency resolution
- Timeout management
- Caching and incremental runs
- Failure handling and retry logic

### 6. Test Manager

**Location**: `crackerjack/managers/test_manager.py`

Manages test execution and result aggregation:

**Responsibilities**:
- Test discovery and collection
- Test execution (pytest, unittest, etc.)
- Result aggregation and reporting
- Coverage calculation
- Test history tracking

**Test Integration**:
- pytest: Primary test framework
- unittest: Standard library tests
- Integration tests: Cross-component testing
- Property-based tests: Hypothesis integration

### 7. AI Auto-Fix Engine

**Location**: `crackerjack/ai/`

Optional AI-powered code fixing:

**Components**:

**Agent Orchestration**:
- Multiple specialized AI agents
- Agent selection and routing
- Context-aware fixing

**Supported Providers**:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Local models (via Ollama)

**Fix Strategies**:
- Automatic fixes for simple issues
- Interactive fixes for complex issues
- Dry-run mode for preview
- Rollback capability

**Safety Features**:
- Change validation
- Test verification
- Rollback on failure
- Approval workflow

### 8. Reporting & Analytics

**Location**: `crackerjack/reporting/`

Results aggregation and metrics:

**Output Formats**:
- Console output (human-readable)
- JSON (machine-readable)
- HTML (detailed reports)
- JUnit XML (CI/CD integration)

**Metrics Tracking**:
- Check pass/fail rates
- Coverage trends
- Complexity trends
- Execution time
- Historical data

**Storage**:
- Local file system (JSON, SQLite)
- Remote storage (optional)
- Time-series data for trends

## Data Flow

### 1. Check Execution Flow

```
User Command (crackerjack run)
    │
    ├─> Load Configuration
    │   └─> crackerjack.toml
    │   └─> ~/.crackerjack/config.toml
    │   └─> Environment variables
    │
    ├─> Resolve Quality Gate
    │   └─> Get required checks
    │   └─> Get thresholds
    │   └─> Resolve dependencies
    │
    ├─> Execute Checks (in parallel)
    │   ├─> Linter Manager
    │   ├─> Test Manager
    │   ├─> Security Manager
    │   └─> Coverage Manager
    │
    ├─> Aggregate Results
    │   └─> Collect outputs
    │   └─> Calculate metrics
    │   └─> Compare with thresholds
    │
    ├─> Apply AI Fixes (if enabled)
    │   └─> Analyze failures
    │   └─> Generate fixes
    │   └─> Validate fixes
    │
    └─> Generate Report
        ├─> Console output
        ├─> JSON output
        └─> HTML report
```

### 2. MCP Tool Invocation Flow

```
MCP Client (AI/IDE)
    │
    ├─> Call MCP Tool
    │   └─> run_check
    │   └─> run_all_checks
    │   └─> get_status
    │
    ├─> MCP Server (FastMCP)
    │   └─> Validate parameters
    │   └─> Route to Core Engine
    │
    ├─> Core Engine
    │   └─> Execute checks
    │   └─> Aggregate results
    │
    └─> Return Results
        └─> JSON response
        └─> Error handling
```

## Configuration Architecture

### crackerjack.toml Structure

```toml
# Core configuration
[general]
project_name = "my-project"
parallel_execution = true
max_parallel_jobs = 4

# Check configuration
[checks]
enabled = ["ruff", "pytest", "bandit", "safety"]
disabled = []

# Check-specific settings
[checks.ruff]
config = ".ruff.toml"
fix = true

[checks.pytest]
args = ["-v", "--tb=short"]
timeout = 300

# Coverage configuration
[coverage]
enabled = true
min_coverage = 80
branch_coverage = true
fail_under = 80

# Complexity configuration
[complexity]
enabled = true
max_complexity = 15

# Quality gates
[gates.default]
checks = ["ruff", "pytest", "bandit"]
coverage = 80
complexity = 15

[gates.strict]
checks = ["ruff", "pytest", "bandit", "safety"]
coverage = 90
complexity = 10

# AI auto-fix
[ai_fix]
enabled = false
provider = "openai"
model = "gpt-4"
api_key_env = "OPENAI_API_KEY"
max_fixes = 10
dry_run = false

# Output configuration
[output]
format = "console"  # console, json, html
verbose = false
colored = true

# Reporting
[reporting]
history_file = ".crackerjack/history.json"
metrics_db = ".crackerjack/metrics.db"
trend_analysis = true
```

## Extensibility

### Custom Checks

Add custom checks by implementing the `Check` protocol:

```python
from crackerjack.checks.base import Check, CheckResult, CheckStatus

class CustomCheck(Check):
    name = "custom-check"
    description = "My custom quality check"

    def run(self, context: CheckContext) -> CheckResult:
        # Implement check logic
        issues = []

        # Return result
        return CheckResult(
            status=CheckStatus.PASS if not issues else CheckStatus.FAIL,
            message=f"Found {len(issues)} issues",
            details=issues
        )
```

### Custom Quality Gates

Define custom gates in configuration:

```toml
[gates.my-custom-gate]
checks = ["ruff", "pytest", "custom-check"]
coverage = 85
complexity = 12
custom_threshold = 100
```

### Custom Report Formats

Implement custom report formatters:

```python
from crackerjack.reporting.formatter import ReportFormatter

class CustomFormatter(ReportFormatter):
    def format(self, results: CheckResults) -> str:
        # Custom formatting logic
        pass
```

## Performance Considerations

### Parallel Execution

- **Default**: 4 parallel jobs
- **Configurable**: `max_parallel_jobs` in configuration
- **Smart scheduling**: Respects dependencies between checks

### Caching

- **Test caching**: pytest cache integration
- **Incremental runs**: Only run affected checks
- **Result caching**: Cache check results for unchanged files

### Resource Management

- **Memory limits**: Configurable memory limits per check
- **Timeout enforcement**: Per-check and overall timeouts
- **Cleanup**: Automatic cleanup of temporary files

## Security Considerations

### Input Validation

- All inputs validated with Pydantic models
- Path traversal prevention
- Command injection prevention

### Secrets Management

- API keys via environment variables
- No secrets in configuration files
- Secure credential storage

### Dependency Scanning

- Automated vulnerability scanning with `safety`
- License compliance checking
- Dependency freshness monitoring

## Monitoring & Observability

### Metrics Collection

- Check execution time
- Pass/fail rates
- Coverage trends
- Complexity trends

### Logging

- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Per-check log files

### Health Checks

- MCP server health endpoints
- Dependency availability checks
- Resource utilization monitoring

## Testing Strategy

### Unit Tests

- Test individual components
- Mock external dependencies
- Fast execution (<1s per test)

### Integration Tests

- Test component interactions
- Real tool execution (ruff, pytest, etc.)
- Slower execution (~10s per test)

### End-to-End Tests

- Full workflow testing
- Real project scenarios
- Slowest execution (~1m per test)

## Architecture Decision Records

See `docs/adr/` for detailed architecture decisions:

- **ADR-001**: MCP-first architecture
- **ADR-002**: Multi-agent orchestration
- **ADR-003**: Property-based testing
- **ADR-004**: Quality gate thresholds
- **ADR-005**: Agent skill routing

## Future Enhancements

### Planned Features

- [ ] Distributed execution across multiple machines
- [ ] Real-time code quality monitoring
- [ ] Advanced anomaly detection
- [ ] Integration with more CI/CD platforms
- [ ] Web dashboard for metrics visualization
- [ ] Custom check marketplace

### Under Consideration

- [ ] Plugin system for third-party checks
- [ ] Machine learning for issue prediction
- [ ] Team collaboration features
- [ ] Code review integration
- [ ] Cost optimization for cloud execution

## Related Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[docs/guides/](docs/guides/)** - Detailed guides
- **[docs/reference/](docs/reference/)** - Complete reference
- **[CHANGELOG.md](CHANGELOG.md)** - Version history
