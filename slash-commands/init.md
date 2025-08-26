# /init

Initialize or update crackerjack configuration for a Python project.

## Usage

```
/init
/init --force
```

## Description

This slash command initializes a new Python project with crackerjack's best practices or updates an existing project's configuration to the latest standards.

## What It Does

1. **Checks Project State**: Verifies which configuration files exist
1. **Creates Missing Files**:
   - `pyproject.toml` - Project metadata and dependencies
   - `.pre-commit-config.yaml` - Code quality hooks
   - `CLAUDE.md` - AI assistant guidelines
   - `RULES.md` - Project coding standards
1. **Updates Outdated Configs**: Refreshes configurations older than 30 days
1. **Installs Pre-commit Hooks**: Sets up git hooks for quality enforcement

## When to Use /init

### Automatic Detection

The MCP server can detect when initialization is needed:

- **Missing Core Files**: No pyproject.toml or .pre-commit-config.yaml
- **New Project**: Git repository just initialized
- **Outdated Hooks**: Pre-commit hooks older than 30 days
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

/init

[AI executes initialization and reports results]

The project has been initialized with:
✅ pyproject.toml - Project configuration
✅ .pre-commit-config.yaml - Quality hooks
✅ CLAUDE.md - AI guidelines
✅ RULES.md - Coding standards

Your project now follows Python best practices!
```

## Auto-Init Behavior

When connected via MCP, crackerjack can automatically suggest initialization when:

1. Running `/crackerjack` in an uninitialized project
1. Detecting missing critical configuration files
1. Finding outdated pre-commit hooks (>30 days old)

This ensures projects always have up-to-date quality standards without manual intervention.
