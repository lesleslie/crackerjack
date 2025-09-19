# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.38.11] - 2025-09-19

### Changed

- Crackerjack (quality: 76/100) - 2025-09-18 18:57:37
- Crackerjack (quality: 76/100) - 2025-09-19 01:12:30

### Fixed

- Fix pre-commit hook issues and type checking errors

### Testing

- crackerjack: Update CHANGELOG, test_command_builder, pyproject

## [0.38.10] - 2025-09-18

### Documentation

- config: Update CHANGELOG, pyproject, uv

## [0.38.9] - 2025-09-18

### Documentation

- config: Update CHANGELOG, pyproject, uv

## [0.38.8] - 2025-09-18

### Documentation

- config: Update CHANGELOG, pyproject

## [0.38.7] - 2025-09-18

### Changed

- Crackerjack (quality: 76/100) - 2025-09-18 16:54:43

### Testing

- crackerjack: Update 4 files

## [0.38.6] - 2025-09-18

### Documentation

- crackerjack: Update 4 files

## [0.38.5] - 2025-09-18

### Documentation

- config: Update CHANGELOG, pyproject

## [0.38.4] - 2025-09-18

### Changed

- Crackerjack (quality: 76/100) - 2025-09-18 06:24:19

### Fixed

- test: Update 8 files

## [0.38.3] - 2025-09-18

### Testing

- test: Update 6 files

## [0.38.2] - 2025-09-18

### Documentation

- config: Update 4 files

## [0.38.1] - 2025-09-18

### Changed

- Crackerjack (quality: 76/100) - 2025-09-18 03:07:52

### Fixed

- crackerjack: Update 8 files

## [0.38.0] - 2025-09-17

### Changed

- Crackerjack (quality: 76/100) - 2025-09-17 08:15:08

### Testing

- test: Update 32 files

## [0.37.9] - 2025-09-16

### Documentation

- core: Update 5 files

## [0.37.8] - 2025-09-16

### Documentation

- config: Update CHANGELOG, pyproject

## [0.37.7] - 2025-09-16

### Documentation

- config: Update CHANGELOG, pyproject

## [0.37.6] - 2025-09-16

### Changed

- Crackerjack (quality: 76/100) - 2025-09-16 03:47:48

## [0.37.5] - 2025-09-16

### Changed

- Crackerjack (quality: 76/100) - 2025-09-16 03:31:03

### Documentation

- crackerjack: Update 4 files

## [0.37.4] - 2025-09-16

### Documentation

- crackerjack: Update CHANGELOG, options, pyproject

## [0.37.3] - 2025-09-16

### Testing

- crackerjack: Update 6 files

## [0.37.0] - 2025-09-15

### Testing

- Update CHANGELOG, WORKFLOW_VALIDATION_TEST, pyproject

## [0.36.2] - 2025-09-15

### Changed

- Crackerjack (quality: 76/100) - 2025-09-15 23:04:41

### Fixed

- test: Update 5 files

## [0.36.1] - 2025-09-15

### Documentation

- config: Update CHANGELOG, pyproject

## [0.36.0] - 2025-09-15

### Added

- release: Publish version 0.35.2

### Changed

- Crackerjack (quality: 76/100) - 2025-09-15 22:55:16

### Internal

- No changes to commit

## [0.35.2] - 2025-09-15

### Documentation

- core: Update 6 files

### Internal

- No changes to commit

## [0.35.1] - 2025-09-15

### Changed

- Crackerjack (quality: 76/100) - 2025-09-15 22:25:11

### Fixed

- Fixed commit/push stage being skipped when using -s -p -c flags together

## [0.35.0] - 2025-09-15

### Fixed

- cli: Add 'auto' option to BumpOption enum and fix URL formatting

### Documentation

- config: Update CHANGELOG, CLAUDE, pyproject

## [0.34.2] - 2025-09-15

### Fixed

- security: Suppress verbose logging and fix commit validation error (parentheses allowed)

## [0.34.0] - 2025-09-15

### Changed

- Update config, deps, docs

## [0.33.12] - 2025-09-15

### Changed

- Update config, deps, docs

## [0.33.11] - 2025-09-15

### Changed

- Update config, deps, docs

## [0.33.10] - 2025-09-15

### Changed

- Update config, core, deps, docs

## [0.33.9] - 2025-09-15

### Changed

- Update config, deps, docs

## [0.33.8] - 2025-09-14

### Changed

- Update config, deps, docs

## [0.33.7] - 2025-09-14

### Changed

- Update config, core, deps, docs

## [0.33.6] - 2025-09-14

### Changed

- Update config, core, deps, docs

## [0.33.5] - 2025-09-14

### Changed

- Update config, core, deps, docs

## [0.33.4] - 2025-09-14

### Changed

- Update config, deps, docs

## [0.33.3] - 2025-09-14

### Changed

- Update config, core, deps, docs

## [0.33.2] - 2025-09-14

### Added

- Fix regex validation and remove conflicting pre-commit git hook

## [0.33.1] - 2025-09-14

### Added

- Complete Phase 4 Advanced Features implementation
- Complete Phase 4 enterprise features and fix hook system
- Fix SQL syntax errors, refactor complexity violations, improve type annotations

### Changed

- Crackerjack (quality: 80/100) - 2025-09-07 16:59:59
- Crackerjack (quality: 80/100) - 2025-09-09 14:44:05
- Crackerjack (quality: 80/100) - 2025-09-09 18:14:20
- Fix complexity violations and regex validation
- Post-release updates
- Update configuration

## [0.31.9] - 2025-01-09

### Added

- Enterprise-grade regex pattern management system with centralized ValidatedPattern class
- Thread-safe CompiledPatternCache for performance optimization
- 18+ validated regex patterns for security, formatting, and version management
- Pre-commit hook validation to prevent bad regex patterns in codebase
- Enhanced SecurityAgent with 1.0 confidence scoring for critical security issues
- Improved RefactoringAgent with 0.9 confidence scoring for code transformations
- Better DocumentationAgent coordination with 0.8 confidence scoring
- Agent batch processing for comprehensive issue fixing
- Quick Reference section in CLAUDE.md for common commands
- Enhanced Agent Selection Guide with confidence scoring and decision tree
- Improved Common Issues & Solutions troubleshooting documentation

### Changed

- Updated GitLab MCP server: 2.0.3 → 2.0.4 for improved integration capabilities
- Updated MotherDuck MCP server: 0.3.1 → 0.6.3 for enhanced database operations
- Optimized CLAUDE.md documentation from 57KB to 18KB (68% reduction)
- Enhanced MCP server integration with better error handling and performance

### Fixed

- Critical security vulnerabilities in character class spacing for token masking patterns
- PyPI and GitHub token masking vulnerabilities in security.py
- Migrated all TOKEN_PATTERNS to ValidatedPattern system for consistency
- Added word boundary protection against false positives in token detection
- Fixed regex replacement patterns that caused spacing issues and security risks
- Improved specialized agent architecture for better issue classification and resolution

### Security

- Fixed token masking patterns to prevent false positives and information disclosure
- Enhanced validation of regex replacement patterns to prevent injection vulnerabilities
- Added comprehensive testing for all security-related regex patterns
- Improved protection against token exposure in logs and error messages

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

- \[0.31.9\]: Latest release with enterprise-grade regex pattern management and security fixes
- \[0.31.8\]: AI agent workflow fixes and error collection improvements
- \[0.31.0\]: Major architectural refactoring to modular design
- \[0.30.3\]: Coverage ratchet system introduction
- \[0.30.2\]: AI agent and MCP server integration
