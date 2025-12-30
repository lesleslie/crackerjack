______________________________________________________________________

## description: Initialize or update crackerjack configuration for a Python project with best practices, quality hooks, AI guidelines, and skill system integration.

# /crackerjack:init

Initialize or update crackerjack configuration for a Python project.

## Usage

```
/crackerjack:init
/crackerjack:init --force
```

## Description

This slash command initializes a new Python project with crackerjack's best practices or updates an existing project's configuration to the latest standards, including integration with Crackerjack's AI agent skill system.

## What It Does

1. **Checks Project State**: Verifies which configuration files exist
1. **Smart Merge Configuration**:
   - `pyproject.toml` - Intelligently merges tool configurations, preserves higher coverage requirements
   - `CLAUDE.md` - Appends crackerjack guidelines without overwriting existing content
   - `RULES.md` - Copies only if missing, preserves existing coding standards
   - `.mcp.json` - Creates MCP configuration for Crackerjack server integration
   - `.gitignore` - Smart merges common Python ignore patterns
1. **Preserves Project Identity**: Never overwrites existing project metadata, dependencies, or configurations

## New: Skill System Integration

When you run `/crackerjack:init`, your project will be configured to access Crackerjack's AI agent skill system:

- **11 Agent Skills**: RefactoringAgent, PerformanceAgent, SecurityAgent, etc.
- **6 MCP Skill Groups**: quality_checks, semantic_search, proactive_agent, monitoring, utilities, intelligence
- **8 Skill Management Tools**: list_skills, get_skill_info, search_skills, execute_skill, etc.
- **Smart Agent Matching**: Automatically finds the best agent for any issue type

After initialization, you can use skills via MCP:

```
# List all available skills
await mcp.call_tool("list_skills", {"skill_type": "all"})

# Find skills for a complexity issue
await mcp.call_tool("get_skills_for_issue", {"issue_type": "complexity"})

# Execute a skill
await mcp.call_tool("execute_skill", {
    "skill_id": "skill_abc123",
    "issue_type": "complexity",
    "issue_data": {"message": "...", "file_path": "..."}
})
```

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
- **Feature Updates**: After Crackerjack feature additions (e.g., skill system)

## Options

- `--force`: Force reinitialization even if configuration exists

## Example

```
User: Set up this Python project with best practices
AI: I'll initialize crackerjack configuration for your project.

/crackerjack:init

[AI executes initialization and reports results]

The project has been initialized with:
✅ pyproject.toml - Project configuration with crackerjack
✅ CLAUDE.md - AI guidelines for Claude Code
✅ RULES.md - Python coding standards
✅ .mcp.json - MCP server configuration
✅ .gitignore - Python ignore patterns
✅ Skill System - Access to 11 AI agent skills

Your project now has:
- Quality checks (ruff, pytest, coverage, complexity)
- AI-powered fixing with 12 specialized agents
- Skill system for intelligent agent selection
- MCP integration for tool access
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
- **Merges Tool Configurations**: Adds missing tool sections (`[tool.ruff]`, `[tool.pyright]`, `[tool.coverage]`, etc.)
- **Preserves Higher Coverage**: If target has higher `--cov-fail-under` than source, keeps the higher value
- **Adds Missing Pytest Markers**: Appends new test markers while preserving existing ones
- **Includes Skill System**: Configures access to AI agent skills via MCP

### CLAUDE.md Smart Append

- **Non-Destructive**: Appends crackerjack guidelines with clear markers
- **Prevents Duplicates**: Skips if crackerjack section already exists
- **Clear Boundaries**: Uses `<!-- CRACKERJACK_START -->` and `<!-- CRACKERJACK_END -->` markers
- **Includes Skill Documentation**: References to skill system usage

### .mcp.json Creation

- **Smart Configuration**: Creates `.mcp.json` if missing
- **MCP Server Setup**: Configures connection to Crackerjack MCP server (localhost:8676)
- **Session Management**: Optional session-mgmt server configuration
- **Timeout Configuration**: Appropriate timeouts for AI operations
- **Preserves Existing**: Won't overwrite if `.mcp.json` already exists

### Universal Compatibility

This smart merge approach works with **any Python package**, not just specific projects:

- ✅ **MCP Servers** (session-mgmt-mcp, excalidraw-mcp, custom servers)
- ✅ **Django Projects** with existing configurations
- ✅ **Flask Applications** with established tooling
- ✅ **Data Science Projects** with Jupyter-specific settings
- ✅ **CLI Tools** with complex pyproject.toml configurations

### Example Smart Merge Results

**Before**: Project with 85% coverage requirement
**After**: Keeps 85% coverage, adds all crackerjack tools, preserves project identity

**Before**: CLAUDE.md with project-specific guidelines
**After**: Original content + crackerjack section appended with clear markers

**Before**: No MCP configuration
**After**: Creates `.mcp.json` with Crackerjack server connection + skill system access

## Benefits of Initialization

After running `/crackerjack:init`, your project gains:

1. **Quality Infrastructure**

   - Ruff formatting and linting
   - Pytest testing with coverage
   - Type checking with pyright
   - Complexity limits
   - Security scanning

1. **AI Agent Access**

   - 12 specialized AI agents (refactoring, security, performance, etc.)
   - Smart agent selection based on issue type
   - Batch processing capabilities
   - Confidence-based execution

1. **Skill System**

   - Discoverable agent capabilities
   - 8 skill management tools
   - Search and filtering by issue type
   - Performance tracking

1. **MCP Integration**

   - Direct tool access via Claude Code
   - Real-time progress monitoring
   - Intelligent fix suggestions
   - Semantic search capabilities
