# Crackerjack Configuration Templates

These templates provide standardized `pyproject.toml` configurations for different project types.

## Template Overview

### 1. `pyproject-minimal.toml` - Minimal MCP Server

**Use For:**

- MCP servers (mailgun-mcp, raindropio-mcp, unifi-mcp, opera-cloud-mcp)
- Simple tools and utilities
- Microservices with basic quality needs

**Features:**

- ✅ Basic Ruff formatting/linting
- ✅ Standard pytest with coverage
- ✅ **Parallel test support** (`parallel = true`, `concurrency`)
- ✅ Bandit security scanning
- ✅ Creosote unused dependency detection
- ✅ 4 standard test markers (unit, integration, slow, benchmark)

**Size:** ~80 lines

______________________________________________________________________

### 2. `pyproject-library.toml` - Full-Featured Library

**Use For:**

- Python libraries (oneiric, mcp-common, acb, fastblocks)
- Shared packages
- Frameworks
- Projects with comprehensive testing needs

**Features:**

- ✅ All minimal template features
- ✅ Comprehensive test markers (10 types)
- ✅ Minimal Pyright type checking fallback
- ✅ Codespell typo detection
- ✅ Refurb modernization suggestions
- ✅ Complexipy complexity checking
- ✅ Extended coverage exclusions

**Size:** ~130 lines

______________________________________________________________________

### 3. `pyproject-full.toml` - Crackerjack-Level

**Use For:**

- Crackerjack itself
- Session-buddy
- Complex AI systems with full tooling

**Features:**

- ✅ All library template features
- ✅ Extended test markers (16 types including AI-generated, chaos, mutation)
- ✅ MCP server configuration section
- ✅ AI agent timeout settings (skylos, refurb)
- ✅ Test parallelization settings (workers, memory limits)
- ✅ Mdformat markdown formatting
- ✅ Terminal width customization

**Size:** ~175 lines

______________________________________________________________________

## Usage

### Automatic (Recommended)

Templates are automatically selected during `/crackerjack:init` based on project characteristics:

```bash
# In your project directory
/crackerjack:init
```

The AI will:

1. Analyze your project structure
1. Detect appropriate template
1. Prompt for confirmation
1. Apply template with smart merge

### Manual Selection

Override automatic detection:

```bash
# Via CLI flag
python -m crackerjack init --template minimal

# Via interactive prompt
/crackerjack:init  # Then select from menu
```

### Manual Template Application

For advanced users who want direct control:

```python
from pathlib import Path
from crackerjack.services.template_applicator import TemplateApplicator

applicator = TemplateApplicator()
applicator.apply_template(
    project_path=Path("/path/to/project"),
    template_name="minimal",
    package_name="my_package",
)
```

______________________________________________________________________

## Template Detection Logic

The AI uses multi-factor analysis:

### Minimal Template Selected When:

- Project has MCP-related dependencies (`fastmcp`, `mcp`, `mcp-common`)
- Simple dependency structure (< 15 deps, ≤ 2 dependency groups)
- No AI agent indicators
- No complex quality tools

### Library Template Selected When:

- Project has library classifiers
- Package structure with multiple modules (> 3 Python files)
- Complex dependencies (> 15 deps or > 2 dependency groups)
- Some quality tools configured (3-4 tools)

### Full Template Selected When:

- Project is crackerjack itself
- Has AI agent system (`agents/` or `intelligence/` directories)
- Multiple AI dependencies (transformers, onnxruntime, nltk, etc.)
- Complex quality tool configuration (5+ tools)

______________________________________________________________________

## Placeholders

Templates use placeholders that are automatically replaced:

| Placeholder | Replaced With | Example |
|-------------|---------------|---------|
| `<PACKAGE_NAME>` | Python package name | `excalidraw_mcp` |
| `<MCP_HTTP_PORT>` | Unique MCP HTTP port | `3032` |
| `<MCP_WEBSOCKET_PORT>` | Unique MCP WebSocket port | `3031` |

______________________________________________________________________

## Configuration Priorities

All templates ensure these critical settings:

### Must-Have (Every Template)

- ✅ `line-length = 88` (consistent formatting)
- ✅ `parallel = true` in coverage (enables pytest-xdist)
- ✅ `concurrency = ["multiprocessing"]` (prevents coverage corruption)
- ✅ `timeout = 600` in pytest (10-minute limit)
- ✅ `asyncio_mode = "auto"` (async test support)

### Recommended (Most Templates)

- Bandit security scanning
- Creosote unused dependency detection
- Ruff extend-select (minimal rule set)
- Standard test markers

### Optional (Complex Projects)

- Pyright type checking
- Codespell typo detection
- Refurb modernization
- Complexipy complexity checking
- MCP server settings
- AI agent timeouts

______________________________________________________________________

## Smart Merge Behavior

Templates are **intelligently merged** with existing configuration:

### Preserves

- ✅ Project metadata (name, version, description)
- ✅ Dependencies and dependency-groups
- ✅ Higher coverage requirements
- ✅ Existing test markers (adds new ones)
- ✅ Custom tool settings

### Adds/Updates

- ✅ Missing tool configurations
- ✅ Critical parallel test settings
- ✅ Standard quality tool configs
- ✅ Security scanning setup

### Never Overwrites

- ❌ Project identity
- ❌ Custom dependencies
- ❌ Stricter quality standards
- ❌ Project-specific settings

______________________________________________________________________

## Examples

### Example 1: New MCP Server

**Before:** No pyproject.toml
**After:** Full minimal template applied

```toml
# Generated configuration (~80 lines)
[tool.ruff]
target-version = "py313"
line-length = 88
# ... rest of minimal template
```

### Example 2: Existing Library

**Before:** Basic pyproject.toml with 85% coverage requirement
**After:** Library template merged, preserves 85% coverage

```toml
# Keeps original:
# --cov-fail-under=85

# Adds from template:
[tool.coverage.run]
parallel = true
concurrency = ["multiprocessing"]
# ... rest of library template
```

### Example 3: Complex AI System

**Before:** Crackerjack with full configuration
**After:** Full template applied, project-specific settings preserved

```toml
# Keeps custom:
[tool.crackerjack]
mcp_http_port = 8676  # Unique to crackerjack
test_workers = 0
# ... rest of full template
```

______________________________________________________________________

## Validation

After applying templates, verify with:

```bash
# Test parallel coverage works
pytest --cov=<package> --cov-report=json -n auto

# Run full quality check
python -m crackerjack run -t

# Verify configuration
python -m crackerjack run --ai-fix -t
```

______________________________________________________________________

## Benefits

### Immediate

- ✅ **3-4x faster tests** (parallel execution)
- ✅ **Consistent code style** (line-length 88)
- ✅ **Security scanning** (bandit)
- ✅ **Unused dependency detection** (creosote)

### Long-term

- ✅ **Easy new projects** (use templates)
- ✅ **Reduced maintenance** (fewer settings)
- ✅ **Better tooling** (same quality standards)
- ✅ **Faster CI/CD** (optimized timeouts)

______________________________________________________________________

## Migration Guide

### Step 1: Backup

```bash
cp pyproject.toml pyproject.toml.backup
```

### Step 2: Apply Template

```bash
/crackerjack:init
# Or manual:
python -m crackerjack init --template minimal
```

### Step 3: Verify

```bash
python -m crackerjack run -t
```

### Step 4: Commit

```bash
git add pyproject.toml
git commit -m "chore: apply crackerjack minimal template"
```

______________________________________________________________________

## Troubleshooting

### Q: Template applied incorrectly?

**A:** Use `--force` flag to reapply, or manually edit `pyproject.toml`

### Q: Tests failing after template application?

**A:** Check coverage parallel settings, ensure pytest-xdist installed

### Q: Which template for my project?

**A:** Use automatic detection, it analyzes 6+ factors to choose correctly

### Q: Can I customize after applying?

**A:** Yes! Templates are starting points, customize as needed

______________________________________________________________________

## See Also

- [CONFIG_SIMPLIFICATION_PROGRESS.md](../docs/archive/config-automation/CONFIG_SIMPLIFICATION_PROGRESS.md) - Progress tracker (archived)
- [pyproject.toml](../pyproject.toml) - Crackerjack's own configuration (full template example)
- [/crackerjack:init](../crackerjack/slash_commands/init.md) - Initialization command docs
