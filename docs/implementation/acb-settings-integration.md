# ACB Settings Integration Implementation Plan

## Problem Analysis

**Current Issue:**

- Attempting to call `CrackerjackSettings.from_yaml()` which doesn't exist
- Synchronous `depends.set()` call times out with ACB async initialization
- Module-level registration conflicts with async requirements

**Root Causes:**

1. ACB Settings doesn't provide `from_yaml()` - must manually load YAML
1. ACB Settings initialization can be async (`create_async()`) or sync (constructor)
1. Module-level code (`__init__.py`) executes synchronously
1. YAML configuration must be loaded and passed to Settings constructor

## ACB Settings Patterns

### Pattern 1: Synchronous Initialization (Recommended for Module-Level)

```python
from acb.config import Settings
from pathlib import Path
import yaml


class MySettings(Settings):
    field1: str = "default"
    field2: int = 42


# Load YAML data
yaml_path = Path("settings/config.yaml")
with open(yaml_path) as f:
    yaml_data = yaml.safe_load(f) or {}

# Filter to only relevant fields
relevant_data = {k: v for k, v in yaml_data.items() if k in MySettings.model_fields}

# Synchronous initialization
settings = MySettings(**relevant_data)
```

### Pattern 2: Async Initialization (For Application Runtime)

```python
async def load_settings() -> MySettings:
    yaml_path = Path("settings/config.yaml")
    with open(yaml_path) as f:
        yaml_data = yaml.safe_load(f) or {}

    relevant_data = {k: v for k, v in yaml_data.items() if k in MySettings.model_fields}

    # Async initialization (loads secrets, etc.)
    return await MySettings.create_async(**relevant_data)
```

### Pattern 3: Multi-File Configuration Layering

```python
def load_layered_config(settings_class: type[Settings]) -> Settings:
    """Load configuration from multiple YAML files with priority."""
    settings_dir = Path("settings")

    # Priority order (lowest to highest)
    config_files = [
        settings_dir / "base.yaml",  # Base configuration
        settings_dir / "crackerjack.yaml",  # Main config
        settings_dir / "local.yaml",  # Local overrides (gitignored)
    ]

    # Merge YAML data
    merged_data = {}
    for config_file in config_files:
        if config_file.exists():
            with open(config_file) as f:
                file_data = yaml.safe_load(f) or {}
                merged_data.update(file_data)

    # Filter to relevant fields
    relevant_data = {
        k: v for k, v in merged_data.items() if k in settings_class.model_fields
    }

    return settings_class(**relevant_data)
```

## Recommended Solution for Crackerjack

### Implementation Strategy

1. **Create Settings Loader Utility** (`crackerjack/config/loader.py`)

   - Encapsulates YAML loading logic
   - Supports multi-file configuration layering
   - Handles missing files gracefully
   - Filters data to match Settings fields

1. **Update Settings Class** (`crackerjack/config/settings.py`)

   - Keep existing CrackerjackSettings definition
   - Add class method for convenient loading
   - Document YAML configuration pattern

1. **Update Module Initialization** (`crackerjack/config/__init__.py`)

   - Use synchronous loader for module-level registration
   - Register with ACB dependency injection
   - Provide async alternative for runtime usage

1. **Create Settings Directory Structure**

   ```
   settings/
   ├── crackerjack.yaml      # Base configuration (committed)
   ├── local.yaml            # Local overrides (gitignored)
   └── .gitkeep              # Ensure directory exists
   ```

### File Changes

#### 1. Create `crackerjack/config/loader.py`

```python
"""Settings loader for ACB configuration with YAML support."""

from pathlib import Path
from typing import TypeVar
import yaml

from acb.config import Settings

T = TypeVar("T", bound=Settings)


def load_settings(
    settings_class: type[T],
    settings_dir: Path | None = None,
) -> T:
    """Load settings from YAML files with layered configuration.

    Args:
        settings_class: The Settings class to instantiate
        settings_dir: Directory containing YAML files (default: ./settings)

    Returns:
        Initialized Settings instance with merged configuration

    Configuration Priority (highest to lowest):
        1. settings/local.yaml (local overrides, gitignored)
        2. settings/crackerjack.yaml (main configuration)
        3. Default values from Settings class
    """
    if settings_dir is None:
        settings_dir = Path.cwd() / "settings"

    # Configuration files in priority order (lowest to highest)
    config_files = [
        settings_dir / "crackerjack.yaml",
        settings_dir / "local.yaml",
    ]

    # Merge YAML data
    merged_data = {}
    for config_file in config_files:
        if config_file.exists():
            with open(config_file) as f:
                file_data = yaml.safe_load(f) or {}
                merged_data.update(file_data)

    # Filter to only fields defined in the Settings class
    relevant_data = {
        k: v for k, v in merged_data.items() if k in settings_class.model_fields
    }

    # Synchronous initialization
    return settings_class(**relevant_data)


async def load_settings_async(
    settings_class: type[T],
    settings_dir: Path | None = None,
) -> T:
    """Load settings asynchronously with full ACB initialization.

    Args:
        settings_class: The Settings class to instantiate
        settings_dir: Directory containing YAML files (default: ./settings)

    Returns:
        Initialized Settings instance with async initialization complete

    Note:
        Use this for application runtime when async context is available.
        For module-level initialization, use synchronous load_settings().
    """
    if settings_dir is None:
        settings_dir = Path.cwd() / "settings"

    # Configuration files in priority order (lowest to highest)
    config_files = [
        settings_dir / "crackerjack.yaml",
        settings_dir / "local.yaml",
    ]

    # Merge YAML data
    merged_data = {}
    for config_file in config_files:
        if config_file.exists():
            with open(config_file) as f:
                file_data = yaml.safe_load(f) or {}
                merged_data.update(file_data)

    # Filter to relevant fields
    relevant_data = {
        k: v for k, v in merged_data.items() if k in settings_class.model_fields
    }

    # Async initialization (loads secrets, etc.)
    return await settings_class.create_async(**relevant_data)
```

#### 2. Update `crackerjack/config/settings.py`

```python
# Add class method for convenient loading
@classmethod
def load(cls, settings_dir: Path | None = None) -> "CrackerjackSettings":
    """Load settings from YAML configuration files.

    Args:
        settings_dir: Directory containing YAML files (default: ./settings)

    Returns:
        Initialized CrackerjackSettings instance

    Configuration Files:
        - settings/crackerjack.yaml (base configuration)
        - settings/local.yaml (local overrides, gitignored)
    """
    from .loader import load_settings

    return load_settings(cls, settings_dir)


@classmethod
async def load_async(cls, settings_dir: Path | None = None) -> "CrackerjackSettings":
    """Load settings asynchronously with full ACB initialization.

    Args:
        settings_dir: Directory containing YAML files (default: ./settings)

    Returns:
        Initialized CrackerjackSettings instance with async init complete
    """
    from .loader import load_settings_async

    return await load_settings_async(cls, settings_dir)
```

#### 3. Update `crackerjack/config/__init__.py`

```python
from .hooks import (
    COMPREHENSIVE_STRATEGY,
    FAST_STRATEGY,
    HookConfigLoader,
    HookDefinition,
    HookStage,
    HookStrategy,
    RetryPolicy,
)
from .settings import CrackerjackSettings
from .loader import load_settings, load_settings_async

# Register settings with ACB dependency injection
from acb.depends import depends

# Load settings from YAML files (synchronous for module-level)
depends.set(CrackerjackSettings, CrackerjackSettings.load())

__all__ = [
    "COMPREHENSIVE_STRATEGY",
    "FAST_STRATEGY",
    "HookConfigLoader",
    "HookDefinition",
    "HookStage",
    "HookStrategy",
    "RetryPolicy",
    "CrackerjackSettings",
    "load_settings",
    "load_settings_async",
]
```

### Testing Strategy

1. **Unit Tests for Loader**

   - Test YAML loading with valid configuration
   - Test missing file handling (should use defaults)
   - Test configuration layering (local.yaml overrides crackerjack.yaml)
   - Test field filtering (ignore unknown YAML keys)

1. **Integration Tests**

   - Test dependency injection registration
   - Test settings retrieval via `depends.get(CrackerjackSettings)`
   - Test async loading pattern

1. **Edge Cases**

   - Empty YAML files
   - Malformed YAML (should fail gracefully)
   - Missing settings directory (should use defaults)
   - Type mismatches in YAML (Pydantic validation)

### Migration Notes

**Breaking Changes:**

- None (only fixing broken `from_yaml()` call)

**Compatibility:**

- Existing YAML files (`settings/crackerjack.yaml`) work without changes
- Defaults in `CrackerjackSettings` remain as fallbacks
- Command-line argument overrides still work (handled by argparse)

**Dependencies:**

- PyYAML (already in pyproject.toml)
- ACB 0.19.0+ (already installed)

### Documentation Updates

1. **CLAUDE.md**

   - Document settings loading pattern
   - Add example of local.yaml overrides
   - Explain configuration priority

1. **README.md**

   - Add configuration section
   - Document environment-specific settings
   - Show YAML configuration examples

## Implementation Checklist

- [ ] Create `crackerjack/config/loader.py` with YAML loading utilities
- [ ] Add `load()` and `load_async()` class methods to `CrackerjackSettings`
- [ ] Update `crackerjack/config/__init__.py` to use synchronous loader
- [ ] Add unit tests for loader functionality
- [ ] Add integration tests for DI registration
- [ ] Update documentation (CLAUDE.md, README.md)
- [ ] Verify existing YAML configuration works
- [ ] Test command-line argument overrides still work

## Success Criteria

1. ✅ Settings load from YAML files without timeout
1. ✅ ACB dependency injection works (`depends.get(CrackerjackSettings)`)
1. ✅ Configuration layering works (local.yaml overrides crackerjack.yaml)
1. ✅ Unknown YAML fields ignored (no validation errors)
1. ✅ Default values used when YAML files missing
1. ✅ Both sync and async loading patterns available
1. ✅ All existing tests pass
1. ✅ No breaking changes to existing functionality
