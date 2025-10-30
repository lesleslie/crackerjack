# Crackerjack Configuration Systems Guide

## Overview

Crackerjack uses two complementary configuration systems that serve different purposes in the application lifecycle:

1. **ACB Settings** - Runtime application configuration (handled by ACB dependency injection system)
2. **Config Template Service** - Project-level configuration management
3. **Config Merge Service** - Project initialization configuration merging

## System 1: ACB Settings (Runtime Configuration)

### Purpose
Manages application runtime settings and configurations for the Crackerjack application itself.

### Location
- Primary: `crackerjack/config/settings.py`
- Configuration loading: `crackerjack/config/loader.py`

### Usage Pattern
```python
from acb.depends import depends
from crackerjack.config.settings import CrackerjackSettings

settings = depends.get(CrackerjackSettings)
```

### Features
- Automatic environment variable loading (CRACKERJACK_* prefix)
- Type validation via Pydantic
- Single source of truth for all runtime settings
- Backward compatibility with existing APIs

## System 2: ConfigTemplateService (Template Management)

### Purpose
Manages version-based configuration templates for project files like `.pre-commit-config.yaml` and `pyproject.toml`.

### Location
- Service: `crackerjack/services/config_template.py`
- CLI Integration: `crackerjack/cli/handlers.py`

### Usage
```bash
# Check for available configuration updates
python -m crackerjack --check-config-updates

# Show diff for specific configuration type
python -m crackerjack --diff-config pre-commit

# Apply configuration updates interactively
python -m crackerjack --apply-config-updates --config-interactive

# Refresh configuration cache
python -m crackerjack --refresh-cache
```

### Features
- Version-based tracking of configuration templates
- User-controlled updates (explicit approval required)
- Diff visibility (shows changes before applying)
- Automatic pre-commit cache management
- Centralized configuration templates as code

## System 3: ConfigMergeService (Initialization Merging)

### Purpose
Used during project initialization to intelligently merge configuration files while preserving user modifications.

### Location
- Service: `crackerjack/services/config_merge.py`
- Protocol: `crackerjack/models/protocols.py`
- Used by: `crackerjack/services/initialization.py`

### Features
- Smart merging of pyproject.toml
- Smart merging of .pre-commit-config.yaml
- Smart merging of .gitignore
- Preserves existing user configurations while adding new settings

## Interaction Between Systems

1. **Project Initialization** (ConfigMergeService)
   - When `python -m crackerjack` is run for a new project
   - Uses ConfigMergeService to intelligently merge template configs

2. **Ongoing Development** (ConfigTemplateService)
   - When users want to update project configurations
   - Uses ConfigTemplateService for version-controlled updates

3. **Runtime Operation** (ACB Settings)
   - Controls all runtime behavior of Crackerjack
   - Manages command-line options and internal configuration

## Decision Framework

| Scenario | System to Use | Reason |
|----------|---------------|---------|
| Setting runtime options | ACB Settings | Global application configuration |
| Initializing a new project | ConfigMergeService | Automatic setup with smart merging |
| Updating existing project configs | ConfigTemplateService | User-controlled, versioned updates |
| Managing pre-commit hooks | ConfigTemplateService | Template-based updates with diff visibility |

## Migration Status

The configuration system has evolved from a single monolithic system to three specialized components:

- **Before**: 11 config files (~1,808 LOC) with file copying and automatic merging
- **After**: 3 specialized systems (~300 LOC for ACB Settings + services for templates and initialization)

This architecture provides:
- Clear separation of concerns
- User control over configuration updates
- Maintainable code structure
- Flexible initialization vs. ongoing management
