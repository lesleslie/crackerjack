# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crackerjack is an opinionated Python project management tool unifying UV, Ruff, pytest, and pre-commit into a single workflow with AI agent integration via MCP.

**Key Dependencies**: Python 3.13+, UV, pre-commit, pytest

**Clean Code Philosophy**: DRY/YAGNI/KISS - Every line is a liability. Optimize for readability with self-documenting code.

## AI Documentation References

- **[AI-REFERENCE.md](AI-REFERENCE.md)** - Command reference with decision trees
- **[AGENT-CAPABILITIES.json](AGENT-CAPABILITIES.json)** - Structured agent data
- **[ERROR-PATTERNS.yaml](ERROR-PATTERNS.yaml)** - Automated issue resolution patterns

## Essential Commands

```bash
# Daily workflow
python -m crackerjack                    # Quality checks
python -m crackerjack -t                 # With tests
python -m crackerjack --ai-agent -t      # AI auto-fixing (recommended)

# Development
python -m crackerjack --ai-debug -t      # Debug AI issues
python -m crackerjack --skip-hooks       # Skip hooks during iteration
python -m crackerjack -x                 # Code cleaning mode

# Server management
python -m crackerjack --start-mcp-server    # MCP server
python -m crackerjack --watchdog            # Monitor/restart services

# Release
python -m crackerjack -a patch              # Full release workflow
```

## AI Agent System

**9 Specialized Agents** handle domain-specific issues:

- **RefactoringAgent** (0.9): Complexity ≤15, dead code removal
- **PerformanceAgent** (0.85): O(n²) detection, optimization
- **SecurityAgent** (0.8): Hardcoded paths, unsafe operations
- **DocumentationAgent** (0.8): Changelog, .md consistency
- **TestCreationAgent** (0.8): Test failures, fixtures
- **DRYAgent** (0.8): Code duplication patterns
- **FormattingAgent** (0.8): Style violations, imports
- **ImportOptimizationAgent**: Import cleanup, reorganization
- **TestSpecialistAgent** (0.8): Advanced testing scenarios

**Usage**: `--ai-agent` enables batch fixing; confidence ≥0.7 uses specific agents

## Architecture

**Modular DI Architecture**: `__main__.py` → `WorkflowOrchestrator` → Coordinators → Managers → Services

**Critical Pattern**: Always import protocols from `models/protocols.py`, never concrete classes

```python
# ❌ Wrong
from ..managers.test_manager import TestManager

# ✅ Correct
from ..models.protocols import TestManagerProtocol
```

**Core Layers**:

- **Orchestration**: `WorkflowOrchestrator`, DI containers, lifecycle management
- **Coordinators**: Session/phase coordination, async workflows, parallel execution
- **Managers**: Hook execution (fast→comprehensive), test management, publishing
- **Services**: Filesystem, git, config, security, health monitoring

## Testing & Development

```bash
# Specific test
python -m pytest tests/test_file.py::TestClass::test_method -v

# Coverage
python -m pytest --cov=crackerjack --cov-report=html

# Custom workers
python -m crackerjack -t --test-workers 4

# Version bump
python -m crackerjack --bump patch
```

## Quality Process

**Workflow Order**:

1. **Fast Hooks** (~5s): formatting, basic checks → retry once if fail
1. **Full Test Suite**: collect ALL failures, don't stop on first
1. **Comprehensive Hooks** (~30s): type checking, security, complexity → collect ALL issues
1. **AI Batch Fixing**: process all collected failures together

**Testing**: pytest with asyncio, 300s timeout, auto-detected workers
**Coverage**: Ratchet system targeting 100%, never decrease

## Code Standards

**Quality Rules**:

- **Complexity ≤15** per function
- **No hardcoded paths** (use `tempfile`)
- **No shell=True** in subprocess
- **Type annotations required**
- **Protocol-based DI**
- **Python 3.13+**: `|` unions, protocols, pathlib

**Refactoring Pattern**: Break complex methods into helpers

```python
def complex_method(self, data: dict) -> bool:
    if not self._validate_input(data):
        return self._handle_invalid_input()
    processed = self._process_data(data)
    return self._save_results(processed)
```

**Critical Regex Safety**: NEVER write raw regex. Use centralized registry:

```python
# ❌ DANGEROUS
text = re.sub(r"(\w+) - (\w+)", r"\g < 1 >-\g < 2 >", text)

# ✅ SAFE
from crackerjack.services.regex_patterns import SAFE_PATTERNS

text = SAFE_PATTERNS["fix_hyphenated_names"].apply(text)
```

## Common Issues & Solutions

**Development**:

- **AI agent ineffective**: Use `--ai-debug -t` for analysis
- **Import errors**: Always import protocols from `models/protocols.py`
- **Test hangs**: Avoid complex async tests, use simple synchronous config tests
- **Coverage failing**: Never reduce below baseline, add tests incrementally
- **Complexity >15**: Break into helper methods using RefactoringAgent approach

**Server**:

- **MCP not starting**: `--restart-mcp-server` or `--watchdog`
- **Terminal stuck**: `stty sane; reset; exec $SHELL -l`
- **Slow tests**: Customize `--test-workers N` or use `--skip-hooks`

## MCP Server Integration

**Features**: Dual protocol (MCP + WebSocket), real-time progress, job tracking

```bash
# Start server
python -m crackerjack --start-mcp-server

# Monitor progress at http://localhost:8675/
python -m crackerjack.mcp.progress_monitor <job_id>
```

**Available Tools**: `execute_crackerjack`, `get_job_progress`, `get_comprehensive_status`, `analyze_errors`

**Slash Commands**: `/crackerjack:run`, `/crackerjack:status`, `/crackerjack:init`

## Critical Reminders

**Core Instructions**:

- Do only what's asked, nothing more
- NEVER create files unless absolutely necessary
- ALWAYS prefer editing existing files
- MAINTAIN coverage ratchet

**Quality Standards**:

- **Test Quality**: Avoid async tests that hang, use synchronous config tests
- **Import Compliance**: Use protocols from `models/protocols.py`
- **Fix failures FIRST** before creating new tests
- Use IDE diagnostics after implementation

**Failure Patterns to Avoid**:

```python
# ❌ Async tests that hang
@pytest.mark.asyncio
async def test_batch_processing(self, batched_saver):
    await batched_saver.start()  # Can hang


# ✅ Simple synchronous tests
def test_batch_configuration(self, batched_saver):
    assert batched_saver.max_batch_size == expected_size


# ❌ Import concrete classes
from ..managers.test_manager import TestManager

# ✅ Import protocols
from ..models.protocols import TestManagerProtocol
```

**Current Status**: 10.11% coverage baseline targeting 100% (ratchet system: 2% tolerance, never reduce)
