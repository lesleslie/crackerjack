> Crackerjack Docs: [Main](<../../README.md>) | [CLAUDE.md](<../../CLAUDE.md>) | [Services](<./README.md>)

# Services

Service abstractions and provider integrations for infrastructure, quality, monitoring, and AI capabilities.

## Overview

The services package contains 60+ specialized service modules organized into functional categories. Services handle infrastructure concerns (filesystem, git, config), quality enforcement, monitoring, security, and AI integration. Most services follow ACB patterns with dependency injection and lifecycle management.

## Service Categories

### Core Infrastructure

**Filesystem & File Operations**

- `filesystem.py`: Core filesystem operations with path validation
- `enhanced_filesystem.py`: Advanced filesystem operations with atomic writes
- `file_modifier.py`: Safe file modification with backup and rollback
- `file_filter.py`: File filtering and pattern matching
- `file_hasher.py`: Content hashing for change detection
- `backup_service.py`: Automated backup creation and management

**Version Control**

- `git.py`: Git operations (commit, push, status, branch management)
- `intelligent_commit.py`: AI-powered commit message generation
- `changelog_automation.py`: Automatic changelog generation from commits

**Configuration Management**

- `unified_config.py`: Unified configuration loading and validation
- `config_merge.py`: Intelligent configuration merging for initialization
- `config_template.py`: Configuration template management and versioning
- `config_integrity.py`: Configuration validation and integrity checking

**Initialization**

- `initialization.py`: Project initialization and setup workflows

### Quality & Testing

**Coverage & Testing**

- `coverage_ratchet.py`: Coverage ratchet system (never decrease coverage)
- `coverage_badge_service.py`: Coverage badge generation and updates
- `incremental_executor.py`: Incremental test execution
- `parallel_executor.py`: Parallel test execution with pytest-xdist

**Quality Enforcement**

- `tool_filter.py`: Quality tool filtering and selection
- `tool_version_service.py`: Tool version management and compatibility
- `quality/` subdirectory — Quality-specific services

### Security

**Input Validation & Security**

- `input_validator.py`: Comprehensive input validation framework
- `validation_rate_limiter.py`: Rate limiting for validation failures
- `security.py`: Core security utilities and validation
- `security_logger.py`: Security event logging with severity levels
- `secure_path_utils.py`: Path traversal prevention and validation
- `secure_subprocess.py`: Safe subprocess execution without shell injection

**Status & Authentication**

- `status_security_manager.py`: Security manager for status operations
- `status_authentication.py`: Authentication for status endpoints
- `bounded_status_operations.py`: Bounded operations for status queries
- `thread_safe_status_collector.py`: Thread-safe status data collection
- `secure_status_formatter.py`: Secure formatting for status output

**Resource Management**

- `websocket_resource_limiter.py`: WebSocket connection and resource limits

### Monitoring & Metrics

**Health & Metrics**

- `health_metrics.py`: Health metrics collection and reporting
- `metrics.py`: General metrics tracking and aggregation
- `profiler.py`: Performance profiling and analysis
- `dependency_monitor.py`: Dependency health monitoring
- `monitoring/` subdirectory — Monitoring-specific services

**Debugging & Logging**

- `debug.py`: Debug utilities and helpers
- `logging.py`: Structured logging configuration
- `log_manager.py`: Log file management and rotation

### Pattern Analysis & Intelligence

**Pattern Detection & Analysis**

- `regex_patterns.py`: Centralized regex pattern registry (advanced-grade)
- `regex_utils.py`: Regex utilities and validation
- `pattern_detector.py`: Code pattern detection and analysis
- `pattern_cache.py`: Pattern caching for performance
- `error_pattern_analyzer.py`: Error pattern analysis and categorization

**AI & Intelligence**

- `anomaly_detector.py`: Anomaly detection in code and metrics
- `predictive_analytics.py`: Predictive analytics for quality trends
- `ai/` subdirectory — AI-specific services
- `vector_store.py`: Vector storage for semantic search

**Analysis & Optimization**

- `dependency_analyzer.py`: Dependency graph analysis
- `version_analyzer.py`: Version compatibility analysis
- `heatmap_generator.py`: Code complexity heatmap generation
- `memory_optimizer.py`: Memory usage optimization
- `enterprise_optimizer.py`: Enterprise-level optimization strategies

### Documentation & Code Analysis

**Documentation**

- `documentation_generator.py`: Automated API documentation generation
- `documentation_service.py`: Documentation management and updates

**Code Intelligence**

- `api_extractor.py`: API surface extraction and analysis
- `smart_scheduling.py`: Intelligent task scheduling

### Language Server Protocol (LSP)

**LSP Integration**

- `lsp_client.py`: Generic LSP client implementation
- `zuban_lsp_service.py`: Zuban LSP service integration
- `server_manager.py`: LSP server lifecycle management

### Utilities

**Cache & Performance**

- `cache.py`: General-purpose caching
- `terminal_utils.py`: Terminal and console utilities
- `version_checker.py`: Version checking and updates

## Architecture

### ACB Compliance Status

Based on Phase 2-4 refactoring audit:

| Category | Compliance | Status | Notes |
|----------|-----------|--------|-------|
| Core Infrastructure | 95% | ✅ Excellent | Phase 3 refactored, consistent constructors |
| Security Services | 95% | ✅ Excellent | Comprehensive validation and logging |
| Quality Services | 90% | ✅ Good | Coverage ratchet, testing infrastructure |
| Monitoring Services | 85% | ✅ Good | Health metrics, profiling |
| LSP Services | 80% | ✅ Good | Server management, client integration |
| AI Services | 75% | ⚠️ Mixed | Some legacy patterns remain |

### Dependency Injection Pattern

Most services follow ACB dependency injection:

```python
from acb.depends import depends, Inject
from crackerjack.models.protocols import Console, CrackerjackCache


@depends.inject
class FileSystemService:
    def __init__(
        self,
        console: Inject[Console] = None,
        cache: Inject[CrackerjackCache] = None,
    ) -> None:
        self.console = console
        self.cache = cache

    async def init(self) -> None:
        # Async initialization if needed
        pass
```

## Usage Examples

### Filesystem Operations

```python
from crackerjack.services.filesystem import FileSystemService

fs = FileSystemService()
await fs.init()

# Safe file operations
content = await fs.read_file(Path("config.yaml"))
await fs.write_file(Path("output.txt"), "data")
```

### Git Operations

```python
from crackerjack.services.git import GitService

git = GitService()
await git.init()

# Commit with intelligent message
await git.commit_changes(
    message="Auto-generated commit message", files=["file1.py", "file2.py"]
)
```

### Coverage Ratchet

```python
from crackerjack.services.coverage_ratchet import CoverageRatchet

ratchet = CoverageRatchet()
current = 21.6
baseline = 19.6

if ratchet.validate_coverage(current, baseline):
    print("Coverage improved!")
```

### Security Validation

```python
from crackerjack.services.input_validator import get_input_validator

validator = get_input_validator()
result = validator.validate_command_args("safe_command arg1 arg2")

if result.valid:
    # Safe to execute
    execute(result.sanitized_value)
```

### Pattern Detection

```python
from crackerjack.services.regex_patterns import SAFE_PATTERNS

# Use centralized, validated patterns
text = SAFE_PATTERNS["fix_hyphenated_names"].apply(text)
```

## Service Subdirectories

### AI Services (`ai/`)

AI-specific services for code analysis and generation:

- Claude integration
- Code generation
- Semantic analysis
- See [ai/README.md](<./ai/README.md>)

### Monitoring Services (`monitoring/`)

Health and performance monitoring:

- Real-time metrics
- Performance tracking
- Resource monitoring
- See [monitoring/README.md](<./monitoring/README.md>)

### Quality Services (`quality/`)

Quality enforcement and tracking:

- Quality metrics
- Standards enforcement
- Compliance tracking
- See [quality/README.md](<./quality/README.md>)

### Pattern Services (`patterns/`)

Pattern detection and analysis:

- Code pattern recognition
- Anti-pattern detection
- Pattern libraries
- See [patterns/README.md](./patterns/README.md) (if exists)

## Configuration

Services use ACB Settings for configuration:

```python
from acb.depends import depends
from crackerjack.config import CrackerjackSettings

settings = depends.get(CrackerjackSettings)
```

Configuration files:

- `settings/crackerjack.yaml` — Base configuration
- `settings/local.yaml` — Local overrides (gitignored)

## Security Considerations

### Input Validation

All user input should be validated through `input_validator.py`:

```python
from crackerjack.services.input_validator import validate_and_sanitize_string

try:
    safe_input = validate_and_sanitize_string(user_input)
    # Use safe_input
except ExecutionError as e:
    # Handle validation failure
    pass
```

### Path Validation

Use `secure_path_utils.py` for all path operations:

```python
from crackerjack.services.secure_path_utils import SecurePathValidator

validated_path = SecurePathValidator.validate_file_path(
    user_path, base_directory=project_root
)
```

### Subprocess Security

Use `secure_subprocess.py` instead of direct subprocess calls:

```python
from crackerjack.services.secure_subprocess import SecureSubprocess

result = await SecureSubprocess.run_command(
    ["python", "-m", "pytest"], cwd=project_root
)
```

## Best Practices

1. **Use DI**: Always use dependency injection via `@depends.inject`
1. **Import Protocols**: Import from `models/protocols.py`, not concrete classes
1. **Validate Input**: Use input_validator for all external input
1. **Secure Paths**: Use SecurePathValidator for path operations
1. **Centralize Patterns**: Use regex_patterns.py instead of raw regex
1. **Handle Errors**: Use structured error handling with specific exceptions
1. **Log Security Events**: Use security_logger for security-relevant operations
1. **Cache Appropriately**: Use cache service for expensive operations
1. **Async When Needed**: Use async/await for I/O-bound operations
1. **Test Thoroughly**: Add tests for all new services

## Related

- [Adapters](<../adapters/README.md>) — Quality tool adapters that use services
- [Managers](<../managers/README.md>) — Managers that coordinate services
- [Orchestration](<../orchestration/README.md>) — Orchestration using services
- [Config](<../config/README.md>) — ACB Settings integration
- [SECURITY.md](<../../SECURITY.md>) — Security documentation

## Future Enhancements

- [ ] Standardize async/sync patterns across all services
- [ ] Add telemetry and observability
- [ ] Implement service health checks
- [ ] Add circuit breaker patterns for external services
- [ ] Create service benchmarking framework
- [ ] Develop service plugin system
