> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | [Config](./README.md)

# Config

Configuration management using ACB Settings with YAML-based configuration, type validation, and dependency injection.

## Overview

The config package provides centralized configuration management for Crackerjack using the ACB Settings framework. Configuration is loaded from YAML files with a priority system, validated using Pydantic models, and integrated with the dependency injection system for seamless access throughout the application.

## Core Components

- **settings.py**: ACB Settings definitions with Pydantic validation
- **loader.py**: Configuration loading and merging logic
- **hooks.py**: Hook definitions and metadata configuration
- **tool_commands.py**: Tool command definitions and execution parameters
- **global_lock_config.py**: Global lock configuration for session management

## Configuration Architecture

### File Hierarchy

```
settings/
├── crackerjack.yaml    # Base configuration (committed to git)
└── local.yaml          # Local overrides (gitignored, for development)
```

### Priority Order

Configuration is loaded with the following priority (highest to lowest):

1. **`settings/local.yaml`** — Local developer overrides (gitignored)
1. **`settings/crackerjack.yaml`** — Base project configuration
1. **Default values** in `CrackerjackSettings` class definitions

### Loading Modes

```python
from crackerjack.config import CrackerjackSettings
from acb.depends import depends

# Option 1: Load directly (synchronous)
settings = CrackerjackSettings.load()

# Option 2: Get from dependency injection (recommended)
settings = depends.get(CrackerjackSettings)

# Option 3: Load asynchronously (for runtime use)
settings = await CrackerjackSettings.load_async()
```

## Settings Structure

### Main Settings Class

The `CrackerjackSettings` class aggregates all configuration categories:

```python
class CrackerjackSettings(Settings):
    console: ConsoleSettings
    cleaning: CleaningSettings
    hooks: HookSettings
    testing: TestSettings
    publishing: PublishSettings
    git: GitSettings
    ai: AISettings
    execution: ExecutionSettings
    progress: ProgressSettings
    cleanup: CleanupSettings
    advanced: AdvancedSettings
    mcp_server: MCPServerSettings
    zuban_lsp: ZubanLSPSettings
    global_lock: GlobalLockSettings

    # Orchestration settings
    enable_orchestration: bool = True
    orchestration_mode: str = "acb"
    enable_caching: bool = True
    cache_backend: str = "memory"
    cache_ttl: int = 3600
    max_parallel_hooks: int = 4
    default_timeout: int = 600
    # ... and more
```

### Configuration Categories

#### Console Settings

```python
class ConsoleSettings(Settings):
    width: int = 70  # Console output width
```

#### Hook Settings

```python
class HookSettings(Settings):
    skip_hooks: bool = False
    update_precommit: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    enable_lsp_optimization: bool = False
```

#### Test Settings

```python
class TestSettings(Settings):
    test: bool = False
    benchmark: bool = False
    test_workers: int = 0  # 0 = auto-detect
    test_timeout: int = 0
    auto_detect_workers: bool = True
    max_workers: int = 8
    min_workers: int = 2
    memory_per_worker_gb: float = 2.0
```

#### AI Settings

```python
class AISettings(Settings):
    ai_agent: bool = False
    start_mcp_server: bool = False
    max_iterations: int = 5
    autofix: bool = True
    ai_agent_autofix: bool = False
```

#### MCP Server Settings

```python
class MCPServerSettings(Settings):
    http_port: int = 8676
    http_host: str = "127.0.0.1"
    websocket_port: int = 8675
    http_enabled: bool = False
```

#### Global Lock Settings

```python
class GlobalLockSettings(Settings):
    enabled: bool = True
    timeout_seconds: float = 600.0
    stale_lock_hours: float = 2.0
    lock_directory: Path = Path.home() / ".crackerjack" / "locks"
    session_heartbeat_interval: float = 30.0
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 5.0
    enable_lock_monitoring: bool = True
```

## Usage Examples

### Accessing Settings

```python
from acb.depends import depends, Inject
from crackerjack.config import CrackerjackSettings


@depends.inject
def my_function(settings: Inject[CrackerjackSettings] = None) -> None:
    # Access nested settings
    if settings.testing.auto_detect_workers:
        workers = calculate_workers(settings.testing.max_workers)

    # Access top-level settings
    if settings.enable_caching:
        setup_cache(ttl=settings.cache_ttl)
```

### Creating Local Overrides

```yaml
# settings/local.yaml (gitignored)

# Development overrides
execution:
  verbose: true
  debug: true

testing:
  test_workers: 4
  max_workers: 8

ai:
  ai_agent: true
  max_iterations: 10

mcp_server:
  websocket_port: 8675
  http_enabled: true

hooks:
  experimental_hooks: true
  enable_lsp_optimization: true

# Orchestration tuning
max_parallel_hooks: 8
cache_ttl: 7200
log_cache_stats: true
log_execution_timing: true
```

### Hook Configuration

Hooks are defined in `hooks.py` with metadata for orchestration:

```python
from crackerjack.config.hooks import HookDefinition, HookStage, SecurityLevel

hook = HookDefinition(
    name="ruff",
    command=["ruff", "check", "--fix"],
    timeout=45,
    stage=HookStage.FAST,
    dependencies=[],
    manual_stage=False,
    security_level=SecurityLevel.MEDIUM,
    use_precommit_legacy=False,
    accepts_file_paths=True,
)
```

### Tool Commands

Tool commands define execution parameters:

```python
from crackerjack.config.tool_commands import ToolCommand

command = ToolCommand(
    name="ruff",
    executable="ruff",
    args=["check", "--fix"],
    timeout=60,
    requires_files=True,
    output_format="json",
)
```

## Hook Stages

Crackerjack uses a two-stage hook system:

### Fast Stage (~5s)

Essential checks for rapid feedback:

```yaml
hooks:
  - ruff (format + lint)
  - trailing-whitespace
  - end-of-file-fixer
  - gitleaks (secret detection)
  - codespell (spelling)
```

### Comprehensive Stage (~30s)

Thorough static analysis:

```yaml
hooks:
  - zuban (type checking)
  - bandit/semgrep (security)
  - skylos (dead code)
  - creosote (unused deps)
  - complexipy (complexity ≤15)
  - refurb (modern patterns)
```

## Configuration Best Practices

1. **Use settings/local.yaml for Development**

   - Never commit local.yaml to git
   - Override defaults for your workflow
   - Test different configurations

1. **Keep Base Configuration Minimal**

   - settings/crackerjack.yaml should have sane defaults
   - Document why non-obvious values are chosen
   - Use comments to explain complex settings

1. **Validate Configuration**

   - Pydantic provides automatic validation
   - Add custom validators for business rules
   - Use type hints for all settings

1. **Access via Dependency Injection**

   - Use `Inject[CrackerjackSettings]` in functions
   - Avoid `Settings.load()` in business logic
   - Let DI container manage lifecycle

1. **Organize by Domain**

   - Group related settings in sub-classes
   - Use clear, descriptive names
   - Follow the existing pattern

## Common Configuration Patterns

### Enable AI Auto-Fixing

```yaml
# settings/local.yaml
ai:
  ai_agent: true
  autofix: true
  max_iterations: 10

execution:
  verbose: true  # See agent decisions
```

### Fast Iteration Mode

```yaml
# settings/local.yaml
hooks:
  skip_hooks: false  # Run fast hooks

execution:
  verbose: false  # Quiet output

testing:
  test_workers: -2  # Half cores for faster cycles
```

### CI/Production Mode

```yaml
# settings/crackerjack.yaml
testing:
  test_workers: 0  # Auto-detect
  test_timeout: 300
  auto_detect_workers: true

hooks:
  skip_hooks: false
  experimental_hooks: false

execution:
  verbose: false
  async_mode: true

orchestration_mode: "acb"
enable_caching: true
max_parallel_hooks: 11
stop_on_critical_failure: true
```

## Environment Variables

Some settings can be overridden with environment variables:

```bash
# Disable auto-worker detection
export CRACKERJACK_DISABLE_AUTO_WORKERS=1

# Override MCP port
export CRACKERJACK_MCP_PORT=8675

# Enable verbose logging
export CRACKERJACK_VERBOSE=1
```

## Validation

Settings are validated using Pydantic:

```python
from pydantic import field_validator, model_validator


class TestSettings(Settings):
    test_workers: int = 0

    @field_validator("test_workers")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        if v < -8 or v > 64:
            raise ValueError("test_workers must be between -8 and 64")
        return v
```

## Migration from Legacy Config

Old configuration methods are deprecated:

```python
# ❌ Old approach (deprecated)
from crackerjack.config import get_config

config = get_config()

# ✅ New approach (ACB Settings)
from acb.depends import depends, Inject
from crackerjack.config import CrackerjackSettings


@depends.inject
def my_func(settings: Inject[CrackerjackSettings] = None):
    # Use settings here
    pass
```

## Troubleshooting

### Configuration Not Loading

```bash
# Check if settings files exist
ls -la settings/

# Verify YAML syntax
python -c "import yaml; yaml.safe_load(open('settings/crackerjack.yaml'))"

# Enable debug logging
python -m crackerjack --debug
```

### Settings Not Applied

```python
# Verify DI container has settings
from acb.depends import depends
from crackerjack.config import CrackerjackSettings

settings = depends.get(CrackerjackSettings)
print(settings.model_dump_json(indent=2))
```

### Unknown Fields Warning

ACB Settings silently ignores unknown fields in YAML files. Check for typos:

```yaml
# ❌ Will be ignored (typo)
tesing:
  test_workers: 4

# ✅ Correct
testing:
  test_workers: 4
```

## Related

- [CLI](../cli/README.md) — CLI uses configuration for option defaults
- [Services](../services/README.md) — Services access configuration via DI
- [Managers](../managers/README.md) — Managers configure orchestration
- [Main README](../../README.md) — Configuration examples
- [CLAUDE.md](../../docs/guides/CLAUDE.md) — ACB Settings integration overview

## Future Enhancements

- [ ] Configuration validation UI/CLI command
- [ ] Configuration migration tool for version upgrades
- [ ] Configuration profiles (dev, test, prod)
- [ ] Remote configuration support
- [ ] Configuration change monitoring and reload
- [ ] Schema generation for IDE auto-completion
