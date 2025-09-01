# AGENTS.md

AI agent interaction patterns and tooling for Crackerjack - the opinionated Python project management tool with autonomous code quality enforcement.

## Overview

Crackerjack is an AI-native Python development tool that provides **autonomous, iterative code fixing** through a sophisticated multi-agent system. It goes far beyond simple linting to provide intelligent code analysis, automated fixes, and comprehensive quality enforcement.

**Core Philosophy**: Every line of code is a liability. The best code is no code. Crackerjack helps achieve this through:

- **DRY (Don't Repeat Yourself)**: Automated duplicate code detection and consolidation
- **YAGNI (You Ain't Gonna Need It)**: Build only what's needed now
- **KISS (Keep It Simple, Stupid)**: Complexity reduction through automated refactoring
- **Self-Documenting Code**: Code that explains itself without excessive comments

## AI Agent Architecture

### Multi-Agent Coordination System

Crackerjack includes **9 specialized sub-agents** that automatically detect, analyze, and fix different types of code quality issues:

#### 🏗️ Code Structure & Quality Agents

**RefactoringAgent** - Primary Expertise: Complexity Reduction (`IssueType.COMPLEXITY`)

- Breaks down complex functions (cognitive complexity ≤15)
- Extracts common patterns into reusable utilities
- Applies dependency injection and Protocol patterns
- **Real Code Transformation**: Actually modifies code structure
- **Confidence**: 0.9 for complexity issues, 0.8 for dead code

**PerformanceAgent** - Primary Expertise: Performance Optimization (`IssueType.PERFORMANCE`)

- Detects and fixes O(n²) complexity patterns
- Transforms `list += [item]` → `list.append(item)`
- Optimizes string building (concatenation → list.append + join)
- Identifies repeated expensive operations in loops
- **AST-based Pattern Recognition**: Accurate detection and transformation

**DRYAgent** - Primary Expertise: Code Duplication (`IssueType.DRY_VIOLATION`)

- Detects duplicate code patterns and repeated functionality
- Suggests extracting common patterns to utility functions
- Recommends base classes or mixins for repeated functionality
- **Core DRY Principle Enforcement**

#### 🔧 Code Quality & Standards Agents

**FormattingAgent** - Primary Expertise: Code Style (`IssueType.FORMATTING`)

- Handles code style and formatting violations
- Fixes import-related formatting issues
- Ensures consistent code formatting standards

**SecurityAgent** - Primary Expertise: Security (`IssueType.SECURITY`)

- Detects and fixes security vulnerabilities (hardcoded paths, unsafe operations)
- Applies security best practices
- Identifies potential security risks in code patterns

**ImportOptimizationAgent** - Primary Expertise: Import Optimization

- Optimizes import statements and organization (`IssueType.IMPORT_ERROR`)
- Removes unused imports and dead code (`IssueType.DEAD_CODE`)
- Consolidates and reorganizes import patterns
- **Real Code Transformation**: Restructures import statements

#### 📝 Documentation & Testing Agents

**DocumentationAgent** - Primary Expertise: Documentation (`IssueType.DOCUMENTATION`)

- Auto-generates changelog entries from git commits during version bumps
- Maintains consistency across all .md files (agent counts, references)
- Updates README examples when APIs change
- Adds newly discovered error patterns to CLAUDE.md
- **Integration**: Works with publish workflow for automatic updates
- **Philosophy Alignment**: Reduces manual documentation maintenance

**TestCreationAgent** - Primary Expertise: Test Failures (`IssueType.TEST_FAILURE`)

- Fixes test failures and missing test dependencies (`IssueType.DEPENDENCY`)
- Improves test coverage and quality
- Handles dependency-related testing issues

**TestSpecialistAgent** - Primary Expertise: Advanced Testing

- Handles complex testing scenarios and fixture management
- Fixes advanced test failures and import issues in test files
- Specializes in testing framework integration

### Agent Coordination System

**AgentCoordinator** (`crackerjack/agents/coordinator.py`) routes issues to appropriate agents:

- **Single-agent mode**: High confidence (≥0.7) issues handled by best-match agent
- **Collaborative mode**: Lower confidence issues processed by multiple agents
- **Batch processing**: Issues grouped by type for efficient parallel processing
- **Confidence scoring**: Each agent provides confidence scores for different issue types

## AI-Powered Iteration Protocol

### Critical Workflow Architecture

Crackerjack implements a **strict iteration protocol** that ensures fixes are applied between iterations:

```
Iteration Cycle (Repeats until success or max 10 iterations):
├── 1. Fast Hooks (formatting) → Retry if needed
├── 2. Collect ALL test failures (don't stop on first)
├── 3. Collect ALL hook issues (don't stop on first)
├── 4. Apply AI fixes for ALL collected issues ⭐ CRITICAL STEP
└── 5. Move to next iteration (validates previous fixes worked)
```

**Key Principle**: **NO EARLY EXIT** during collection phases. All issues are gathered before the AI fixing phase.

### Implementation Details

**Core Implementation**: `AsyncWorkflowOrchestrator._execute_ai_agent_workflow_async()`

```python
for iteration in range(1, max_iterations + 1):
    # Step 1: Fast hooks with retry logic
    fast_hooks_success = await self._run_fast_hooks_with_retry_async(options)

    # Step 2: Collect ALL test issues (don't stop on first)
    test_issues = await self._collect_test_issues_async(options)

    # Step 3: Collect ALL hook issues (don't stop on first)
    hook_issues = await self._collect_comprehensive_hook_issues_async(options)

    # Exit condition: everything passes
    if fast_hooks_success and not test_issues and not hook_issues:
        break

    # Step 4: Apply AI fixes for ALL collected issues
    fix_success = await self._apply_ai_fixes_async(
        options, test_issues, hook_issues, iteration
    )
    if not fix_success:
        return False  # Fail the workflow
```

## MCP Server Integration

### Available MCP Tools

Crackerjack provides comprehensive MCP (Model Context Protocol) integration for AI assistants:

| Tool Category | Tool Name | Purpose |
|---------------|-----------|---------|
| **Execution** | `execute_crackerjack` | Start iterative auto-fixing workflow |
| **Progress** | `get_job_progress` | Get current progress for running jobs |
| **Monitoring** | `get_comprehensive_status` | Get complete system status (servers, jobs, health) |
| **Stages** | `run_crackerjack_stage` | Execute specific workflow stages |
| **Analysis** | `smart_error_analysis` | Intelligent error pattern analysis |
| **Server** | `get_server_stats` | Get MCP server resource usage statistics |

### Slash Commands

**`/crackerjack:run`** - Primary AI Assistant Command

- Executes full iterative auto-fixing with AI agent mode
- Autonomous code quality enforcement (up to 10 iterations)
- Real-time progress tracking via WebSocket
- **Usage**: `/crackerjack:run [--debug]`

**`/crackerjack:status`** - System Health Check

- Comprehensive system status including MCP server health
- WebSocket server status and active jobs
- Resource usage and service health metrics

**`/crackerjack:init`** - Project Initialization

- Initialize or update project configuration
- Intelligent smart merge (preserves existing configurations)
- Never overwrites project identity

## AI Assistant Integration Patterns

### 1. Autonomous Quality Enforcement

**Recommended Primary Workflow**:

```bash
# AI assistant uses this command for complete automation
/crackerjack:run
```

**What happens**:

1. **Multi-iteration fixing**: AI agents automatically detect and fix ALL issues
1. **Real code changes**: Actual modifications to source files (not just detection)
1. **Comprehensive coverage**: Tests, formatting, security, complexity, typing
1. **Zero manual intervention**: Fully autonomous operation

### 2. Progress Monitoring Integration

**WebSocket-based real-time progress**:

- **Server**: Automatically starts on `localhost:8675`
- **Progress URL**: `ws://localhost:8675/ws/progress/{job_id}`
- **Test Interface**: `http://localhost:8675/test`

**MCP Tools for Progress**:

```python
# Start job and get ID
result = execute_crackerjack("/crackerjack:run")
job_id = result["job_id"]

# Monitor progress
progress = get_job_progress(job_id)
```

### 3. Development Workflow Integration

**AI Assistant Workflow**:

1. **Assessment**: Use `/crackerjack:status` to check current project health
1. **Execution**: Use `/crackerjack:run` for autonomous quality improvement
1. **Monitoring**: Track progress via MCP tools or WebSocket
1. **Validation**: AI receives structured results and progress updates

### 4. Custom Integration Patterns

**For AI systems building on Crackerjack**:

```python
from crackerjack import create_crackerjack_runner
from pathlib import Path

# Create AI-optimized runner
runner = create_crackerjack_runner(
    pkg_path=Path.cwd(),
    output_format="json",  # Structured output for AI parsing
)


# Enable AI agent mode
class AIOptions:
    ai_agent = True
    test = True
    verbose = True


# Execute with structured results
result = runner.process(AIOptions())
if result.success:
    # Process structured results programmatically
    for action in result.actions:
        print(f"- {action.name}: {action.status}")
```

## Advanced AI Features

### Intelligent Error Analysis

**Smart Error Pattern Recognition**:

- **Historical Learning**: Tracks common error patterns and successful fixes
- **Context-Aware**: Understands project structure and dependencies
- **Batch Processing**: Analyzes related errors together for coordinated fixes

### Structured Output Generation

**AI-Friendly Data Formats**:

- **JUnit XML**: `test-results.xml` for detailed test outcomes
- **JSON Coverage**: `coverage.json` with line-by-line coverage data
- **Benchmark Data**: `benchmark.json` for performance metrics
- **Console JSON**: Structured status updates during execution

### WebSocket Architecture

**Real-time Communication**:

- **FastAPI-based**: Modern async WebSocket server
- **Job Management**: Background task execution with progress tracking
- **Rich Components**: Formatted progress panels and status displays
- **Graceful Fallback**: Automatic fallback to polling if WebSocket unavailable

## Quality Standards & Enforcement

### Automated Quality Rules

- **Cognitive Complexity**: ≤13 per function (enforced by ComplexityPy)
- **Test Coverage**: 42% minimum requirement (configurable)
- **Security Standards**: No hardcoded paths, secure subprocess calls
- **Type Safety**: Complete type annotations required
- **Import Organization**: Optimized import structure
- **Dead Code**: Zero tolerance for unused code

### AI Agent Capabilities

**What AI Agents Actually Fix**:

- ✅ **Type Errors**: Adds missing type annotations, fixes type mismatches
- ✅ **Security Issues**: Removes hardcoded paths, fixes vulnerabilities
- ✅ **Dead Code**: Removes unused imports, variables, functions
- ✅ **Test Failures**: Fixes missing fixtures, import errors, assertions
- ✅ **Code Quality**: Applies refactoring, reduces complexity
- ✅ **Performance**: Optimizes algorithms and data structures
- ✅ **Documentation**: Updates docs and changelogs automatically

## Environment & Dependencies

### Core Requirements

- **Python**: 3.13+ (modern type hints, performance optimizations)
- **UV**: Modern Python package manager
- **Pre-commit**: Git hook management
- **FastMCP**: MCP server framework (≥2.10.6)

### AI-Specific Dependencies

- **WebSocket Support**: `uvicorn>=0.32.1`, `websockets>=15.0.1`
- **Rich UI**: `rich>=14` for terminal formatting and progress
- **FastAPI**: `fastapi>=0.116.1` for HTTP/WebSocket endpoints

### Installation for AI Integration

```bash
# Standard installation
uv sync

# With development dependencies
uv sync --group dev

# For AI assistant integration
pip install crackerjack[ai-agent]
```

## Configuration for AI Systems

### MCP Server Configuration

**Add to `.mcp.json`**:

```json
{
  "mcpServers": {
    "crackerjack": {
      "command": "python",
      "args": ["-m", "crackerjack", "--start-mcp-server"],
      "cwd": "/path/to/project",
      "env": {
        "PYTHONPATH": "/path/to/project"
      }
    }
  }
}
```

### Environment Variables for AI Mode

```bash
AI_AGENT=1                          # Enable AI agent mode
CRACKERJACK_STRUCTURED_OUTPUT=1     # JSON formatting
PYTEST_REPORT_FORMAT=json           # Structured test results
```

## Best Practices for AI Assistants

### 1. Always Use MCP Tools

- **✅ CORRECT**: Use `/crackerjack:run` or MCP `execute_crackerjack` tool
- **❌ NEVER**: Fall back to bash execution of `python -m crackerjack`

### 2. Monitor Progress Appropriately

- **Short tasks**: Use `--debug` flag for immediate output
- **Long tasks**: Monitor via `get_job_progress` for real-time updates

### 3. Handle Results Intelligently

- **Parse structured output**: Use generated JSON/XML files
- **Understand iterations**: Each iteration validates previous fixes
- **Report progress**: Keep users informed of autonomous fixing progress

### 4. Respect the Philosophy

- **Code minimalism**: Less code is better code
- **Quality over quantity**: Fix root causes, not just symptoms
- **Autonomous operation**: Trust the AI agents to handle complex fixes

## Troubleshooting for AI Systems

### Common Integration Issues

1. **MCP Server Connection**:

   ```bash
   python -c "from crackerjack.mcp.server import mcp; print('✅ MCP ready')"
   ```

1. **WebSocket Server Issues**:

   ```bash
   curl http://localhost:8675/health
   ```

1. **AI Agent Not Fixing Issues**:

   - Check that iteration protocol is being followed
   - Verify fixes are being applied between iterations
   - Ensure batch processing (not early exit on first failure)

### Performance Optimization

- **Use structured output**: Avoid parsing console text
- **Batch operations**: Process multiple issues together
- **Monitor resources**: Check system health via MCP tools
- **Cache results**: Leverage Crackerjack's built-in caching

## Future AI Integration Roadmap

### Enhanced AI Capabilities

- **Semantic Code Understanding**: AI-friendly code structure representations
- **Contextual Learning**: Adaptive fixing based on project patterns
- **Multi-project Coordination**: Cross-project knowledge sharing
- **Custom AI Plugins**: Extensible agent architecture

### Advanced Workflows

- **Interactive AI Fixing**: Multi-step guided processes with feedback
- **Predictive Quality**: Prevent issues before they occur
- **Team AI Integration**: Collaborative AI-assisted development
- **Continuous Quality**: Real-time quality monitoring and fixing

______________________________________________________________________

## Contributing to AI Integration

When adding new AI capabilities:

1. **Follow the iteration protocol** - ensure fixes are applied between iterations
1. **Add MCP tools** - use `@mcp.tool()` decorator with proper documentation
1. **Update slash commands** - add corresponding `@mcp.prompt()` for user access
1. **Test with AI assistants** - validate with Claude, ChatGPT, and other LLMs
1. **Document in AGENTS.md** - update this file with new capabilities

## Security & Privacy

- **Local Processing**: All AI agent processing happens locally
- **No External APIs**: No data sent to external services during fixing
- **Secure Execution**: Input validation and secure subprocess calls
- **Permission Management**: Granular control over trusted operations

______________________________________________________________________

*This AGENTS.md file represents the emerging standard for documenting AI agent integration in development tools. Crackerjack's AI-native architecture demonstrates how autonomous code quality enforcement can be achieved through intelligent multi-agent coordination.*
