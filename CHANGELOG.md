______________________________________________________________________

## [0.46.2] - 2025-12-19

### Changed

- Update dependencies

## [0.46.1] - 2025-12-19

### Changed

- Update config, core, deps, docs

## [0.46.0] - 2025-12-11

### Changed

- Update config, core, deps, docs

## [0.45.2] - 2025-12-09

### Changed

- Update config, deps

## [0.45.1] - 2025-12-09

### Changed

- Update config, core, deps

## [0.45.0] - 2025-12-09

### Changed

- Update config, core, deps, docs

## [0.44.44] - 2025-12-09

### Changed

- Update config, core, deps, docs, tests

## [0.44.43] - 2025-12-03

### Changed

- Update config, core, deps, docs, tests

## [0.44.42] - 2025-11-27

### Changed

- Update core, deps

## [0.44.41] - 2025-11-27

### Changed

- Update config, core, deps

## [0.44.40] - 2025-11-27

### Changed

- Update config, core, deps

## [0.44.39] - 2025-11-27

### Changed

- Update config, deps

## [0.44.38] - 2025-11-27

### Changed

- Update config, core, deps

## [0.44.37] - 2025-11-27

### Changed

- Update config, core, deps

## [0.44.36] - 2025-11-26

### Changed

- Update core, deps

## [0.44.35] - 2025-11-26

### Changed

- Crackerjack (quality: 72/100) - 2025-11-26 07:09:38
- Update documentation

## [0.44.34] - 2025-11-26

### Changed

- Update dependencies

## [0.44.33] - 2025-11-26

### Changed

- Update core, deps

## [0.44.32] - 2025-11-25

### Changed

- cleanup
- Update core, deps
- Update deps, docs, tests

## [0.44.31] - 2025-11-25

### Changed

- Update config, core, deps, docs, tests
- Update deps, docs, tests

## [0.44.29] - 2025-11-19

### Changed

- Crackerjack (quality: 67/100) - 2025-11-17 02:09:39
- Crackerjack (quality: 67/100) - 2025-11-18 10:45:28
- Crackerjack (quality: 67/100) - 2025-11-18 10:47:06
- Crackerjack (quality: 67/100) - 2025-11-19 13:45:14
- Update config, core, deps, docs, tests
- Update config, core, docs, tests

### Documentation

- Add comprehensive README.md audit report
- Complete comprehensive README audit fixes (batch 2 + 3)
- Expand critical README files (batch 1)

## [0.44.28] - 2025-11-16

### Changed

- Update core, deps, docs

## [0.44.27] - 2025-11-16

### Changed

- Update core, deps, docs

## [0.44.26] - 2025-11-16

### Changed

- Update core, deps, docs, tests

## [0.44.25] - 2025-11-16

### Changed

- Update config, core, deps, docs, tests

## [0.44.24] - 2025-11-16

### Changed

- Update config, deps

### Documentation

- Clean up documentation structure

## [0.44.23] - 2025-11-16

### Changed

- Update core, deps

## [0.44.22] - 2025-11-16

### Changed

- Fix markdown link formatting across documentation
- Simplify configuration and improve quality
- Update core, deps, docs

### Fixed

- hooks: Remove hardcoded package name from complexipy parser
- Windows compatibility, semgrep error categorization, docs

### Documentation

- Add comprehensive configuration consolidation audit
- Add comprehensive hooks and tools audit report
- Add comprehensive tempfile coverage output analysis
- Add comprehensive tempfile JSON output analysis
- Add cross-project configuration consolidation audit
- Add unified implementation plan from 3 audits
- Update audit documents with implementation status

## [0.44.21] - 2025-11-16

### Fixed

- **CRITICAL:** Remove hardcoded "crackerjack" package name from complexipy parser
  - Added auto-detection of package name from tool output using regex
  - Fixes 100% of external projects where complexity violations were silently ignored
  - Falls back to pyproject.toml detection if regex fails
- Fix Windows path separator compatibility in PATH environment variable handling
  - Replace hardcoded `": "` with `os.pathsep` for cross-platform support
- Categorize semgrep errors to distinguish code vs infrastructure issues
  - Network/timeout errors now warn instead of failing builds
  - Only code/config errors fail the build
  - Improves CI/CD resilience to transient network issues

### Changed

- Simplify configuration in pyproject.toml
  - Remove 3 redundant `[[tool.refurb.amend]]` blocks (18 lines)
  - Remove redundant test worker settings: `auto_detect_workers`, `min_workers`
  - Enable branch coverage for more accurate metrics (`branch = true`)
- Document zuban v0.2.2 limitation with `[tool.mypy]` parsing
  - Keep mypy.ini with clear explanation why it's needed
  - Add migration path for when zuban is fixed
- Improve zuban `--no-error-summary` flag documentation
  - Document rationale: suppresses summary line to keep issue output clean

### Audit & Documentation

- Comprehensive audit of hooks and tools for false/faulty error reporting
- Cross-project configuration consolidation analysis (6 projects)
- Unified implementation plan consolidating 3 audit documents (17 tasks)
- Updated IMPLEMENTATION_SUMMARY.md with detailed Phase 1-4 completion

______________________________________________________________________

## [0.44.20] - 2025-11-15

### Changed

- Update config, deps

## [0.44.19] - 2025-11-15

### Changed

- Update config, core, deps

## [0.44.18] - 2025-11-15

### Changed

- Update config, core, deps

## [0.44.17] - 2025-11-15

### Changed

- Update core, deps

## [0.44.16] - 2025-11-14

### Changed

- Update core, deps

## [0.44.15] - 2025-11-14

### Added

- Enhance semgrep JSON parsing to extract errors from errors array
- Fix orchestration layer to properly extract semgrep JSON errors

### Changed

- Add diagnostic logging for hooks showing FAILED with 0 issues
- Expand diagnostic logging to all hooks with failures
- Update core, docs, tests

### Fixed

- Correct hook issue counting for failed hooks with zero detected issues
- Ensure adapter-based hooks show errors when failing with 0 parsed issues

### Internal

- Remove debug logging from hook executors

## [0.44.14] - 2025-11-14

### Changed

- Update core, deps, docs

### Fixed

- Correct hook issue counting and dynamic package detection

### Documentation

- Add comprehensive documentation audit report
- Complete medium/low priority audit fixes and update report
- Expand minimal package READMEs (high priority issue #3)
- Resolve critical coverage inconsistencies and update audit report

## [0.44.13] - 2025-11-14

### Changed

- Update core, deps

### Fixed

- Add error_message fields to all async hook error paths
- Show 0 issues for passed hooks instead of file count

## [0.44.12] - 2025-11-14

### Changed

- Update dependencies

### Fixed

- Normalize package names and capture hook errors correctly
- orchestration: Capture stdout+stderr for failed hook error messages

## [0.44.11] - 2025-11-14

### Changed

- cli: Extract command handlers from __main__.py into 7 focused modules
- cli: Update __main__.py to use extracted handler modules (1,520 → 517 lines)
- Consolidate quality and performance services - delete deprecated duplicates
- Extract performance and refactoring agent helpers
- Extract test_creation_agent helpers into focused modules
- Extract workflow_orchestrator.py into 5 focused modules
- Remove backup and duplicate files (Phase 1)
- Split monitoring_endpoints.py into organized modules
- Split regex_patterns.py into organized domain modules
- Update agents to delegate to helper modules
- Update core, deps, docs, tests

### Documentation

- Add comprehensive final project summary
- Add comprehensive package refactoring plan
- Update REFACTORING_PLAN.md - ALL PHASES COMPLETE
- Update REFACTORING_PLAN.md - Future Enhancements complete
- Update REFACTORING_PLAN.md - Phase 2 100% complete
- Update REFACTORING_PLAN.md - Phase 4 and Phase 5 COMPLETE
- Update REFACTORING_PLAN.md with Phase 2 progress

### Internal

- Remove backup files from refactoring (monitoring_endpoints_old.py, regex_patterns_old.py)

## [0.44.10] - 2025-11-14

### Changed

- refactoring
- Simplify conditional expression in issue count calculation
- Update core, docs, tests

### Fixed

- Capture error output for failed hooks with no parsed issues
- Make mdformat wrapper fail when it formats files
- Show accurate issue counts in hook results table
- Use project directory name instead of hardcoded 'crackerjack' fallback

### Documentation

- Add comprehensive test improvement plan

### Testing

- Add comprehensive ArchitectAgent and TestCreationAgent tests
- Add comprehensive AsyncTimeoutManager tests
- Add comprehensive AutofixCoordinator tests
- Add comprehensive CLI layer tests (Phase 5 - Part 2)
- Add comprehensive DRYAgent and FormattingAgent tests
- Add comprehensive EnhancedProactiveAgent and SemanticAgent tests
- Add comprehensive file_lifecycle tests
- Add comprehensive HookManager and PublishManager tests
- Add comprehensive MCP rate_limiter tests
- Add comprehensive MCP state tests
- Add comprehensive orchestration tests (Phase 5 - Part 1)
- Add comprehensive parallel_executor tests
- Add comprehensive PerformanceAgent and DocumentationAgent tests
- Add comprehensive RefactoringAgent and SecurityAgent tests
- Add comprehensive resource_manager tests
- Add comprehensive SessionCoordinator tests
- Add Phase 2 core service tests (filesystem and cache)
- Complete Phase 4 with TestSpecialistAgent and ImportOptimizationAgent tests
- Implement Phase 1 test improvements
- Implement Phase 3 agent system tests (base and coordinator)
- Implement Phase 4 manager tests and remove broken smoke tests

## [0.44.9] - 2025-11-14

### Changed

- Update deps, docs

### Fixed

- Remove hardcoded 'crackerjack' path assumptions

## [0.44.8] - 2025-11-14

### Changed

- Crackerjack (quality: 62/100) - 2025-11-13 00:52:36
- Update core, docs, tests

## [0.44.7] - 2025-11-12

### Changed

- Crackerjack (quality: 62/100) - 2025-11-11 19:56:38
- Crackerjack (quality: 62/100) - 2025-11-12 03:59:00
- Crackerjack (quality: 70/100) - 2025-11-09 08:58:12
- Crackerjack (quality: 70/100) - 2025-11-09 09:27:02

## [Unreleased] - 2025-11-09

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-09

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-09

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-09

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.44.6] - 2025-11-08

### Changed

- Update core, deps, tests

## [0.44.5] - 2025-11-08

### Changed

- Update dependencies

## [0.44.4] - 2025-11-08

### Changed

- Update core, deps, docs, tests

## [0.44.3] - 2025-11-08

### Changed

- Update core, deps
- Update documentation

## [0.44.1] - 2025-11-08

### Changed

- Update dependencies

## [0.43.0] - 2025-11-08

### Changed

- Crackerjack (quality: 67/100) - 2025-11-08 08:54:48
- Update core, docs

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.42.5] - 2025-11-08

### Added

- Add mdformat + mdformat-ruff hook with gitignore support

### Changed

- Crackerjack (quality: 64/100) - 2025-11-07 22:10:47
- Crackerjack (quality: 64/100) - 2025-11-07 22:33:22
- Crackerjack (quality: 66/100) - 2025-11-07 15:23:54
- Crackerjack (quality: 66/100) - 2025-11-08 00:37:58
- Crackerjack (quality: 67/100) - 2025-11-07 12:34:59
- Crackerjack (quality: 67/100) - 2025-11-07 17:08:15
- Crackerjack (quality: 67/100) - 2025-11-07 17:27:37
- Crackerjack (quality: 67/100) - 2025-11-07 17:42:52
- Crackerjack (quality: 67/100) - 2025-11-07 18:04:40
- Crackerjack (quality: 67/100) - 2025-11-07 21:24:32
- Update core, deps, docs

### Fixed

- Mdformat timeout and enable auto-fix

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.42.4] - 2025-11-07

### Changed

- Crackerjack (quality: 67/100) - 2025-11-07 10:50:56
- Update core, docs

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.42.3] - 2025-11-07

### Changed

- Update config, core, deps, docs

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.42.2] - 2025-11-07

### Changed

- Crackerjack (quality: 66/100) - 2025-11-07 08:50:31
- Crackerjack (quality: 70/100) - 2025-11-07 07:58:38
- Update core, docs

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.42.1] - 2025-11-07

### Changed

- Crackerjack (quality: 67/100) - 2025-11-07 06:55:13
- Raise large file limit to 1MB for comprehensive frameworks
- Update config, docs

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-07

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.42.0] - 2025-11-06

### Added

- **BREAKING:** di: Migrate WorkflowOrchestrator to ACB dependency injection
- Complete ACB cache migration - remove old cache.py
- Implement centralized error handling decorators
- workflows: Complete Level 3.5 and HookManager registration
- workflows: Complete Level 4 + 4.5 manager registration
- workflows: Phase 2 Week 1 Day 2 - DI container Level 1-3 complete

### Changed

- **BREAKING:** Complete Phase 3 ACB DI migration and remove enhanced_container
- Apply linter formatting to core_tools and acb_cache_adapter
- Complete ACB DI migration for core orchestration
- Crackerjack (quality: 65/100) - 2025-10-11 06:02:33
- Crackerjack (quality: 65/100) - 2025-10-25 21:39:23
- Crackerjack (quality: 65/100) - 2025-10-26 02:51:53
- Crackerjack (quality: 66/100) - 2025-10-26 03:00:45
- Crackerjack (quality: 66/100) - 2025-10-26 21:26:50
- Crackerjack (quality: 66/100) - 2025-10-30 05:32:02
- Crackerjack (quality: 66/100) - 2025-10-30 06:32:33
- Crackerjack (quality: 66/100) - 2025-10-30 07:50:43
- Crackerjack (quality: 66/100) - 2025-10-30 08:14:33
- Crackerjack (quality: 67/100) - 2025-10-10 15:01:16
- Crackerjack (quality: 67/100) - 2025-10-26 10:23:34
- Crackerjack (quality: 67/100) - 2025-10-26 11:20:52
- Crackerjack (quality: 67/100) - 2025-11-05 12:00:24
- Crackerjack (quality: 67/100) - 2025-11-05 13:22:56
- Crackerjack (quality: 67/100) - 2025-11-05 17:05:04
- Crackerjack (quality: 67/100) - 2025-11-05 19:24:17
- Crackerjack (quality: 67/100) - 2025-11-05 20:17:36
- Crackerjack (quality: 67/100) - 2025-11-05 23:00:13
- Crackerjack (quality: 69/100) - 2025-10-09 06:18:13
- Crackerjack (quality: 69/100) - 2025-10-09 09:08:14
- Crackerjack (quality: 69/100) - 2025-10-09 09:28:02
- Crackerjack (quality: 69/100) - 2025-10-09 09:46:06
- Crackerjack (quality: 69/100) - 2025-10-09 10:13:58
- Crackerjack (quality: 69/100) - 2025-10-09 11:29:53
- Crackerjack (quality: 69/100) - 2025-10-09 12:36:05
- Crackerjack (quality: 69/100) - 2025-10-09 14:20:24
- Crackerjack (quality: 69/100) - 2025-10-09 14:49:40
- Crackerjack (quality: 69/100) - 2025-10-09 16:08:54
- Crackerjack (quality: 69/100) - 2025-10-09 17:32:36
- Crackerjack (quality: 69/100) - 2025-10-09 17:51:59
- Crackerjack (quality: 69/100) - 2025-10-09 19:26:25
- Crackerjack (quality: 69/100) - 2025-10-09 20:02:52
- Crackerjack (quality: 69/100) - 2025-10-09 21:07:41
- Crackerjack (quality: 69/100) - 2025-10-09 21:35:52
- Crackerjack (quality: 69/100) - 2025-10-09 22:35:31
- Crackerjack (quality: 69/100) - 2025-10-09 23:56:18
- Crackerjack (quality: 70/100) - 2025-10-26 18:26:51
- Crackerjack (quality: 71/100) - 2025-10-10 17:44:57
- Crackerjack (quality: 71/100) - 2025-10-10 21:41:43
- Crackerjack (quality: 71/100) - 2025-10-15 02:20:41
- Crackerjack (quality: 71/100) - 2025-10-15 22:32:09
- Crackerjack (quality: 71/100) - 2025-10-16 15:57:30
- Crackerjack (quality: 71/100) - 2025-10-17 23:10:50
- Update core, docs
- Update documentation

### Fixed

- agents: Implement lazy imports to avoid loading heavy ML dependencies
- hook-manager: Implement config loading priority system
- hook-manager: Use instance properties in get_execution_info()
- phase3: Complete ACB DI test fixes - config priority, orchestrator settings, parallelism
- Resolve event loop conflicts in ACB cache adapter
- Resolve hook failures and reduce decorator complexity
- Resolve test failures found during ACB DI migration
- tests: Update 4 files

### Documentation

- Add comprehensive improvement roadmap
- architecture: Create WorkflowOrchestrator decomposition strategy
- Streamline CLAUDE.md with improved architecture focus
- Update architecture docs to reflect facade removal
- Update improvement plan with Phase 3.1 completion

### Testing

- Add cache isolation fixture for regex pattern tests
- Fix 6 failing Phase 3 service tests
- Update tests for ACB DI migration

### Internal

- Remove obsolete backup files and unused enhanced versions
- Remove remaining facade files to complete Phase 3 goals

## [Unreleased] - 2025-11-06

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Added

- feat(workflows): complete ACB workflow migration with commit and publish support
  - Added `run_commit_phase` action handler for git commit/push functionality
  - Added `run_publish_phase` action handler for version bump and PyPI publishing
  - Created `COMMIT_WORKFLOW` definition (quality checks + commit)
  - Created `PUBLISH_WORKFLOW` definition (tests + quality checks + commit + publish)
  - Updated `select_workflow_for_options()` to route `-c`, `-t`, `-p` flags correctly
  - Registered new actions in `ACTION_REGISTRY` for automatic discovery
  - ACB workflow engine now feature-complete with legacy orchestrator parity

### Fixed

- fix(workflows): commit and publish stages now execute with ACB workflow engine
  - Resolves issue where `-c -t -p patch` flags were ignored in Phase 4.2
  - Eliminates need for `--use-legacy-orchestrator` flag for commit/publish workflows

## [Unreleased] - 2025-11-05

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-11-05

### Changed

- **BREAKING**: ACB workflows are now the default execution path (Phase 4.2 complete)
  - Use `--use-legacy-orchestrator` to opt out and use the legacy orchestrator
  - Removed opt-in `--use-acb-workflows` requirement (ACB is now default)
  - Real-time console output streaming during workflow execution
  - Non-blocking async execution with `asyncio.to_thread()` pattern

### Added

- Added `--use-legacy-orchestrator` flag for opting out of ACB workflows
- Added `/--no-use-legacy-orchestrator` toggle flag syntax support
- Real-time progress indicators during hook execution
- Phase 4.2 completion documentation (docs/PHASE-4.2-COMPLETION.md)

### Fixed

- Fixed parameter plumbing bug where `use_legacy_orchestrator` was missing from `create_options()` function
- Fixed event loop blocking issue by restoring `asyncio.to_thread()` for synchronous phase methods
- Fixed console output buffering - now streams in real-time
- Performance: Fast hooks now complete in ~48s (previously timed out at 180s)

### Performance

- Fast hooks: ~48s (vs 180s+ timeout before Phase 4.2)
- Full workflow: ~90s with real-time output
- Event loop: Non-blocking with `asyncio.to_thread()` for CPU-bound operations
- DI context: Preserved across thread boundaries with `Inject[]` pattern

______________________________________________________________________

## [Unreleased] - 2025-10-31

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-31

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-31

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-31

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-31

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-31

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-31

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-31

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-30

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-15

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-15

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-15

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-15

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-14

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-14

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-14

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-14

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-14

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-14

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-14

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-10

### Added

- docs: adapter migration guidance and telemetry dashboard design notes
- docs: workflow session controller ADR

### Changed

- refactor: externalize monitoring dashboard templates and share renderer utilities
- feat: add retry/backoff support to workflow event bus with telemetry benchmark (avg ~1.12k events/s)
- chore: reorganize service modules into quality/monitoring/ai subpackages with
  compatibility shims and SQLite-backed telemetry/state

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-10

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-09

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-09

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.41.3] - 2025-10-08

### Changed

- Crackerjack (quality: 69/100) - 2025-10-08 20:46:02

### Fixed

- tests: Update 6 files

## [Unreleased] - 2025-10-08

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.41.2] - 2025-10-04

### Changed

- Crackerjack (quality: 69/100) - 2025-10-04 12:48:19

### Testing

- tests: Update 5 files

### Internal

- Add newline at EOF and update uv.lock
- Modernize dependency groups and fix pre-commit hook

## [Unreleased] - 2025-10-04

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.41.0] - 2025-01-10

### BREAKING CHANGES

- **Dependency Groups Modernization**: Removed self-reference from `[dependency-groups]`
  - ⚠️ No functional impact - structural improvement only
  - Eliminates circular dependency when installing dev group
  - Follows modern UV and PEP 735 best practices
  - See `docs/README.md` (Migration Notes) for details

### Changed

- Removed `"crackerjack"` self-reference from dev dependency group
- Updated dependency group structure for better UV compatibility

______________________________________________________________________

## [0.40.3] - 2025-10-04

### Testing

- test: Update 5 files

## [Unreleased] - 2025-10-04

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.40.2] - 2025-10-04

### Documentation

- config: Update CHANGELOG, pyproject, uv

## [Unreleased] - 2025-10-04

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.40.1] - 2025-10-04

### Fixed

- test: Update 12 files

## [0.40.0] - 2025-10-04

### Added

- Add AI-powered auto-fix workflow with iteration loop

### Changed

- Crackerjack (quality: 69/100) - 2025-10-03 21:23:05
- Crackerjack (quality: 69/100) - 2025-10-04 03:04:08
- Crackerjack (quality: 69/100) - 2025-10-04 03:23:36

### Fixed

- test: Update 8 files

### Internal

- Cleanup working docs and update gitignore

## [Unreleased] - 2025-10-04

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-04

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-04

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-04

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-03

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-03

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-03

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-03

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.39.11] - 2025-10-03

### Changed

- Crackerjack (quality: 69/100) - 2025-10-03 17:08:40

### Fixed

- test: Update 7 files

## [Unreleased] - 2025-10-03

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.39.11] - 2025-10-03

### Fixed

- **CRITICAL:** Fixed `--ai-fix` flag completely broken due to two separate bugs:
  1. Parameter passing bug in `_setup_debug_and_verbose_flags()` - was hardcoding `ai_fix=False` instead of preserving user's flag value
  1. Workflow routing bug in three orchestrator functions - weren't checking `options.ai_agent` before routing to AI workflow
- Added comprehensive unit tests for parameter passing fix (4 tests, all passing)
- Verified complete data flow: `--ai-fix` → parameter preservation → `options.ai_agent` property → workflow routing
- All three workflow paths now correctly delegate to AI agent when `--ai-fix` is enabled:
  - `_execute_standard_hooks_workflow_monitored()` (default workflow)
  - `_run_fast_hooks_phase_monitored()` (`--fast` workflow)
  - `_run_comprehensive_hooks_phase_monitored()` (`--comp` workflow)

### Documentation

- Added `AI-FIX-TEST-RESULTS.md` with complete test verification and data flow analysis
- Added `AI-FIX-IMPLEMENTATION-AND-TEST-PLAN.md` with comprehensive implementation details
- Added `AI-FIX-QUICK-SUMMARY.md` for quick reference

## [0.39.10] - 2025-10-03

### Fixed

- test: Update 7 files

## [Unreleased] - 2025-10-03

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.39.9] - 2025-10-03

### Testing

- tests: Update 5 files

## [Unreleased] - 2025-10-03

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.39.8] - 2025-10-03

### Testing

- tests: Update CHANGELOG, pyproject, test_session_coordinator

## [Unreleased] - 2025-10-03

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.39.7] - 2025-10-03

### Changed

- Crackerjack (quality: 69/100) - 2025-10-03 10:30:07
- Crackerjack (quality: 69/100) - 2025-10-03 11:48:05
- Crackerjack (quality: 69/100) - 2025-10-03 12:08:12

### Documentation

- Complete Phase 1 & 2 documentation audit and updates
- Complete Phase 3 optimization - 100% CLI coverage achieved

### Testing

- test: Update 6 files

## [Unreleased] - 2025-10-03

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-03

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-10-03

### Added

- docs: Add documentation for 3 new AI agents (SemanticAgent, ArchitectAgent, EnhancedProactiveAgent)
- docs: Comprehensive documentation audit report with 73-file inventory

### Changed

- docs: Update agent count from 9 to 12 across README.md and CLAUDE.md
- docs: Enhanced agent descriptions with capabilities and use cases

## [0.39.6] - 2025-10-03

### Changed

- Crackerjack (quality: 64/100) - 2025-10-02 13:40:49
- Crackerjack (quality: 64/100) - 2025-10-02 20:06:38
- Crackerjack (quality: 64/100) - 2025-10-02 20:47:06
- Crackerjack (quality: 64/100) - 2025-10-02 20:54:53
- Crackerjack (quality: 64/100) - 2025-10-02 21:20:59
- Crackerjack (quality: 64/100) - 2025-10-02 22:04:12
- Crackerjack (quality: 64/100) - 2025-10-02 22:16:32
- Crackerjack (quality: 68/100) - 2025-10-02 22:58:03

### Testing

- tests: Update 4 files

## [Unreleased] - 2025-10-02

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## id: 01K6K1AYFVG7DAPYM597FJRPA8

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.39.5] - 2025-10-02

### Testing

- test: Update 6 files

## [Unreleased] - 2025-10-02

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.39.4] - 2025-10-01

### Testing

- test: Update 12 files

## [Unreleased] - 2025-10-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.39.3] - 2025-10-01

### Testing

- tests: Update 7 files

## [Unreleased] - 2025-10-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.39.2] - 2025-10-01

### Testing

- tests: Update 5 files

## [Unreleased] - 2025-10-01

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.39.1] - 2025-09-28

### Testing

- tests: Update 6 files

## [Unreleased] - 2025-09-28

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.39.0] - 2025-09-28

### Added

- test: Update 24 files

### Changed

- Crackerjack (quality: 73/100) - 2025-09-25 03:49:18
- Crackerjack (quality: 73/100) - 2025-09-25 07:28:02
- Crackerjack (quality: 73/100) - 2025-09-25 07:43:25
- Crackerjack (quality: 73/100) - 2025-09-25 07:55:55
- Crackerjack (quality: 73/100) - 2025-09-25 08:27:08
- Crackerjack (quality: 73/100) - 2025-09-25 11:31:40
- Crackerjack (quality: 73/100) - 2025-09-26 13:55:31
- Crackerjack (quality: 73/100) - 2025-09-28 08:40:14

## [Unreleased] - 2025-09-28

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-28

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [Unreleased] - 2025-09-26

### Added

- feat: add new feature

### Fixed

- fix: resolve bug in parser

## [0.38.15] - 2025-09-22

### Changed

- Prevent pre-commit configuration during initialization and ensure -s option skips hooks
- Prevent pre-commit configuration during initialization and ensure -s option skips hooks

### Testing

- test: Update 12 files

## [0.38.14] - 2025-09-22

### Testing

- test: Update 10 files

## [0.38.13] - 2025-09-22

### Changed

- Crackerjack (quality: 73/100) - 2025-09-21 21:43:13
- Crackerjack (quality: 76/100) - 2025-09-19 06:14:42
- Crackerjack (quality: 76/100) - 2025-09-19 15:39:37
- Crackerjack (quality: 76/100) - 2025-09-19 20:44:35

### Testing

- test: Update 10 files

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
