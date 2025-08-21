# Crackerjack Architecture

## Overview

Crackerjack has been refactored from a monolithic architecture into a modular, maintainable system following modern software engineering principles. This document outlines the new architecture and its benefits.

## Architectural Principles

- **Separation of Concerns**: Each module has a single, well-defined responsibility
- **Dependency Injection**: Services are injected rather than hard-coded, enabling easy testing and flexibility
- **Protocol-Based Design**: Interfaces define contracts between components
- **Modular Structure**: Small, focused modules instead of large monolithic files
- **Testability**: Architecture designed to support comprehensive unit and integration testing

## Directory Structure

```
crackerjack/
├── core/                   # Core orchestration and dependency injection
│   ├── __init__.py
│   ├── container.py        # Dependency injection container
│   ├── workflow_orchestrator.py  # Main workflow coordination (legacy facade)
│   ├── session_coordinator.py    # Session tracking and resource management
│   ├── phase_coordinator.py      # Individual workflow phase execution
│   └── performance.py      # Performance monitoring and benchmarks
├── managers/               # Domain-specific business logic managers
│   ├── __init__.py
│   ├── async_hook_manager.py  # Async hook execution
│   ├── hook_manager.py     # Pre-commit hook execution
│   ├── test_manager.py     # Test execution and coverage
│   └── publish_manager.py  # Version management and PyPI publishing
├── services/               # Infrastructure and external service abstractions
│   ├── __init__.py
│   ├── cache.py           # Caching service
│   ├── config.py          # Configuration management
│   ├── debug.py           # Debug logging service
│   ├── enhanced_filesystem.py  # Enhanced file operations
│   ├── file_hasher.py     # File hashing utilities
│   ├── filesystem.py      # File system operations with caching and batching
│   ├── git.py             # Git operations and commit logic
│   ├── initialization.py  # Project initialization service
│   ├── log_manager.py     # Log management with XDG standards
│   ├── logging.py         # Logging configuration
│   ├── metrics.py         # Performance metrics
│   ├── security.py        # Security operations and token handling
│   └── unified_config.py  # Unified configuration management
├── models/                 # Data models and interface definitions
│   ├── __init__.py
│   ├── protocols.py        # Interface definitions (protocols)
│   └── task.py            # Task tracking and session models
├── mcp/                   # Model Context Protocol integration
│   ├── __init__.py
│   ├── cache.py           # Error pattern caching
│   ├── client_runner.py   # MCP client runner
│   ├── context.py         # Context management
│   ├── file_monitor.py    # File monitoring
│   ├── progress_monitor.py # Progress monitoring
│   ├── rate_limiter.py    # Rate limiting
│   ├── server.py          # MCP server implementation
│   ├── service_watchdog.py # Service monitoring
│   ├── state.py           # Session state management
│   └── websocket_server.py # WebSocket server
├── agents/                # AI agent coordination (9 specialized agents)
│   ├── __init__.py
│   ├── base.py           # Base agent class and IssueType enum
│   ├── coordinator.py    # Agent coordinator with confidence scoring
│   ├── documentation_agent.py # Documentation consistency and changelog specialist
│   ├── dry_agent.py      # DRY violation detection and fixing
│   ├── formatting_agent.py # Formatting and style specialist
│   ├── import_optimization_agent.py # Import optimization specialist
│   ├── performance_agent.py # Performance optimization specialist
│   ├── refactoring_agent.py # Complexity reduction and dead code removal
│   ├── security_agent.py  # Security vulnerability specialist
│   ├── test_creation_agent.py # Test creation specialist
│   ├── test_specialist_agent.py # Advanced test specialist
│   └── tracker.py        # Agent tracking and metrics
├── executors/             # Hook execution strategies
│   ├── __init__.py
│   ├── async_hook_executor.py # Async execution
│   ├── cached_hook_executor.py # Cached execution
│   ├── hook_executor.py   # Standard execution
│   └── individual_hook_executor.py # Individual execution
├── config/                # Configuration management
│   ├── __init__.py
│   └── hooks.py          # Hook definitions
├── plugins/               # Plugin system
│   ├── __init__.py
│   ├── base.py           # Base plugin class
│   ├── hooks.py          # Hook plugins
│   ├── loader.py         # Plugin loader
│   └── managers.py       # Plugin managers
├── cli/                   # CLI-specific presentation logic
│   ├── __init__.py
│   ├── facade.py         # CLI facade
│   └── interactive.py    # Interactive CLI
├── code_cleaner.py        # Code cleaning functionality
├── dynamic_config.py      # Configuration generation
├── errors.py              # Error definitions
├── interactive.py         # Interactive CLI
├── py313.py              # Python 3.13 features
└── __main__.py           # CLI entry point
```

## Component Responsibilities

### Core Layer

**`core/container.py`**

- Dependency injection container
- Service registration and resolution
- Configuration of default implementations

**`core/workflow_orchestrator.py`**

- Legacy facade maintaining backward compatibility
- Delegates to new coordinator pattern
- Provides same public API as original monolithic class
- Reduced from 823 lines to 141 lines (83% reduction)

**`core/session_coordinator.py`**

- Session tracking and progress reporting
- Resource cleanup and lifecycle management
- Debug logging with automatic cleanup
- Thread pool and lock file management

**`core/phase_coordinator.py`**

- Individual workflow phase execution
- Coordinates between session and domain managers
- Handles configuration, cleaning, hooks, testing, publishing, and commit phases
- Single responsibility for phase orchestration

### Managers Layer

**`managers/hook_manager.py`**

- Executes pre-commit hooks (fast and comprehensive)
- Parses hook output and tracks results
- Handles hook installation and updates
- Provides hook execution summaries

**`managers/test_manager.py`**

- Runs pytest with optimal configuration
- Manages parallel test execution
- Handles coverage reporting and benchmarks
- Validates test environment

**`managers/publish_manager.py`**

- Handles version bumping (semantic versioning)
- Manages PyPI authentication and publishing
- Creates git tags and handles releases
- Validates package information

### Services Layer

**`services/filesystem.py`**

- Abstracts file system operations with comprehensive error handling
- Provides consistent interface for file I/O with proper exception types
- Handles path manipulation and file operations with security validation
- Caching and batching for performance optimization

**`services/git.py`**

- Git repository operations with enhanced error handling
- Intelligent commit message generation
- Change detection and staging with proper validation
- Branch and remote operations

**`services/config.py`**

- Configuration management for pyproject.toml and pre-commit
- Template generation and validation
- Dynamic configuration updates

**`services/security.py`**

- Token masking and secure file creation
- Security validation for file operations
- Secure subprocess execution patterns

### Models Layer

**`models/protocols.py`**

- Defines interfaces for all major components
- Enables dependency injection and testing
- Ensures consistent contracts between layers

**`models/task.py`**

- Task and session tracking models
- Progress reporting and state management
- Hook result definitions

### AI Agent Layer

**`agents/base.py`**

- Base SubAgent class with common interface
- IssueType enum defining all supported issue categories
- AgentRegistry for dynamic agent discovery and loading
- FixResult data structures for agent response coordination

**`agents/coordinator.py`**

- AgentCoordinator routes issues to appropriate agents based on confidence scoring
- Single-agent mode (≥0.7 confidence) vs collaborative mode
- Batch processing for efficient issue resolution
- Agent performance tracking and optimization

**`agents/[specific]_agent.py`**

- 9 specialized agents with domain-specific expertise:
  - **DocumentationAgent**: Documentation consistency and changelog management
  - **PerformanceAgent**: AST-based performance optimization (list concatenation, string building, nested loops)
  - **RefactoringAgent**: Complexity reduction and dead code removal
  - **DRYAgent**: Don't Repeat Yourself violation detection and fixing
  - **SecurityAgent**: Security vulnerability detection and remediation
  - **ImportOptimizationAgent**: Import statement optimization and cleanup
  - **FormattingAgent**: Code style and formatting fixes
  - **TestCreationAgent**: Test failure resolution and coverage improvement
  - **TestSpecialistAgent**: Advanced testing scenario management

**Agent Capabilities:**

- **Real Code Transformation**: Agents modify source code, not just provide recommendations
- **AST-based Analysis**: Advanced pattern detection using Python's Abstract Syntax Tree
- **Confidence Scoring**: Each agent provides confidence ratings for issue handling
- **Iterative Improvement**: Agents work in coordination until all issues are resolved

### MCP Layer

**`mcp/server.py`**

- Model Context Protocol server implementation
- AI agent integration tools and commands
- Workflow automation for AI assistants

**`mcp/state.py`**

- Session state management for MCP operations
- Issue tracking and prioritization
- Checkpoint and resume functionality

**`mcp/cache.py`**

- Error pattern caching for efficient AI interactions
- Fix result tracking and success rate analysis
- Pattern recognition and auto-fix suggestions

## Data Flow - Coordinator Pattern

```
CLI Entry Point (__main__.py)
    ↓
WorkflowOrchestrator (Legacy Facade)
    ↓
WorkflowPipeline
    ↓
┌──────────────────┬──────────────────┐
│ SessionCoordinator│ PhaseCoordinator │
│ • Session tracking│ • Phase execution│
│ • Resource cleanup│ • Error handling │
│ • Progress logging│ • Manager coord  │
└──────────────────┴──────────────────┘
    ↓
┌─────────────────┬─────────────────┬─────────────────┐
│   Hook Manager  │  Test Manager   │ Publish Manager │
└─────────────────┴─────────────────┴─────────────────┘
    ↓
┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Filesystem Svc  │   Git Service   │ Config Service  │ Security Service│
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘
```

## Key Improvements Over Previous Architecture

### From Monolithic to Coordinator Pattern

**Before (Original Monolith):**

- Single 4,781-line file with 282 functions
- Mixed responsibilities (business logic + presentation)
- Tight coupling to console and external tools
- Difficult to test and maintain

**After (First Refactor):**

- Multiple focused modules (core orchestrator ~800 lines, others \<500 lines)
- Clear separation of concerns
- Dependency injection for loose coupling

**After (Coordinator Pattern - Current):**

- **WorkflowOrchestrator**: 823 → 141 lines (83% reduction)
- **SessionCoordinator**: 196 lines - dedicated session management
- **PhaseCoordinator**: 398 lines - dedicated phase execution
- **Total complexity reduction**: Single responsibility per coordinator
- **Enhanced testability**: 22 new integration tests added

### Dependency Management

**Before:**

```python
# Hard-coded dependencies
self.console.print("Starting...")
result = subprocess.run(["git", "status"])
```

**After (Coordinator Pattern):**

```python
# Coordinator pattern with injected dependencies
class PhaseCoordinator:
    def __init__(
        self,
        session: SessionCoordinator,
        filesystem: FileSystemInterface,
        git_service: GitInterface,
    ):
        self.session = session
        self.filesystem = filesystem
        self.git_service = git_service


# Pipeline orchestration
class WorkflowPipeline:
    def __init__(self, session: SessionCoordinator, phases: PhaseCoordinator):
        self.session = session
        self.phases = phases
```

### Testability Improvements

**Before:**

- Difficult to mock external dependencies
- Console output mixed with business logic
- Large integration tests only

**After:**

- Protocol-based interfaces enable easy mocking
- Business logic separated from presentation
- Unit tests for individual components
- Integration tests for workflow coordination

## Coordinator Pattern Architecture

The current architecture implements the **Coordinator Pattern**, which provides several key advantages:

### Core Principles

1. **Single Responsibility**: Each coordinator has one focused responsibility
1. **Collaboration over Inheritance**: Coordinators work together through composition
1. **Dependency Injection**: All dependencies are injected, enabling easy testing
1. **Resource Management**: Centralized resource cleanup and lifecycle management

### Coordinator Responsibilities

- **SessionCoordinator**: Manages session state, logging, and resource cleanup
- **PhaseCoordinator**: Orchestrates individual workflow phases
- **WorkflowPipeline**: High-level workflow orchestration using coordinators

### Benefits of Coordinator Pattern

1. **Reduced Complexity**: 83% reduction in main orchestrator code (823→141 lines)
1. **Enhanced Testability**: 22 new integration tests validate coordinator interactions
1. **Better Error Handling**: Centralized error handling with proper recovery patterns
1. **Resource Safety**: Automatic cleanup of threads, locks, and temporary files
1. **Security Hardening**: Command validation and injection prevention

## Benefits of New Architecture

1. **Maintainability**: Small, focused coordinators are easier to understand and modify
1. **Testability**: Coordinator pattern enables comprehensive unit and integration testing
1. **Extensibility**: New coordinators can be added without modifying existing code
1. **Performance**: Better separation allows for optimization of individual coordinators
1. **Reliability**: Smaller, well-tested coordinators reduce bug surface area
1. **Security**: Enhanced security validation and resource management
1. **Resource Management**: Proper cleanup of system resources and temporary files

## Migration Strategy

The refactoring maintains backward compatibility:

- All existing CLI commands and options work unchanged
- Same public API surface
- Identical configuration files
- Gradual migration of legacy components

## Legacy Components

Some components remain from the original architecture:

- `code_cleaner.py`: Code cleaning logic (stable, integrated)
- `dynamic_config.py`: Configuration generation (stable, integrated with services)
- `interactive.py`: Interactive CLI (stable, delegated by main workflow)

All components have been successfully integrated while maintaining functionality.

## Testing Strategy

- **Unit Tests**: Each manager and service has comprehensive unit tests
- **Integration Tests**: Workflow orchestrator integration testing
- **MCP Tests**: MCP server and AI integration testing
- **End-to-End Tests**: Complete CLI workflow testing

## Performance Considerations

- **Lazy Loading**: Services are created only when needed
- **Caching**: Filesystem and git operations cache results
- **Parallel Execution**: Test and hook execution optimized for parallelism
- **Memory Efficiency**: Smaller objects with focused responsibilities

## Recent Improvements (Current Release)

### Security Hardening

- **Command Validation**: All external commands validated against allowlist
- **Injection Prevention**: Shell injection and path traversal protection
- **Resource Cleanup**: Comprehensive cleanup of file locks and threads
- **Safe Subprocess**: No shell=True usage, proper error handling

### Performance Optimizations

- **Code Deduplication**: 60% reduction in duplicate logic
- **Lazy Loading**: Services created only when needed
- **Memory Efficiency**: Proper resource management and cleanup

## Future Enhancements

1. **Plugin Architecture**: Enable third-party extensions
1. **Configuration System**: Centralized configuration management
1. **Event System**: Pub/sub for workflow events
1. **Metrics Collection**: Performance and usage analytics
1. **CLI Modernization**: Continue modernizing remaining components

This architecture provides a solid foundation for future development while maintaining the reliability and functionality that crackerjack users expect.
