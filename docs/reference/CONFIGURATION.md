# Crackerjack Configuration Reference

This document describes all configuration options available in crackerjack.

## Configuration File Locations

Crackerjack loads configuration from multiple sources in order of priority:

1. **Environment variables** (highest priority)
1. `settings/local.yaml` (gitignored, for local development)
1. `settings/crackerjack.yaml` (committed to git, base configuration)
1. Default values in code (lowest priority)

## AI Settings

### Provider Selection

Choose between AI providers for code fixing:

```yaml
ai:
  ai_provider: claude  # Options: "claude" (default) or "qwen"
```

**See Also**: [Qwen Provider Documentation](../features/QWEN_PROVIDER.md)

### AI Agent Configuration

```yaml
ai:
  ai_agent: false           # Enable AI agent (default: false)
  start_mcp_server: false   # Start MCP server (default: false)
  max_iterations: 5         # Maximum AI iterations (default: 5)
  autofix: true             # Enable automatic fixing (default: true)
  ai_agent_autofix: false   # Enable AI agent autofix (default: false)
```

### Environment Variables for AI

#### Claude (Anthropic)

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

#### Qwen

```bash
export QWEN_API_KEY="sk-your-qwen-key-here"
export QWEN_MODEL="qwen-coder-plus"  # Optional
export QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"  # Optional
```

## Execution Settings

```yaml
execution:
  interactive: false        # Interactive mode (default: false)
  verbose: false           # Verbose output (default: false)
  async_mode: false        # Async execution mode (default: false)
  no_config_updates: false # Prevent config updates (default: false)
```

## Test Settings

```yaml
tests:
  run_tests: false              # Run test suite
  test_workers: 0               # Test parallelization (0 = auto-detect)
  enable_parallel_phases: false # Run tests and hooks in parallel
```

### Test Worker Configuration

- `0` (default): Auto-detect optimal worker count
- `1`: Sequential execution (no parallelization)
- `N` (N > 1): Explicit worker count
- `-N` (N < 0): Fractional workers (e.g., -2 = half of CPU cores)

## Cleaning Settings

```yaml
cleaning:
  clean: true              # Run cleaning hooks
  update_docs: false       # Update documentation
  force_update_docs: false # Force documentation update
  compress_docs: false     # Compress documentation
  auto_compress_docs: false # Auto-compress documentation
```

## Hook Settings

```yaml
hooks:
  skip_hooks: false              # Skip all hooks
  experimental_hooks: false      # Enable experimental hooks
  enable_pyrefly: false          # Enable Pyrefly
  enable_ty: false               # Enable Ty (type checking)
  enable_lsp_optimization: false # Enable LSP optimizations
```

## Documentation Settings

```yaml
documentation:
  enabled: true                 # Documentation enabled
  auto_cleanup_on_publish: true # Auto cleanup on publish
  dry_run_by_default: false     # Dry run mode
  backup_before_cleanup: true   # Backup before cleanup
```

### Essential Documentation Files

```yaml
documentation:
  essential_files:
    - AGENTS.md
    - CHANGELOG.md
    - CLAUDE.md
    - NOTES.md
    - QWEN.md
    - README.md
```

## Progress Settings

```yaml
progress:
  enabled: false        # Progress tracking disabled
  track_progress: true  # Track progress
```

## Cleanup Settings

```yaml
cleanup:
  auto_cleanup: true     # Auto cleanup enabled
  keep_debug_logs: 5     # Keep 5 debug logs
  keep_coverage_files: 10 # Keep 10 coverage files
```

## Publishing Settings

```yaml
publishing:
  commit: false      # Commit changes
  create_pr: false   # Create pull request
```

## Example Configuration Files

### Minimal Configuration

`settings/local.yaml`:

```yaml
ai:
  autofix: true
  ai_provider: claude
```

### Full Development Configuration

`settings/local.yaml`:

```yaml
ai:
  ai_provider: claude
  ai_agent: true
  autofix: true
  max_iterations: 5

execution:
  verbose: true

tests:
  run_tests: true
  test_workers: 0
  enable_parallel_phases: true

hooks:
  experimental_hooks: true
```

### Qwen Provider Configuration

`settings/local.yaml`:

```yaml
ai:
  ai_provider: qwen
  autofix: true

tests:
  run_tests: true
```

Then set environment variables:

```bash
export QWEN_API_KEY="sk-your-qwen-key"
python -m crackerjack run --ai-fix
```

## Command-Line Override

Command-line flags override configuration files:

```bash
# Override AI provider
python -m crackerjack run --ai-fix --ai-provider qwen

# Override test execution
python -m crackerjack run --run-tests --test-workers 4

# Override verbose mode
python -m crackerjack run --verbose
```

## Configuration Validation

Crackerjack validates configuration on startup:

- Invalid values are rejected with clear error messages
- Missing required fields prompt for values
- Type mismatches are reported immediately

## Best Practices

### 1. Use Environment Variables for Secrets

❌ **Don't** put API keys in config files:

```yaml
ai:
  anthropic_api_key: sk-ant-key  # DON'T DO THIS
```

✅ **Do** use environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-key"
```

### 2. Use local.yaml for Development

Keep developer-specific settings in `settings/local.yaml` (gitignored):

```yaml
# settings/local.yaml
execution:
  verbose: true

tests:
  test_workers: 4
```

### 3. Use crackerjack.yaml for Team Settings

Keep team-wide settings in `settings/crackerjack.yaml` (committed to git):

```yaml
# settings/crackerjack.yaml
hooks:
  skip_hooks: false

tests:
  run_tests: true
```

### 4. Document Provider-Specific Settings

When using Qwen, document the provider choice:

```yaml
# Using Qwen for cost efficiency
ai:
  ai_provider: qwen

# To switch back to Claude, change to:
# ai_provider: claude
```

## Troubleshooting

### Configuration Not Loading

**Problem**: Settings not taking effect

**Solutions**:

1. Check file location: Must be in `settings/` directory
1. Check YAML syntax: Use a YAML validator
1. Check priority: Environment variables override config files
1. Enable verbose mode: `python -m crackerjack run --verbose`

### Provider Not Working

**Problem**: AI provider errors

**Solutions**:

1. Verify API key is set: `echo $QWEN_API_KEY` or `echo $ANTHROPIC_API_KEY`
1. Check provider is valid: Must be "claude" or "qwen"
1. Test connection: Run with `--verbose` flag
1. Check documentation: [Qwen Provider](../features/QWEN_PROVIDER.md)

### Tests Not Running in Parallel

**Problem**: Tests running sequentially despite parallelization enabled

**Solutions**:

1. Verify pytest-xdist is installed: `uv pip list | grep pytest`
1. Check `test_workers` setting: Should be 0 (auto) or > 1
1. Check for shared state: Some tests may not be parallel-safe
1. Force parallel: `--test-workers 4`

## Related Documentation

- [Qwen Provider Documentation](../features/QWEN_PROVIDER.md)
- [Security Documentation](SECURITY.md)
- [Coverage Policy](COVERAGE_POLICY.md)
