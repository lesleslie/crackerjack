# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-09-02

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-02

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-02

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-02

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-02

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-02

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-02

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-02

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.31.8] - 2025-09-01

### Fixed

- Critical bug in AI agent workflow where specific error details were not being captured from hook failures
- Fixed `HookExecutor` to properly capture subprocess output in `issues_found` field
- Fixed `AsyncWorkflowOrchestrator._collect_comprehensive_hook_issues_async()` to extract specific issues from `HookResult.issues_found`
- Fixed `_collect_test_issues_async()` to use `test_manager.get_test_failures()` for detailed error information
- Connected `_apply_ai_fixes_async()` to existing `AgentCoordinator` system for structured issue processing
- Added `_parse_issues_for_agents()` method to convert string issues to structured `Issue` objects
- Resolved pyright type errors in async workflow orchestrator

### Improved

- Enhanced AI agent error collection to provide specific details instead of generic messages
- Improved iterative fixing workflow to process all collected issues in batch rather than stopping on first failure
- Better integration between hook execution and AI agent fixing phases

## [0.31.7] - 2025-09-01

### Added

- Enhanced configuration management and dependency updates
- Improved core workflow orchestration patterns

### Fixed

- Configuration consistency across different execution modes
- Core dependency management improvements

## [0.31.6] - 2025-09-01

### Added

- Documentation updates for AI agent workflow rules
- Enhanced configuration management for modular architecture

### Fixed

- Core workflow improvements and configuration consistency
- Documentation accuracy for recent architectural changes

## [0.31.5] - 2025-09-01

### Added

- Comprehensive AI agent workflow documentation (AI-AGENT-RULES.md)
- Detailed iteration protocol specifications for AI agent fixing
- Sub-agent architecture documentation with 9 specialized agents
- Enhanced error collection and batch fixing patterns

### Fixed

- AI agent workflow iteration boundaries and fix application timing
- Progress validation between iterations
- WebSocket progress reporting for MCP server integration

## [0.31.4] - 2025-09-01

### Added

- Modular MCP server architecture (70% line reduction from 3,116 to 921 lines)
- WebSocket server refactoring (35% reduction from 1,479 to 944 lines)
- Enhanced filesystem operations with XDG compliance and atomic operations
- Plugin system architecture with dynamic loading and dependency resolution

### Fixed

- CLI entry point complexity reduction (80% reduction from 601 to 122 lines)
- Protocol-based dependency injection improvements
- Thread-safe session state management with async locks
- Service lifecycle management with enhanced container patterns

## [0.31.3] - 2025-09-01

### Added

- Enhanced container with service lifetime management (SINGLETON, TRANSIENT, SCOPED)
- Advanced filesystem operations with backup management and security validation
- Comprehensive health metrics and performance benchmarking
- Plugin-based hook system with custom validation rules

### Fixed

- Service descriptor with factory support and dependency resolution
- Thread-local scoping for singleton services
- Circular dependency detection in enhanced container
- Performance monitoring for file operations

## [0.31.0] - 2025-08-31

### Added

- Major architectural refactoring from monolithic to modular design
- Dependency injection container with protocol-based interfaces
- Advanced workflow orchestration with parallel execution strategies
- Session coordination with cleanup handlers and progress management
- Comprehensive manager pattern for hook, test, and publish operations

### Changed

- **BREAKING**: Migrated from monolithic `Crackerjack` class to modular `WorkflowOrchestrator`
- Restructured CLI interface with dedicated options and handlers modules
- Enhanced async/await patterns throughout the codebase
- Protocol-based interfaces in `models/protocols.py` for better testability

### Fixed

- All 31+ refurb violations in agents directory (FURB107, FURB109, FURB118, etc.)
- Major complexity reductions in critical functions (34→3, 33→2)
- Import error prevention with proper protocol usage
- Fast hooks consistency and reliability improvements

## [0.30.3] - 2025-08-29

### Added

- Coverage ratchet system targeting 100% test coverage
- Milestone celebration system for coverage achievements
- Progressive coverage improvement with no regression policy
- Enhanced test management with intelligent parallelization

### Changed

- Replaced arbitrary coverage limits with continuous improvement model
- Enhanced testing framework with timeout and worker configuration
- Rich terminal displays for coverage progress visualization

### Fixed

- Test execution reliability and performance optimization
- Coverage measurement accuracy and consistency
- Memory usage optimization for large test suites

## [0.30.2] - 2025-08-29

### Added

- AI agent integration with MCP (Model Context Protocol) server
- WebSocket-based progress streaming for real-time monitoring
- Comprehensive pre-commit hook management with fast/comprehensive stages
- Service watchdog for automatic MCP and WebSocket server monitoring

### Changed

- Enhanced CLI with AI agent mode and interactive Rich UI
- Improved error handling and structured output for AI agents
- Advanced workflow orchestration with session coordination

### Fixed

- MCP server stability and connection handling
- WebSocket progress reporting accuracy
- Pre-commit hook execution reliability and performance

______________________________________________________________________

## Historical Context

This changelog was reconstructed from git history on 2025-09-02. Prior to v0.30.2, Crackerjack underwent significant development including:

- Initial Python project management tool creation
- UV package manager integration
- Ruff, pytest, and pre-commit hook unification
- Basic quality enforcement workflow implementation
- Foundation for modular architecture patterns

For detailed commit history, use: `git log --oneline --since="2025-08-01"`

## Contributing

When updating this changelog:

1. Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format
1. Group changes under Added, Changed, Deprecated, Removed, Fixed, Security
1. Include version numbers and dates for all releases
1. Link to relevant issues and pull requests when applicable
1. Focus on user-facing changes rather than internal refactoring details

## Version Links

- \[0.31.8\]: Latest release with AI agent workflow fixes
- \[0.31.0\]: Major architectural refactoring to modular design
- \[0.30.3\]: Coverage ratchet system introduction
- \[0.30.2\]: AI agent and MCP server integration
