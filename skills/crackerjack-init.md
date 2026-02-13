---
name: crackerjack-init
description: Initialize or update crackerjack configuration for a Python project with AI-powered template detection, best practices, and skill system integration
---

# Crackerjack Project Initialization

Initialize or update crackerjack configuration for a Python project with intelligent template detection and smart merging.

## 🎯 What This Does

This skill helps you set up crackerjack's quality infrastructure with:

1. **AI Template Detection**: Analyzes your project and recommends optimal configuration
2. **Smart Template Application**: Applies appropriate `pyproject.toml` template with 6+ quality tools
3. **Configuration Files**: Creates `CLAUDE.md`, `RULES.md`, `.mcp.json`, `.gitignore`
4. **Preserves Project Identity**: Never overwrites existing project metadata
5. **Skill System Integration**: Configures access to 12 AI agents and 6 MCP skill groups

## 📋 Before You Begin

**Check if this project already has crackerjack:**

```bash
# Check for existing configuration
test -f pyproject.toml && grep -q "crackerjack" pyproject.toml && echo "Already configured" || echo "Not configured"
```

**Current status questions to consider:**

- Is this a new project or existing project?
- What type of project is this? (MCP server, library, CLI tool, web app)
- Do you have existing quality tools configured? (ruff, pytest, etc.)
- What's your target test coverage? (default: 80-100%)

## 🚀 Interactive Setup

### Step 1: Project Type Detection

**What type of project are you working with?**

1. **MCP Server** → Uses `minimal` template (~80 lines)
   - Fast setup, basic quality tools
   - Ideal: simple tools, utilities, microservices

2. **Library/Framework** → Uses `library` template (~130 lines)
   - Comprehensive testing, full quality tooling
   - Ideal: packages others will import

3. **AI System / Complex App** → Uses `full` template (~175 lines)
   - AI agents, extended timeouts, maximum tooling
   - Ideal: crackerjack-level sophistication

4. **Auto-detect** (Recommended) → Let AI analyze your project
   - Examines dependencies, structure, patterns
   - Recommends optimal template

### Step 2: Configuration Strategy

**How should we handle existing configuration?**

1. **Smart Merge** (Recommended)
   - Preserves your project metadata (name, version, description)
   - Adds missing crackerjack tools
   - Keeps your higher coverage requirements
   - Merges test markers intelligently

2. **Fresh Start** (Use with caution!)
   - Creates new `pyproject.toml` from template
   - Overwrites existing crackerjack configuration
   - Preserves non-crackerjack sections
   - Best for: new projects or major reconfigurations

3. **Preview Mode**
   - Shows what would be applied
   - Lists all changes before committing
   - Safe exploration without changes

### Step 3: Additional Options

**Quality enhancements to include:**

- [ ] **Skill System** - 12 AI agents + 6 MCP skill groups (always recommended)
- [ ] **MCP Integration** - Configure crackerjack MCP server (localhost:8676)
- [ ] **Session Management** - Optional session-buddy integration
- [ ] **Extended Markers** - AI-generated, chaos, mutation testing markers

**Testing configuration:**

- [ ] **Parallel Tests** - Auto-detect workers (3-4x faster on 8-core systems)
- [ ] **Phase Parallelization** - Run tests + comprehensive hooks concurrently
- [ ] **Coverage Ratchet** - Never decrease coverage (100% target)

## 💡 Common Workflows

### Workflow 1: New Project Setup (Recommended)

**Best for**: Brand new projects, greenfield development

```bash
# Let AI detect optimal template
python -m crackerjack init

# Interactive prompts will:
# 1. Analyze your project structure
# 2. Recommend template (minimal/library/full)
# 3. Show preview of changes
# 4. Ask for confirmation
# 5. Apply smart merge
```

**What you get:**
- ✅ Optimized `pyproject.toml` for your project type
- ✅ `CLAUDE.md` with AI guidelines
- ✅ `RULES.md` with Python coding standards
- ✅ `.mcp.json` for MCP server integration
- ✅ Smart-merged `.gitignore`
- ✅ Access to 12 AI agents via skill system

### Workflow 2: Existing Project Update

**Best for**: Projects needing quality tool upgrade

```bash
# Force reinitialization with smart merge
python -m crackerjack init --force

# Or specify template explicitly
python -m crackerjack init --template library --force
```

**Smart merge behavior:**
- ✅ Project name, version, dependencies: **preserved**
- ✅ Higher coverage requirements: **kept** (85% stays 85%)
- ✅ Existing test markers: **merged** with new ones
- ✅ Custom tool settings: **preserved** unless explicitly upgrading

### Workflow 3: Template Override

**Best for**: When you know exactly what you need

```bash
# Minimal template for fast setup
python -m crackerjack init --template minimal

# Library template for comprehensive testing
python -m crackerjack init --template library

# Full template for AI systems
python -m crackerjack init --template full
```

### Workflow 4: Preview Before Applying

**Best for**: Cautious exploration, understanding changes

```bash
# Interactive mode with preview
python -m crackerjack init --interactive

# Will show:
# - Template recommendation
# - Files to be created/modified
# - Specific changes per file
# - Confirmation prompt before applying
```

## 🎨 Template Comparison

| Feature | Minimal | Library | Full |
|---------|---------|---------|------|
| **Lines** | ~80 | ~130 | ~175 |
| **Ruff** | ✅ Basic | ✅ Extended | ✅ Full |
| **Pytest** | ✅ 4 markers | ✅ 10 markers | ✅ 16 markers |
| **Type Checking** | ❌ | ✅ Pyright fallback | ✅ Full config |
| **Security** | ✅ Bandit | ✅ + Codespell | ✅ + All tools |
| **Complexity** | ❌ | ✅ Complexipy | ✅ + Limits |
| **MCP Config** | Basic | Full | Extended |
| **AI Agents** | ✅ Basic | ✅ Enhanced | ✅ Full |
| **Best For** | MCP servers, tools | Libraries, frameworks | AI systems, crackerjack-level |

## 📊 What Gets Created

### 1. pyproject.toml (Smart Merged)

**Preserved:**
- Project metadata (name, version, description, authors)
- Your dependencies
- Your custom settings
- Higher coverage requirements

**Added:**
- Crackerjack dependency (if missing)
- Tool configurations (ruff, pytest, coverage, etc.)
- Test markers (appended, not replaced)
- MCP server settings
- AI agent timeout settings

**Example smart merge:**

```toml
# BEFORE: Your project
[project]
name = "my-project"
version = "0.1.0"

[tool.coverage.run]
cov_fail_under = 85  # Your higher requirement

# AFTER: Smart merge
[project]
name = "my-project"  # ✅ Preserved
version = "0.1.0"     # ✅ Preserved

[dependency-groups]
dev = ["crackerjack"]  # ✅ Added

[tool.coverage.run]
cov_fail_under = 85  # ✅ Kept your higher value!
branch = true         # ✅ Added

[tool.crackerjack]
test_workers = 0      # ✅ Auto-detect (added)
# ... 80-175 lines of quality configuration
```

### 2. CLAUDE.md (Appended)

**Non-destructive append:**
- Adds crackerjack section with clear markers
- Skips if section already exists
- Preserves your existing guidelines

**Structure:**
```markdown
<!-- Your existing content -->

<!-- CRACKERJACK_START -->
# Crackerjack Guidelines
[Comprehensive crackerjack documentation]
<!-- CRACKERJACK_END -->
```

### 3. RULES.md (Copy If Missing)

**Safe creation:**
- Only copied if file doesn't exist
- Contains Python coding standards
- No overwriting of existing rules

### 4. .mcp.json (Create If Missing)

**Smart configuration:**
```json
{
  "mcpServers": {
    "crackerjack": {
      "command": "python",
      "args": ["-m", "crackerjack", "start"],
      "env": {
        "CRACKERJACK_MCP_PORT": "8676"
      }
    }
  }
}
```

### 5. .gitignore (Smart Merged)

**Merges common Python patterns:**
- `__pycache__/`
- `*.pyc`
- `.coverage`
- `.pytest_cache/`
- `.oneiric_cache/`
- Your existing ignores preserved

## 🔍 After Initialization

**Verify your setup:**

```bash
# Check crackerjack is available
python -m crackerjack --help

# Run quality checks
python -m crackerjack run --run-tests

# Check MCP server status
python -m crackerjack status
```

**First workflow recommendation:**

```bash
# After init, run full quality workflow
python -m crackerjack run --ai-fix --run-tests
```

## 🎯 Troubleshooting

**Issue**: "Template detection failed"

**Solution**:
```bash
# Specify template explicitly
python -m crackerjack init --template library
```

**Issue**: "pyproject.toml already exists"

**Solution**:
```bash
# Use force with smart merge
python -m crackerjack init --force
```

**Issue**: "Coverage requirement too high"

**Solution**:
```bash
# Smart merge keeps your higher requirement
# Or manually edit after init:
# pyproject.toml: [tool.coverage.run] cov_fail_under = 85
```

## 📚 Next Steps

After initialization:

1. **Review Generated Files**: Check `pyproject.toml`, `CLAUDE.md`
2. **Run Quality Checks**: `python -m crackerjack run --run-tests`
3. **Configure AI Agents**: Try skill system via MCP tools
4. **Set Up CI/CD**: Add crackerjack to your pipeline
5. **Customize as Needed**: Adjust settings for your workflow

**Related Skills:**
- `crackerjack-run` - Run quality checks with AI fixing
- `session-start` - Begin session with crackerjack integration
- `session-checkpoint` - Mid-session quality verification

**Further Reading:**
- Crackerjack Architecture: `ARCHITECTURE.md`
- Quality Decision Framework: `CLAUDE.md`
- AI Agent System: `docs/AI_FIX_EXPECTED_BEHAVIOR.md`
