# CLI Semantic Naming Improvements

## Overview

Enhance CLI flag names for better semantic clarity while maintaining backward compatibility through aliases.

## Semantic Mapping

### Core Workflow Operations

| Current Flag | Semantic Name | Short Flag | Description | Reasoning |
|-------------|---------------|------------|-------------|-----------|
| `clean` | `strip_code` | `-x` | Remove docstrings and comments | "Clean" is ambiguous - this specifically strips code |
| `all` | `full_release` | `-a` | Complete release workflow | "All" is too vague - this is specifically a release |
| `test` | `run_tests` | `-t` | Execute test suite | More descriptive of actual action |
| `comp` | `comprehensive_hooks` | `--comp` | Run comprehensive hooks only | Clarifies what "comp" means |
| `fast` | `fast_hooks` | `--fast` | Run fast hooks only | Clarifies what "fast" means |

### AI & Automation

| Current Flag | Semantic Name | Short Flag | Description | Reasoning |
|-------------|---------------|------------|-------------|-----------|
| `ai_agent` | `ai_fix` | `--ai-fix` | Enable AI auto-fixing | More specific about AI's role |
| `orchestrated` | `smart_workflow` | `--smart` | Intelligent workflow orchestration | "Orchestrated" is technical jargon |
| `boost_coverage` | `improve_coverage` | `--improve-cov` | Automatically improve test coverage | More action-oriented |

### Server Management

| Current Flag | Semantic Name | Short Flag | Description | Reasoning |
|-------------|---------------|------------|-------------|-----------|
| `start_mcp_server` | `start_ai_server` | `--start-ai` | Start AI agent server | Users don't need to know "MCP" |
| `stop_mcp_server` | `stop_ai_server` | `--stop-ai` | Stop AI agent server | Consistent with start |
| `restart_mcp_server` | `restart_ai_server` | `--restart-ai` | Restart AI agent server | Consistent naming |
| `watchdog` | `monitor_services` | `--monitor` | Monitor and restart services | More descriptive |

### Development & Debugging

| Current Flag | Semantic Name | Short Flag | Description | Reasoning |
|-------------|---------------|------------|-------------|-----------|
| `skip_hooks` | `no_hooks` | `--no-hooks` | Skip pre-commit hooks | More intuitive negative form |
| `experimental_hooks` | `beta_tools` | `--beta` | Enable beta/experimental tools | "Beta" is more user-friendly |
| `async_mode` | `parallel_mode` | `--parallel` | Enable parallel processing | Users understand "parallel" better |

### Version & Publishing

| Current Flag | Semantic Name | Short Flag | Description | Reasoning |
|-------------|---------------|------------|-------------|-----------|
| `no_git_tags` | `skip_tagging` | `--no-tags` | Skip Git tag creation | More explicit about action |
| `skip_version_check` | `no_version_check` | `--no-ver-check` | Skip version validation | Consistent negative naming |
| `cleanup_pypi` | `clean_releases` | `--clean-pypi` | Clean up old PyPI releases | More action-oriented |

### Monitoring & Analytics

| Current Flag | Semantic Name | Short Flag | Description | Reasoning |
|-------------|---------------|------------|-------------|-----------|
| `enhanced_monitor` | `advanced_monitor` | `--advanced` | Advanced monitoring dashboard | "Enhanced" is vague |
| `track_progress` | `show_progress` | `--progress` | Display progress tracking | More direct |
| `coverage_status` | `coverage_report` | `--cov-report` | Show coverage status | More specific |

## Implementation Strategy

### Phase 1: Backward Compatibility

```python
class Options(BaseModel):
    # New semantic names (primary)
    strip_code: bool = False
    full_release: BumpOption | None = None
    run_tests: bool = False
    ai_fix: bool = False

    # Legacy aliases (deprecated)
    clean: bool | None = None
    all: BumpOption | None = None
    test: bool | None = None
    ai_agent: bool | None = None

    def __post_init__(self):
        """Handle legacy flag mapping."""
        if self.clean is not None:
            self.strip_code = self.clean
            warnings.warn("--clean is deprecated, use --strip-code", DeprecationWarning)

        if self.all is not None:
            self.full_release = self.all
            warnings.warn("--all is deprecated, use --full-release", DeprecationWarning)
```

### Phase 2: CLI Help Updates

```python
CLI_OPTIONS = {
    "strip_code": typer.Option(
        False,
        "-x",
        "--strip-code",
        "--clean",  # Backward compatibility alias
        help="Remove docstrings, line comments, and unnecessary whitespace from source code with automatic backup protection (doesn't affect test files).",
    ),
    "full_release": typer.Option(
        None,
        "-a",
        "--full-release",
        "--all",  # Backward compatibility alias
        help="Complete release workflow: strip code, run tests, publish, and commit changes (patch, minor, major).",
        case_sensitive=False,
    ),
    "ai_fix": typer.Option(
        False,
        "--ai-fix",
        "--ai-agent",  # Backward compatibility alias
        help="Enable AI-powered auto-fixing of code issues and failures.",
    ),
}
```

### Phase 3: Documentation Updates

Update all documentation files:

- `README.md` - Update command examples
- `CLAUDE.md` - Update essential commands section
- `AI-REFERENCE.md` - Update command decision trees
- Feature implementation plans - Update flag references

### Phase 4: Gradual Migration

1. **Version 1.x**: Introduce semantic names with deprecation warnings for old flags
1. **Version 2.x**: Remove deprecated flags (breaking change)
1. **Documentation**: Always show semantic names, mention aliases for compatibility

## Enhanced Help Messages

### Current vs Improved

**Before:**

```bash
--clean                Remove docstrings, line comments...
--all                  Run with `-x -t -p <version> -c` development options
--ai-agent             Enable AI agent mode with autonomous auto-fixing
```

**After:**

```bash
--strip-code, -x       Strip code: remove docstrings and comments (with backup protection)
--full-release, -a     Full release workflow: code strip → tests → publish → commit
--ai-fix               AI auto-fix: let AI agents automatically resolve code issues
```

## Error Message Improvements

### Semantic Error Context

```python
def validate_workflow_options(options: Options) -> None:
    """Provide semantic error messages."""

    if options.full_release and not options.run_tests:
        raise ValueError(
            "Full release workflow requires tests. "
            "Use: --full-release --run-tests (or just --full-release which implies tests)"
        )

    if options.strip_code and options.interactive:
        print("⚠️  Strip code mode will modify files. Continue? (y/N): ")

    if options.ai_fix and not options.run_tests:
        print("💡 Tip: AI auto-fix works best with --run-tests to validate fixes")
```

## Migration Timeline

- **Week 1**: Implement backward compatibility system
- **Week 2**: Update CLI help messages and validation
- **Week 3**: Update all documentation with semantic names
- **Week 4**: Add enhanced error messages and tips
- **Week 5**: Testing and user feedback collection

## Expected Benefits

1. **Clarity**: Users immediately understand what commands do
1. **Discoverability**: Semantic names are self-documenting
1. **Consistency**: Similar operations use similar naming patterns
1. **User Experience**: Less cognitive load, faster onboarding
1. **Maintainability**: Code is more self-documenting

## Backward Compatibility Guarantee

All existing scripts and workflows will continue working through:

- Alias support for all old flags
- Deprecation warnings (not errors)
- Clear migration guidance in documentation
- Gradual phase-out over major version releases
