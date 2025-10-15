______________________________________________________________________

## description: Initialize or update crackerjack configuration for a Python project with best practices, quality hooks, and AI guidelines.

# /crackerjack:init

Initialize or update crackerjack configuration for a Python project.

## Usage

```
/crackerjack:init
/crackerjack:init --force
```

## Description

This slash command initializes a new Python project with crackerjack's best practices or updates an existing project's configuration to the latest standards.

## What It Does

1. **Checks Project State**: Verifies which configuration files exist
1. **Smart Merge Configuration**:
   - `pyproject.toml` - Intelligently merges tool configurations, preserves higher coverage requirements
   - `CLAUDE.md` - Appends crackerjack guidelines without overwriting existing content
   - `RULES.md` - Copies only if missing, preserves existing coding standards
1. **Preserves Project Identity**: Never overwrites existing project metadata, dependencies, or configurations

## When to Use /crackerjack:init

### Automatic Detection

The MCP server can detect when initialization is needed:

- **Missing Core Files**: No pyproject.toml
- **New Project**: Git repository just initialized
- **Manual Request**: User explicitly asks for initialization

### Recommended Frequency

- **New Projects**: Always run on project creation
- **Weekly**: For active development projects
- **After Tool Updates**: When crackerjack or dependencies update
- **Team Onboarding**: When new developers join

## Options

- `--force`: Force reinitialization even if configuration exists

## Example

```
User: Set up this Python project with best practices
AI: I'll initialize crackerjack configuration for your project.

/crackerjack:init

[AI executes initialization and reports results]

The project has been initialized with:
✅ pyproject.toml - Project configuration
✅ CLAUDE.md - AI guidelines
✅ RULES.md - Coding standards

Your project now follows Python best practices!
```

## Auto-Init Behavior

When connected via MCP, crackerjack can automatically suggest initialization when:

1. Running `/crackerjack:run` in an uninitialized project
1. Detecting missing critical configuration files
1. Finding configuration files that need updates

This ensures projects always have up-to-date quality standards without manual intervention.

## Smart Merge Behavior

**Crackerjack uses intelligent smart merging instead of destructive overwrites:**

### pyproject.toml Smart Merge

- **Preserves Project Identity**: Project name, version, description, dependencies remain untouched
- **Ensures Crackerjack Dependency**: Adds `crackerjack` to `[dependency-groups].dev` if missing
- **Merges Tool Configurations**: Adds missing tool sections (`[tool.ruff]`, `[tool.pyright]`, etc.)
- **Preserves Higher Coverage**: If target has higher `--cov-fail-under` than source, keeps the higher value
- **Adds Missing Pytest Markers**: Appends new test markers while preserving existing ones

### CLAUDE.md Smart Append

- **Non-Destructive**: Appends crackerjack guidelines with clear markers
- **Prevents Duplicates**: Skips if crackerjack section already exists
- **Clear Boundaries**: Uses `<!-- CRACKERJACK_START -->` and `<!-- CRACKERJACK_END -->` markers

### Universal Compatibility

This smart merge approach works with **any Python package**, not just specific projects:

- ✅ **MCP Servers** (session-mgmt-mcp, excalidraw-mcp)
- ✅ **Django Projects** with existing configurations
- ✅ **Flask Applications** with established tooling
- ✅ **Data Science Projects** with Jupyter-specific settings
- ✅ **CLI Tools** with complex pyproject.toml configurations

### Example Smart Merge Results

**Before**: Project with 85% coverage requirement
**After**: Keeps 85% coverage, adds all crackerjack tools, preserves project identity

**Before**: CLAUDE.md with project-specific guidelines
**After**: Original content + crackerjack section appended with clear markers
