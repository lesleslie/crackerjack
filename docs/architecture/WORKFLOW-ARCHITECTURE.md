# Crackerjack Workflow Architecture

This document describes the complete workflow architecture for crackerjack's AI-powered code fixing system, including MCP integration with session-mgmt-mcp.

## Table of Contents

1. [Overview](<#overview>)
1. [Current Workflow (Basic Mode)](<#current-workflow-basic-mode>)
1. [New Auto-Fix Workflow (AI Mode)](<#new-auto-fix-workflow-ai-mode>)
1. [MCP Integration Flow](<#mcp-integration-flow>)
1. [Component Architecture](<#component-architecture>)
1. [Security Layers](<#security-layers>)
1. [Iteration Loop Design](<#iteration-loop-design>)

______________________________________________________________________

## Overview

Crackerjack provides two execution modes:

1. **Basic Mode**: Runs pre-commit hooks and reports failures (existing functionality)
1. **AI Mode**: Iteratively fixes code issues using Claude AI (new implementation)

Both modes integrate with the MCP (Model Context Protocol) server for remote execution via session-mgmt-mcp.

______________________________________________________________________

## Current Workflow (Basic Mode)

### Execution Path

```
User Command → MCP Server → Input Validation → Crackerjack CLI →
Pre-commit Hooks → Parse Results → Return to User
```

### Workflow Diagram

> **Note**: Workflow diagrams are planned for future documentation updates.

### Steps

1. **User Input**: User runs `/run` or calls `crackerjack_run(command="test")`
1. **MCP Server**: session-mgmt-mcp receives request
1. **Input Validation**: `validate_command()` ensures semantic command format
1. **Execution**: Crackerjack CLI runs pre-commit hooks
1. **Parsing**: Hook output parsed using reverse-parsing algorithm
1. **Results**: Formatted results returned to user

### Key Components

**Input Validator** (`crackerjack/cli/facade.py`):

- Validates command parameter (must be semantic, not flags)
- Rejects `--ai-fix` in wrong places
- Uses `shlex.split()` for shell argument parsing
- Returns `(validated_command, parsed_args)`

**Hook Parser** (`session_mgmt_mcp/tools/hook_parser.py`):

- Reverse parsing: `rsplit(maxsplit=1)` then `rstrip(".")`
- Handles hook names with dots (e.g., `test.integration.api`)
- Status markers: `✅`/`Passed` or `❌`/`Failed`
- Returns `List[HookResult(name, passed)]`

______________________________________________________________________

## New Auto-Fix Workflow (AI Mode)

### Execution Path

```
User Command (ai_agent_mode=True) → MCP Server → AutoFixWorkflow →
Iteration Loop [Run Hooks → Parse → Fix Issues → Verify] →
Convergence or Max Iterations → Return Results
```

### Workflow Diagram

> **Note**: Workflow diagrams are planned for future documentation updates.

### Iteration Loop

The workflow runs in an iterative cycle:

```python
for iteration in range(1, max_iterations + 1):
    # 1. Run hooks
    hook_results = run_pre_commit_hooks()

    # 2. Check convergence
    if all_hooks_passed(hook_results):
        return success("Convergence achieved!")

    # 3. Apply AI fixes for failures
    for failed_hook in hook_results.failures:
        fix_result = apply_ai_fix(failed_hook)

    # 4. Continue to next iteration
```

### Maximum Iterations

- **Default**: 10 iterations
- **Convergence**: Stops early if all hooks pass
- **Partial Success**: Returns after max iterations with remaining issues

______________________________________________________________________

## MCP Integration Flow

### Sequence Diagram: Basic Mode

> **Note**: Sequence diagrams are planned for future documentation updates.

### Sequence Diagram: AI Mode

> **Note**: Sequence diagrams are planned for future documentation updates.

### MCP Parameter Validation

The MCP server validates inputs before execution:

```python
# ✅ CORRECT
crackerjack_run(command="test", ai_agent_mode=True)

# ❌ WRONG - Will raise ValueError
crackerjack_run(command="--ai-fix -t")
```

**Validation Rules**:

1. `command` must be semantic (test, lint, check, etc.)
1. `command` cannot start with `--` or `-`
1. `args` cannot contain `--ai-fix` (use `ai_agent_mode=True` instead)

______________________________________________________________________

## Component Architecture

### Layer 1: Input Validation

**File**: `crackerjack/cli/facade.py`

```python
def validate_command(command: str | None, args: str | None) -> tuple[str, list[str]]:
    """Validate command and detect common misuse patterns."""
    # 1. Check for None
    # 2. Reject flags in command
    # 3. Validate against known commands
    # 4. Check for --ai-fix in args
    # 5. Return validated tuple
```

**Security**: Prevents command injection, validates semantic interface

### Layer 2: AI Adapter

**File**: `crackerjack/adapters/ai/claude.py`

```python
class ClaudeCodeFixer(CleanupMixin):
    """Real AI-powered code fixing using Claude API."""

    async def fix_code_issue(
        self,
        file_path: str,
        issue_description: str,
        code_context: str,
        fix_type: str,
    ) -> dict[str, str | float | list[str] | bool]:
        """Generate code fix using Claude AI."""
        # 1. Sanitize inputs (prevent prompt injection)
        # 2. Call Claude API with structured prompt
        # 3. Parse JSON response
        # 4. Validate AI-generated code (regex + AST)
        # 5. Return structured result
```

**Security Features**:

- Prompt injection prevention via `_sanitize_prompt_input()`
- AI code validation via `_validate_ai_generated_code()`
- Error sanitization via `_sanitize_error_message()`
- API key format validation
- Retry logic with exponential backoff

### Layer 3: File Modification Service

**File**: `crackerjack/services/file_modifier.py`

```python
class SafeFileModifier:
    """Safely modify files with backup and validation."""

    async def apply_fix(
        self,
        file_path: str,
        original_content: str,
        fixed_content: str,
        dry_run: bool = False,
        create_backup: bool = True,
    ) -> dict[str, bool | str | None]:
        """Apply code fix with safety checks."""
        # 1. Validate file path (symlinks, traversal, size)
        # 2. Create backup with timestamp
        # 3. Atomic write (temp → fsync → rename)
        # 4. Preserve permissions
        # 5. Rollback on errors
```

**Security Features**:

- Symlink detection (direct + path chain)
- Path traversal prevention
- Forbidden file patterns (`.env`, `.git/*`, SSH keys)
- Atomic write operations (prevents partial writes)
- File size limits (10MB default)
- Automatic rollback on errors

### Layer 4: Integration Bridge

**File**: `crackerjack/agents/claude_code_bridge.py`

```python
class ClaudeCodeBridge:
    """Integration between issue detection and AI fixing."""

    async def consult_on_issue(self, issue: Issue) -> FixResult:
        """Coordinate AI fix for an issue."""
        # 1. Extract issue details
        # 2. Call AI adapter
        # 3. Validate confidence (>= 0.7)
        # 4. Apply fix via SafeFileModifier
        # 5. Return FixResult
```

**Responsibilities**:

- Orchestrates AI adapter + file modifier
- Enforces confidence thresholds
- Handles dry-run mode
- Generates structured FixResult

### Layer 5: Workflow Orchestration

**File**: `crackerjack/workflows/auto_fix.py` (To be implemented)

```python
class AutoFixWorkflow:
    """Iterative auto-fix workflow."""

    async def run(
        self,
        command: str,
        max_iterations: int = 10,
    ) -> dict[str, bool | list | int | str]:
        """Run iterative auto-fix workflow."""
        # 1. Initialize iteration counter
        # 2. Loop: run hooks → fix issues → verify
        # 3. Check convergence (all hooks pass)
        # 4. Return results with iteration history
```

**Convergence Criteria**:

- All hooks pass: Success
- Max iterations reached: Partial success
- No fixes applied: Cannot make progress

______________________________________________________________________

## Security Layers

The system implements defense-in-depth with **7 security layers**:

### 1. Input Validation

- Validates all user inputs
- Prevents command injection
- Sanitizes shell arguments

### 2. Prompt Injection Prevention

- Filters system instruction overrides
- Blocks role injection attempts
- Escapes markdown code blocks

### 3. AI Code Validation

**Regex Scanning** for dangerous patterns:

- `eval()`, `exec()` calls
- `subprocess.shell=True`
- `os.system()` commands
- `pickle` deserialization
- Unsafe YAML loading

**AST Parsing** for malicious constructs:

- Dangerous function calls
- Dynamic imports
- Code compilation

### 4. Confidence Thresholds

- Minimum confidence: 0.7 (70%)
- Rejects low-confidence fixes
- Prevents unreliable changes

### 5. File Path Validation

- Symlink detection (direct + parents)
- Path traversal prevention
- Forbidden file patterns
- File size limits

### 6. Atomic Operations

- Write-to-temp-then-rename
- `fsync()` before rename
- Prevents partial writes
- Automatic cleanup on errors

### 7. Error Sanitization

- Removes file paths
- Redacts API keys
- Scrubs secrets
- Prevents information leakage

______________________________________________________________________

## Iteration Loop Design

### Convergence Algorithm

```python
MAX_ITERATIONS = 10
iteration = 0
all_passing = False

while iteration < MAX_ITERATIONS and not all_passing:
    iteration += 1

    # Run hooks
    results = run_hooks(command)

    # Check convergence
    if results.all_passing:
        all_passing = True
        break

    # Apply fixes
    fixes_applied = 0
    for failure in results.failures:
        fix = apply_ai_fix(failure)
        if fix.success:
            fixes_applied += 1

    # Check progress
    if fixes_applied == 0:
        # Cannot make progress
        break

return {
    "success": all_passing,
    "iterations": iteration,
    "final_status": "converged" if all_passing else "incomplete",
}
```

### Iteration Data Structure

```python
@dataclass
class FixIteration:
    iteration_num: int
    hooks_run: list[str]
    issues_found: int
    fixes_applied: int
    fixes_successful: int
    hooks_passing: list[str]
    hooks_failing: list[str]
```

### Progress Tracking

Each iteration records:

- Which hooks were run
- How many issues found
- How many fixes attempted
- How many fixes succeeded
- Current pass/fail status

### Early Termination Conditions

1. **Convergence**: All hooks pass
1. **Max Iterations**: Reached limit (10 by default)
1. **No Progress**: No fixes applied in iteration
1. **Critical Failure**: Security violation or API error

______________________________________________________________________

## File Locations

### Crackerjack Project

```
crackerjack/
├── cli/
│   └── facade.py              # Input validation
├── adapters/
│   └── ai/
│       ├── __init__.py
│       └── claude.py          # AI adapter (773 lines)
├── services/
│   └── file_modifier.py       # File operations (495 lines)
├── agents/
│   └── claude_code_bridge.py  # Integration bridge
└── workflows/
    └── auto_fix.py            # Iteration workflow (to implement)
```

### Session-Mgmt-MCP Project

```
session_mgmt_mcp/
└── tools/
    ├── crackerjack_tools.py   # MCP integration
    └── hook_parser.py         # Hook output parsing
```

______________________________________________________________________

## Configuration

### Environment Variables

```bash
# Required for AI mode
export ANTHROPIC_API_KEY=sk-ant-...

# Optional configuration
export CRACKERJACK_MAX_ITERATIONS=10
export CRACKERJACK_CONFIDENCE_THRESHOLD=0.7
export CRACKERJACK_MAX_FILE_SIZE=10485760  # 10MB
```

### Settings Files

**`settings/adapters.yml`**:

```yaml
ai: claude
```

**`settings/ai.yml`** (optional overrides):

```yaml
anthropic:
  model: claude-sonnet-4-5-20250929
  max_tokens: 4096
  temperature: 0.1
  confidence_threshold: 0.7
  max_retries: 3
```

______________________________________________________________________

## Usage Examples

### Basic Mode (No AI)

```bash
# Direct CLI
python -m crackerjack test

# Via MCP
crackerjack_run(command="test")
```

### AI Mode (Auto-Fix)

```bash
# Direct CLI
python -m crackerjack test --ai-fix

# Via MCP (CORRECT)
crackerjack_run(command="test", ai_agent_mode=True)

# Via MCP (WRONG - will error)
crackerjack_run(command="--ai-fix -t")  # ❌ ValueError!
```

### Dry-Run Mode

```bash
# Preview fixes without applying
python -m crackerjack test --ai-fix --dry-run

# Via MCP
crackerjack_run(command="test", args="--dry-run", ai_agent_mode=True)
```

______________________________________________________________________

## Performance Characteristics

### Basic Mode

- **Execution time**: 2-30 seconds (depends on hooks)
- **API calls**: 0
- **File modifications**: 0

### AI Mode (per iteration)

- **Execution time**: 10-60 seconds per iteration
- **API calls**: 1 per failed hook
- **File modifications**: Up to N (number of failures)
- **Total time**: 2-10 minutes for typical workflows

### Optimization Strategies

1. **Parallel Fixes**: Process multiple hooks concurrently
1. **Caching**: Cache AI responses for identical issues
1. **Batch Operations**: Group similar fixes together
1. **Early Termination**: Stop at first convergence

______________________________________________________________________

## Monitoring & Observability

### Log Levels

- **DEBUG**: Detailed execution flow, API calls
- **INFO**: Iteration progress, fixes applied
- **WARNING**: Low confidence, retries
- **ERROR**: API failures, validation errors

### Key Metrics

- Success rate per hook type
- Average iterations to convergence
- AI confidence distribution
- API latency and costs
- File modification success rate

______________________________________________________________________

## Future Enhancements

### Planned Features

1. **Learning System**: Track fix success rates by issue type
1. **Confidence Tuning**: Auto-adjust thresholds based on history
1. **Parallel Processing**: Fix multiple issues concurrently
1. **Response Caching**: Reuse fixes for identical issues
1. **Custom Prompts**: Per-hook prompt customization
1. **Integration Tests**: Verify fixes with test suite
1. **Rollback All**: Undo all changes in iteration

### Architecture Extensions

1. **Plugin System**: Custom fix providers
1. **Multi-LLM Support**: Fallback to other AI providers
1. **Distributed Execution**: Run iterations across machines
1. **Incremental Fixes**: Apply fixes file-by-file

______________________________________________________________________

## Troubleshooting

### Common Issues

**Issue**: "Command cannot be None"

- **Cause**: Invalid MCP call
- **Fix**: Ensure `command` parameter is provided

**Issue**: "Invalid command: '--ai-fix'"

- **Cause**: Flags in command parameter
- **Fix**: Use `ai_agent_mode=True` instead

**Issue**: "Security violation detected"

- **Cause**: AI generated dangerous code
- **Fix**: Review AI output manually, adjust prompts

**Issue**: "Low confidence, skipping fix"

- **Cause**: AI not confident in fix
- **Fix**: Manually fix or adjust confidence threshold

**Issue**: "Max iterations reached"

- **Cause**: Issues cannot be auto-fixed
- **Fix**: Manually fix remaining issues

______________________________________________________________________

## References

- [Implementation Plan](/Users/les/Projects/acb/CRACKERJACK-FIX-IMPLEMENTATION-PLAN.md)
- [Architecture Design](/Users/les/Projects/acb/AI-CODE-FIXING-ARCHITECTURE.md)
- [ACB Framework](https://github.com/lesleslie/acb)
- [Session-Mgmt-MCP](https://github.com/lesleslie/session-mgmt-mcp)

______________________________________________________________________

**Last Updated**: 2025-01-03
**Version**: 2.0
**Status**: In Development (Phase 1.2 Complete)
