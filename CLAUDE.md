# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crackerjack is an opinionated Python project management tool unifying UV, Ruff, pytest, and pre-commit into a single workflow with AI agent integration via MCP.

**Key Dependencies**: Python 3.13+, UV, pre-commit, pytest

**Clean Code Philosophy**: DRY/YAGNI/KISS - Every line is a liability. Optimize for readability with self-documenting code.

## CRITICAL SECURITY & QUALITY RULES

### 1. NEVER MAKE UNAUTHORIZED CHANGES

- **ONLY** modify what is explicitly requested.
- **NEVER** change unrelated code, files, or functionality.
- If you think something else needs changing, **ASK FIRST**.
- Changing anything not explicitly requested is considered **prohibited change**.

### 2. DEPENDENCY MANAGEMENT IS MANDATORY

- **ALWAYS** update package.json/requirements.txt or pyproject.toml when adding imports.
- **NEVER** add import statements without corresponding dependency entries.
- **VERIFY** all dependencies are properly declared before suggesting code.

### 3. NO PLACEHOLDERS - EVER

- **NEVER** use placeholder values like "YOUR_API_KEY", "TODO", or dummy data.
- **ALWAYS** use proper variable references or configuration patterns.
- If real values are needed, **ASK** for them explicitly.
- Use environment variables or config files, not hardcoded values.

### 4. QUESTION VS CODE REQUEST DISTINCTION

- When a user asks a **QUESTION**, provide an **ANSWER** - do NOT change code.
- Only modify code when explicitly requested with phrases like "change", "update", "modify", "fix".
- **NEVER** assume a question is a code change request.

### 5. NO ASSUMPTIONS OR GUESSING

- If information is missing, **ASK** for clarification.
- **NEVER** guess library versions, API formats, or implementation details.
- **NEVER** make assumptions about user requirements or use cases.
- State clearly what information you need to proceed.

### 6. SECURITY IS NON-NEGOTIABLE

- **NEVER** put API keys, secrets, or credentials in client-side code.
- **ALWAYS** implement proper authentication and authorization.
- **ALWAYS** use environment variables for sensitive data.
- **ALWAYS** implement proper input validation and sanitization.
- **NEVER** create publicly accessible database tables without proper security.
- **ALWAYS** implement row-level security for database access.

### 7. CAPABILITY HONESTY

- **NEVER** attempt to generate images, audio, or other media.
- If asked for capabilities you don't have, state limitations clearly.
- **NEVER** create fake implementations of impossible features.
- Suggest proper alternatives using appropriate libraries/services.

### 8. PRESERVE FUNCTIONAL REQUIREMENTS

- **NEVER** change core functionality to "fix" errors.
- When encountering errors, fix the technical issue, not the requirements.
- If requirements seem problematic, **ASK** before changing them.
- Document any necessary requirement clarifications.

### 9. EVIDENCE-BASED RESPONSES

- When asked if something is implemented, **SHOW CODE EVIDENCE**.
- Format: "Looking at the code: [filename] (lines X-Y): [relevant code snippet]"
- **NEVER** guess or assume implementation status.
- If unsure, **SAY SO** and offer to check specific files.

### 10. NO HARDCODED EXAMPLES

- **NEVER** hardcode example values as permanent solutions.
- **ALWAYS** use variables, parameters, or configuration for dynamic values.
- If showing examples, clearly mark them as examples, not implementation.

### 11. INTELLIGENT LOGGING IMPLEMENTATION

- **AUTOMATICALLY** add essential logging to understand core application behavior.
- Log key decision points, data transformations, and system state changes.
- **NEVER** over-log (avoid logging every variable or trivial operations).
- **NEVER** under-log (ensure critical flows are traceable).
- Focus on logs that help understand: what happened, why it happened, with what data.
- Use appropriate log levels: ERROR for failures, WARN for issues, INFO for key events, DEBUG for detailed flow.
- **ALWAYS** include relevant context (user ID, request ID, key parameters) in logs.
- Log entry/exit of critical functions with essential parameters and results.

## RESPONSE PROTOCOLS

### When Uncertain:

- State: "I need clarification on [specific point] before proceeding."
- **NEVER** guess or make assumptions.
- Ask specific questions to get the information needed.

### When Asked "Are You Sure?":

- Re-examine the code thoroughly.
- Provide specific evidence for your answer.
- If uncertain after re-examination, state: "After reviewing, I'm not certain about [specific aspect]. Let me check [specific file/code section]."
- **MAINTAIN CONSISTENCY** - don't change answers without new evidence.

### Error Handling:

- **ANALYZE** the actual error message/response.
- **NEVER** assume error causes (like rate limits) without evidence.
- Ask the user to share error details if needed.
- Provide specific debugging steps.

### Code Cleanup:

- **ALWAYS** remove unused code when making changes.
- **NEVER** leave orphaned functions, imports, or variables.
- Clean up any temporary debugging code automatically.

## MANDATORY CHECKS BEFORE RESPONDING

Before every response, verify:

- [ ] Am I only changing what was explicitly requested?
- [ ] Are all new imports added to dependency files?
- [ ] Are there any placeholder values that need real implementation?
- [ ] Is this a question that needs an answer, not code changes?
- [ ] Am I making any assumptions about missing information?
- [ ] Are there any security vulnerabilities in my suggested code?
- [ ] Am I claiming capabilities I don't actually have?
- [ ] Am I preserving all functional requirements?
- [ ] Can I provide code evidence for any implementation claims?
- [ ] Are there any hardcoded values that should be variables?

## VIOLATION CONSEQUENCES

Violating any of these rules is considered a **CRITICAL ERROR** that can:

- Break production applications
- Introduce security vulnerabilities
- Waste significant development time
- Compromise project integrity

## EMERGENCY STOP PROTOCOL

If you're unsure about ANY aspect of a request:

1. **STOP** code generation.
1. **ASK** for clarification.
1. **WAIT** for explicit confirmation.
1. Only proceed when 100% certain.

Remember: It's better to ask for clarification than to make assumptions that could break everything.

## AI Documentation References

- **[AI-REFERENCE.md](docs/ai/AI-REFERENCE.md)** - Command reference with decision trees
- **[AGENT-CAPABILITIES.json](AGENT-CAPABILITIES.json)** - Structured agent data
- **[ERROR-PATTERNS.yaml](ERROR-PATTERNS.yaml)** - Automated issue resolution patterns

## Essential Commands

```bash
# Daily workflow
python -m crackerjack                       # Quality checks
python -m crackerjack --run-tests            # With tests
python -m crackerjack --ai-fix --run-tests   # AI auto-fixing (recommended)

# Development
python -m crackerjack --ai-debug --run-tests # Debug AI issues
python -m crackerjack --skip-hooks           # Skip hooks during iteration
python -m crackerjack --strip-code           # Code cleaning mode

# Monitoring & Performance
python -m crackerjack --dashboard            # Comprehensive monitoring dashboard
python -m crackerjack --unified-dashboard    # Unified real-time dashboard
python -m crackerjack --monitor              # Multi-project progress monitor
python -m crackerjack --benchmark            # Run in benchmark mode
python -m crackerjack --cache-stats          # Display cache statistics
python -m crackerjack --clear-cache          # Clear all caches

# Server management
python -m crackerjack --start-mcp-server     # MCP server
python -m crackerjack --restart-mcp-server   # Restart MCP server
python -m crackerjack --watchdog             # Monitor/restart services

# Release
python -m crackerjack --full-release patch  # Full release workflow
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

**Usage**: `--ai-fix` enables batch fixing; confidence ≥0.7 uses specific agents

## Advanced Services (Enabled by Default)

Crackerjack now includes sophisticated intelligence services that enhance the development experience automatically:

### 🧠 Smart Commit Messages (Default)

- **AI-Powered Analysis**: Analyzes staged changes using conventional commit patterns
- **Context-Aware**: Considers file types, change patterns, and scope for descriptive messages
- **Automatic Detection**: Identifies breaking changes, features, fixes, and refactoring
- **Fallback Option**: Use `--basic-commit` to disable smart messages when needed

### 📈 Version Intelligence (Integrated)

- **Semantic Analysis**: AI recommends version bumps (major/minor/patch) based on commits
- **Breaking Change Detection**: Automatically identifies API-breaking changes
- **Conventional Commits**: Analyzes feat/fix/breaking patterns with confidence scoring
- **Interactive Mode**: Use `--bump interactive` to see AI recommendations during selection

### 📝 Changelog Automation (Default)

- **Git History Analysis**: Automatically generates changelog entries from commits
- **Categorized Entries**: Groups changes by type (Added, Fixed, Changed, etc.)
- **Version Integration**: Updates changelog during version bumps and publishing
- **Markdown Generation**: Creates properly formatted CHANGELOG.md entries

### 🎯 Quality Intelligence (Active)

- **Anomaly Detection**: ML-based quality trend analysis and early warning system
- **Pattern Recognition**: Identifies improvement/regression patterns in code quality
- **Workflow Decisions**: Influences hook selection based on quality history
- **Predictive Analytics**: Recommends comprehensive vs. fast quality checks intelligently

### ⚡ Performance Benchmarks (Reporting)

- **Real-time Metrics**: Tracks workflow execution time and resource usage
- **Improvement Analysis**: Shows performance gains from optimizations and caching
- **Memory Optimization**: Reports cache hit ratios and memory efficiency metrics
- **Historical Trends**: Maintains performance baselines for comparison

**Integration Benefits**:

- All services work together seamlessly with graceful fallbacks
- Zero configuration required - intelligent defaults work out of the box
- Enhanced developer experience with minimal performance impact
- Comprehensive quality assurance with intelligent automation

## High-Performance Rust Integration

**Ultra-Fast Static Analysis** with seamless Python integration:

- **🦅 Skylos**: Dead code detection **20x faster** than vulture
- **🔍 Zuban**: Type checking **20-200x faster** than pyright
- **🚀 Performance**: 6,000+ operations/second throughput
- **🔄 Compatibility**: Zero breaking changes, drop-in replacements

**Benefits in Daily Workflow**:

- Pre-commit hooks complete in seconds instead of minutes
- `--run-tests` now blazingly fast with Rust-powered type checking
- AI agents get faster feedback for more efficient fixing cycles
- Development iteration speed dramatically improved

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
python -m crackerjack --run-tests --test-workers 4

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

- **AI agent ineffective**: Use `--ai-debug --run-tests` for analysis
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

## Session Management Integration

**Automatic Lifecycle**: Crackerjack projects (git repositories) get automatic session management via session-mgmt-mcp:

- **Session Start**: Automatically initialized when Claude Code connects
- **Mid-Session**: `/session-mgmt:checkpoint` performs quality checks with intelligent auto-compaction
- **Session End**: Automatically executed on `/quit`, disconnect, or crash with graceful cleanup

**Enhanced Workflow Integration**:

```bash
# Standard crackerjack workflow with automatic session management
python -m crackerjack --ai-fix --run-tests  # Quality + AI fixing
# Session checkpoints happen automatically during long runs
# Session cleanup happens automatically when you quit Claude Code
```

**Key Features**:

- **Crash Resilience**: Session data preserved through network/system failures
- **Memory Management**: Auto-compaction during checkpoints when context is heavy
- **Progress Continuity**: Next session resumes with accumulated learning from previous work
- **Zero Manual Intervention**: All session lifecycle managed automatically for git repos

**Manual Override**: Use `/session-mgmt:init`, `/session-mgmt:checkpoint`, `/session-mgmt:end` if needed for fine control

**Integration Benefits**:

- Crackerjack quality metrics tracked over time
- Test patterns and failure resolutions remembered
- Error fix strategies learned and suggested
- Command effectiveness optimized based on history

## Experimental Features

**Framework for Future Innovations**: Crackerjack includes a comprehensive experimental features framework designed to safely evaluate and integrate next-generation tools.

### Experimental Hook Framework

The experimental hook system provides a structured pathway for evaluating new tools before promoting them to stable status:

```bash
# Framework supports experimental evaluation
python -m crackerjack --experimental-hooks  # (when experimental hooks are available)
```

**Evaluation Criteria**:

1. **Availability**: Tool consistently available across environments
1. **Stability**: No crashes or inconsistent results across runs
1. **Value Added**: Catches issues not found by existing tools
1. **Performance**: Stays within time budgets
1. **Integration**: Works reliably with pre-commit workflow

**Promotion Lifecycle**:

1. **Experimental Phase**: Limited to `manual` stage only
1. **Evaluation Period**: 30-90 day assessment with metrics
1. **Promotion Decision**: Move to appropriate tier if criteria met
1. **Removal**: Clean removal if criteria not met

**Current Status**:

- **No Active Experimental Hooks**: Previous experimental candidates (pyrefly, ty) failed availability testing and were removed
- **Framework Ready**: System prepared for future experimental tool evaluation
- **Documentation**: Complete evaluation criteria in [EXPERIMENTAL-EVALUATION.md](EXPERIMENTAL-EVALUATION.md)

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

- make sure to run `python -m crackerjack` after every editing/debugging cycle for quality checking
- always put implementation plans in a md doc for review and reference
- think when you need to think, think harder when you need to think harder

# Test debug logging
