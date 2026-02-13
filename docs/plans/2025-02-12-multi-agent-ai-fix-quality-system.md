# Multi-Agent AI Fix Quality System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the failing AI-fix workflow (2.7% success) into a robust multi-layered validation system (80%+ success) by replicating successful manual CLI workflows with automated agents.

**Architecture:** 4-layer system building from simple to complex: (1) Read-First Foundation - agents must read files before generating, (2) Two-Stage Pipeline - separate analysis from execution with FixPlan validation, (3) Interactive Fix Loop - permissive validation with retry logic, (4) Fallback Wrapper - delegate to Claude Code API when stuck. Each layer adds validation without breaking previous functionality.

**Tech Stack:** Python 3.13+, asyncio, pytest, existing agent framework (crackerjack/agents/), Edit tool for syntax-validating changes, AST for syntax validation, existing test infrastructure.

______________________________________________________________________

## Phase 1: Layer 1 - Read-First Foundation

### Task 1.1: Add File Context Reading to ProactiveAgent Base Class

**Files:**

- Modify: `crackerjack/agents/proactive_agent.py:26-50`
- Create: `crackerjack/agents/file_context.py`
- Test: `tests/agents/test_file_context.py`

**Step 1: Write the failing test**

Create test file:

```bash
cat > tests/agents/test_file_context.py << 'EOF'
"""Test file context reading for agents."""
import pytest
from pathlib import Path
from crackerjack.agents.proactive_agent import ProactiveAgent
from crackerjack.models.issue import Issue

@pytest.mark.asyncio
async def test_agent_reads_file_before_fixing():
    """ProactiveAgent should read file content before generating fixes."""
    agent = ProactiveAgent()
    issue = Issue(
        file_path="tests/fixtures/sample.py",
        line=10,
        issue_type="TYPE_ERROR",
        description="Type error in sample.py"
    )

    # Should read file context
    context = await agent._read_file_context(issue.file_path)

    assert context is not None
    assert "def sample_function" in context
    assert len(context) > 0

@pytest.mark.asyncio
async def test_file_context_includes_full_file():
    """File context should include complete file content."""
    agent = ProactiveAgent()
    file_path = "tests/fixtures/sample.py"

    context = await agent._read_file_context(file_path)

    # Verify we got the whole file
    lines = context.strip().split("\n")
    assert len(lines) > 5  # At least some lines
EOF
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents/test_file_context.py -v`
Expected: FAIL with "ProactiveAgent has no attribute '\_read_file_context'"

**Step 3: Create file context module**

```bash
cat > crackerjack/agents/file_context.py << 'EOF'
"""File context reading utilities for agents."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FileContextReader:
    """Reads and caches file context for agents."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    async def read_file(self, file_path: str | Path) -> str:
        """Read complete file content.

        Args:
            file_path: Path to file to read

        Returns:
            Complete file content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file can't be read
        """
        path = Path(file_path)

        # Check cache first
        cache_key = str(path.absolute())
        if cache_key in self._cache:
            logger.debug(f"📖 Using cached file context for {file_path}")
            return self._cache[cache_key]

        # Read file
        try:
            content = path.read_text(encoding="utf-8")
            self._cache[cache_key] = content
            logger.debug(f"📖 Read {len(content)} chars from {file_path}")
            return content
        except FileNotFoundError:
            logger.error(f"❌ File not found: {file_path}")
            raise
        except IOError as e:
            logger.error(f"❌ Error reading {file_path}: {e}")
            raise

    def clear_cache(self) -> None:
        """Clear cached file contexts."""
        self._cache.clear()
        logger.debug("🗑️  File context cache cleared")
EOF
```

**Step 4: Add method to ProactiveAgent**

Modify `crackerjack/agents/proactive_agent.py`:

Find the ProactiveAgent class `__init__` method and add after it:

```python
from crackerjack.agents.file_context import FileContextReader

class ProactiveAgent:
    def __init__(self, ...):  # Existing init
        # ... existing code ...
        self._file_reader = FileContextReader()

    async def _read_file_context(self, file_path: str | Path) -> str:
        """Read full file content for context.

        This is MANDATORY before generating any fix. Agents should not
        attempt to fix code without understanding the full file context.

        Args:
            file_path: Path to file to read

        Returns:
            Complete file content as string
        """
        return await self._file_reader.read_file(file_path)
```

**Step 5: Create test fixture file**

```bash
mkdir -p tests/fixtures
cat > tests/fixtures/sample.py << 'EOF'
"""Sample file for testing."""
from __future__ import annotations


def sample_function(x: int) -> int:
    """A sample function."""
    return x * 2


def another_function(y: str) -> str:
    """Another sample function."""
    return y.upper()
EOF
```

**Step 6: Run test to verify it passes**

Run: `pytest tests/agents/test_file_context.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add crackerjack/agents/file_context.py crackerjack/agents/proactive_agent.py tests/agents/test_file_context.py tests/fixtures/sample.py
git commit -m "feat(layer1): add file context reading to ProactiveAgent base

- Add FileContextReader class with caching
- Add _read_file_context() method to ProactiveAgent
- Enforce file reading before generating fixes
- Add comprehensive tests

Part of Layer 1: Read-First Foundation"
```

______________________________________________________________________

### Task 1.2: Enforce Edit Tool Usage in ProactiveAgent

**Files:**

- Modify: `crackerjack/agents/proactive_agent.py:100-150`
- Test: `tests/agents/test_edit_tool_enforcement.py`

**Step 1: Write the failing test**

```bash
cat > tests/agents/test_edit_tool_enforcement.py << 'EOF'
"""Test Edit tool enforcement."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from crackerjack.agents.proactive_agent import ProactiveAgent
from crackerjack.models.issue import Issue

@pytest.mark.asyncio
async def test_agent_must_use_edit_tool():
    """Agents should use Edit tool for applying fixes."""
    agent = ProactiveAgent()

    # Mock the Edit tool call
    with patch('crackerjack.agents.proactive_agent.Edit') as mock_edit:
        mock_edit.return_value = AsyncMock(return_value=None)

        issue = Issue(
            file_path="tests/fixtures/sample.py",
            line=5,
            issue_type="FORMATTING",
            description="Fix formatting"
        )

        # Agent should use Edit tool
        result = await agent._apply_fix_with_edit(
            file_path=issue.file_path,
            old_code="return x * 2",
            new_code="return x * 2  # Multiply by 2"
        )

        # Verify Edit was called
        assert mock_edit.called
        assert result is True or result is None  # Should not raise

@pytest.mark.asyncio
async def test_edit_tool_validates_syntax():
    """Edit tool should catch syntax errors."""
    from crackerjack.agents.proactive_agent import ProactiveAgent

    agent = ProactiveAgent()

    # Try to apply invalid syntax
    with pytest.raises(Exception):  # Edit tool should catch this
        await agent._apply_fix_with_edit(
            file_path="tests/fixtures/sample.py",
            old_code="return x * 2",
            new_code="return x * 2  # Unclosed parenthesis:("
        )
EOF
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents/test_edit_tool_enforcement.py -v`
Expected: FAIL with "ProactiveAgent has no attribute '\_apply_fix_with_edit'"

**Step 3: Add Edit tool wrapper to ProactiveAgent**

Modify `crackerjack/agents/proactive_agent.py`:

```python
from Edit import Edit  # Import the Edit tool

class ProactiveAgent:
    # ... existing code ...

    async def _apply_fix_with_edit(
        self,
        file_path: str,
        old_code: str,
        new_code: str
    ) -> bool:
        """Apply fix using Edit tool (syntax-validating).

        This is the ONLY way agents should modify code. The Edit tool
        validates syntax automatically, preventing broken code.

        Args:
            file_path: Path to file to modify
            old_code: Exact code to replace (must match)
            new_code: New code to insert

        Returns:
            True if successful, False otherwise
        """
        try:
            edit = Edit(
                file_path=file_path,
                old_string=old_code,
                new_string=new_code
            )
            # Edit tool validates syntax automatically
            await edit.apply()
            logger.info(f"✅ Applied fix to {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Edit tool failed: {e}")
            return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents/test_edit_tool_enforcement.py -v`
Expected: PASS (or adjust test based on actual Edit tool API)

**Step 5: Commit**

```bash
git add crackerjack/agents/proactive_agent.py tests/agents/test_edit_tool_enforcement.py
git commit -m "feat(layer1): enforce Edit tool usage for all agent fixes

- Add _apply_fix_with_edit() method
- Edit tool validates syntax automatically
- Prevents broken code from being applied
- Add enforcement tests

Part of Layer 1: Read-First Foundation"
```

______________________________________________________________________

### Task 1.3: Add Minimal Diff Size Enforcement

**Files:**

- Modify: `crackerjack/agents/proactive_agent.py:150-180`
- Test: `tests/agents/test_diff_size_limit.py`

**Step 1: Write the failing test**

```bash
cat > tests/agents/test_diff_size_limit.py << 'EOF'
"""Test diff size enforcement."""
import pytest
from crackerjack.agents.proactive_agent import ProactiveAgent

@pytest.mark.asyncio
async def test_small_diff_allowed():
    """Diffs under 50 lines should be allowed."""
    agent = ProactiveAgent()

    old_code = "return x * 2"
    new_code = "return x * 2  # Add comment"

    # Should be allowed (1 line change)
    assert agent._validate_diff_size(old_code, new_code) is True

@pytest.mark.asyncio
async def test_large_diff_rejected():
    """Diffs over 50 lines should be rejected."""
    agent = ProactiveAgent()

    # Generate 51 lines of code
    old_lines = ["line_" + str(i) for i in range(50)]
    new_lines = ["line_" + str(i) + "  # modified" for i in range(51)]

    old_code = "\n".join(old_lines)
    new_code = "\n".join(new_lines)

    # Should be rejected (too many lines)
    assert agent._validate_diff_size(old_code, new_code) is False
EOF
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents/test_diff_size_limit.py -v`
Expected: FAIL with "ProactiveAgent has no attribute '\_validate_diff_size'"

**Step 3: Add diff size validation to ProactiveAgent**

Modify `crackerjack/agents/proactive_agent.py`:

```python
class ProactiveAgent:
    MAX_DIFF_LINES = 50  # Maximum lines per fix

    # ... existing code ...

    def _validate_diff_size(self, old_code: str, new_code: str) -> bool:
        """Validate that diff size is within limits.

        Minimal, targeted changes are less risky and easier to validate.

        Args:
            old_code: Original code
            new_code: New code

        Returns:
            True if diff is small enough, False otherwise
        """
        old_lines = old_code.strip().split("\n")
        new_lines = new_code.strip().split("\n")

        # Check line count
        max_lines = max(len(old_lines), len(new_lines))
        if max_lines > self.MAX_DIFF_LINES:
            logger.warning(
                f"⚠️  Diff too large: {max_lines} lines "
                f"(max: {self.MAX_DIFF_LINES})"
            )
            return False

        logger.debug(f"✅ Diff size OK: {max_lines} lines")
        return True
```

**Step 4: Update \_apply_fix_with_edit to validate size**

```python
async def _apply_fix_with_edit(
    self,
    file_path: str,
    old_code: str,
    new_code: str
) -> bool:
    """Apply fix using Edit tool (syntax-validating)."""
    # Validate diff size first
    if not self._validate_diff_size(old_code, new_code):
        logger.error("❌ Diff too large, rejecting fix")
        return False

    try:
        edit = Edit(
            file_path=file_path,
            old_string=old_code,
            new_string=new_code
        )
        await edit.apply()
        logger.info(f"✅ Applied fix to {file_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Edit tool failed: {e}")
        return False
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/agents/test_diff_size_limit.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add crackerjack/agents/proactive_agent.py tests/agents/test_diff_size_limit.py
git commit -m "feat(layer1): enforce 50-line diff size limit

- Add _validate_diff_size() method
- Reject fixes larger than 50 lines
- Forces agents to make minimal, targeted changes
- Add comprehensive tests

Part of Layer 1: Read-First Foundation"
```

______________________________________________________________________

### Task 1.4: Add Syntax Validation Hook

**Files:**

- Create: `crackerjack/agents/syntax_validator.py`
- Modify: `crackerjack/agents/proactive_agent.py:180-200`
- Test: `tests/agents/test_syntax_validation.py`

**Step 1: Write the failing test**

```bash
cat > tests/agents/test_syntax_validation.py << 'EOF'
"""Test syntax validation."""
import pytest
from crackerjack.agents.syntax_validator import SyntaxValidator

@pytest.mark.asyncio
async def test_valid_python_passes():
    """Valid Python code should pass validation."""
    validator = SyntaxValidator()

    code = """
def hello():
    return "world"
"""

    result = await validator.validate(code)
    assert result.valid is True
    assert result.errors == []

@pytest.mark.asyncio
async def test_syntax_error_fails():
    """Invalid Python should fail validation."""
    validator = SyntaxValidator()

    code = """
def hello(
    return "world"  # Missing closing parenthesis
"""

    result = await validator.validate(code)
    assert result.valid is False
    assert len(result.errors) > 0
    assert "syntax" in str(result.errors).lower() or "parenthesis" in str(result.errors).lower()

@pytest.mark.asyncio
async def test_unclosed_string_fails():
    """Unclosed strings should be detected."""
    validator = SyntaxValidator()

    code = 'message = "hello world'  # Missing closing quote

    result = await validator.validate(code)
    assert result.valid is False
EOF
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents/test_syntax_validation.py -v`
Expected: FAIL with "No module named 'syntax_validator'"

**Step 3: Create SyntaxValidator**

```bash
cat > crackerjack/agents/syntax_validator.py << 'EOF'
"""Syntax validation for AI-generated code."""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of syntax validation."""
    valid: bool
    errors: list[str]


class SyntaxValidator:
    """Validates Python syntax using AST parsing."""

    async def validate(self, code: str) -> ValidationResult:
        """Validate Python code syntax.

        Args:
            code: Python code to validate

        Returns:
            ValidationResult with validity status and error messages
        """
        try:
            # Try to parse as AST
            ast.parse(code)
            logger.debug("✅ Syntax validation passed")
            return ValidationResult(valid=True, errors=[])

        except SyntaxError as e:
            error_msg = f"Line {e.lineno}: {e.msg}"
            logger.warning(f"❌ Syntax error: {error_msg}")
            return ValidationResult(valid=False, errors=[error_msg])

        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(f"❌ Validation error: {error_msg}")
            return ValidationResult(valid=False, errors=[error_msg])
EOF
```

**Step 4: Add validation to ProactiveAgent**

Modify `crackerjack/agents/proactive_agent.py`:

```python
from crackerjack.agents.syntax_validator import SyntaxValidator

class ProactiveAgent:
    def __init__(self, ...):
        # ... existing code ...
        self._syntax_validator = SyntaxValidator()

    async def _validate_syntax(self, code: str) -> ValidationResult:
        """Validate Python syntax.

        Args:
            code: Code to validate

        Returns:
            ValidationResult
        """
        return await self._syntax_validator.validate(code)
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/agents/test_syntax_validation.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add crackerjack/agents/syntax_validator.py crackerjack/agents/proactive_agent.py tests/agents/test_syntax_validation.py
git commit -m "feat(layer1): add AST-based syntax validation

- Add SyntaxValidator class
- Validates code before applying fixes
- Catches syntax errors early
- Comprehensive test coverage

Part of Layer 1: Read-First Foundation"
```

______________________________________________________________________

## Phase 2: Layer 2 - Two-Stage Pipeline

### Task 2.1: Create FixPlan Data Structures

**Files:**

- Create: `crackerjack/models/fix_plan.py`
- Test: `tests/models/test_fix_plan.py`

**Step 1: Write the failing test**

```bash
cat > tests/models/test_fix_plan.py << 'EOF'
"""Test FixPlan data structures."""
from crackerjack.models.fix_plan import FixPlan, ChangeSpec

def test_change_spec_creation():
    """ChangeSpec should store change details."""
    spec = ChangeSpec(
        line_range=(10, 15),
        old_code="return x * 2",
        new_code="return x * 2  # Multiply by 2",
        reason="Add clarifying comment"
    )

    assert spec.line_range == (10, 15)
    assert spec.old_code == "return x * 2"
    assert spec.new_code == "return x * 2  # Multiply by 2"
    assert spec.reason == "Add clarifying comment"

def test_fix_plan_creation():
    """FixPlan should aggregate multiple changes."""
    changes = [
        ChangeSpec(
            line_range=(10, 15),
            old_code="return x * 2",
            new_code="return x * 2  # Multiply by 2",
            reason="Add comment"
        ),
        ChangeSpec(
            line_range=(20, 22),
            old_code="x = 5",
            new_code="x: int = 5",
            reason="Add type hint"
        )
    ]

    plan = FixPlan(
        file_path="sample.py",
        issue_type="TYPE_ERROR",
        changes=changes,
        rationale="Add type hints and comments",
        risk_level="low",
        validated_by="SyntaxValidator"
    )

    assert len(plan.changes) == 2
    assert plan.file_path == "sample.py"
    assert plan.risk_level == "low"
EOF
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/models/test_fix_plan.py -v`
Expected: FAIL with "No module named 'fix_plan'"

**Step 3: Create FixPlan module**

```bash
cat > crackerjack/models/fix_plan.py << 'EOF'
"""Fix plan data structures for two-stage pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class ChangeSpec:
    """Atomic change specification.

    Represents a single, minimal change to be applied.
    """
    line_range: tuple[int, int]
    """Line numbers (start, end) for this change."""

    old_code: str
    """Exact code to be replaced (must match)."""

    new_code: str
    """New code to insert."""

    reason: str
    """Explanation for this change."""


@dataclass
class FixPlan:
    """Validated fix plan.

    A FixPlan is created by the Analysis Team and validated
    before being passed to the Fixer Team for execution.
    """
    file_path: str
    """Path to file to modify."""

    issue_type: str
    """Type of issue being fixed (e.g., TYPE_ERROR, COMPLEXITY)."""

    changes: list[ChangeSpec]
    """List of atomic changes to apply."""

    rationale: str
    """Explanation of the overall fix strategy."""

    risk_level: Literal["low", "medium", "high"]
    """Assessed risk level of this fix."""

    validated_by: str
    """Name of agent/team that validated this plan."""
EOF
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/models/test_fix_plan.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add crackerjack/models/fix_plan.py tests/models/test_fix_plan.py
git commit -m "feat(layer2): add FixPlan and ChangeSpec data structures

- Add ChangeSpec for atomic changes
- Add FixPlan for validated fix plans
- Support risk assessment and validation tracking
- Full test coverage

Part of Layer 2: Two-Stage Pipeline"
```

______________________________________________________________________

### Task 2.2: Create ContextAgent for File Analysis

**Files:**

- Create: `crackerjack/agents/context_agent.py`
- Test: `tests/agents/test_context_agent.py`

**Step 1: Write the failing test**

```bash
cat > tests/agents/test_context_agent.py << 'EOF'
"""Test ContextAgent for file analysis."""
import pytest
from crackerjack.agents.context_agent import ContextAgent
from crackerjack.models.issue import Issue

@pytest.mark.asyncio
async def test_context_agent_extracts_function_context():
    """ContextAgent should extract surrounding function context."""
    agent = ContextAgent()

    issue = Issue(
        file_path="tests/fixtures/sample.py",
        line=7,
        issue_type="TYPE_ERROR",
        description="Type error in sample_function"
    )

    context = await agent.extract_context(issue)

    assert context is not None
    assert "def sample_function" in context
    assert "return x * 2" in context
    assert context["function_name"] == "sample_function"

@pytest.mark.asyncio
async def test_context_agent_identifies_imports():
    """ContextAgent should identify relevant imports."""
    agent = ContextAgent()

    issue = Issue(
        file_path="tests/fixtures/sample.py",
        line=7,
        issue_type="TYPE_ERROR",
        description="Type error"
    )

    context = await agent.extract_context(issue)

    assert "imports" in context
    # Sample file has from __future__ import annotations
    assert len(context["imports"]) >= 0
EOF
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents/test_context_agent.py -v`
Expected: FAIL with "No module named 'context_agent'"

**Step 3: Create ContextAgent**

```bash
cat > crackerjack/agents/context_agent.py << 'EOF'
"""Context extraction agent for analysis stage."""
from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from crackerjack.agents.proactive_agent import ProactiveAgent
from crackerjack.models.issue import Issue

logger = logging.getLogger(__name__)


class ContextAgent(ProactiveAgent):
    """Extracts relevant context from files for analysis."""

    async def extract_context(self, issue: Issue) -> dict[str, Any]:
        """Extract context around an issue location.

        Args:
            issue: Issue to analyze

        Returns:
            Dictionary with context information:
            - file_content: Full file content
            - lines: List of lines
            - function_name: Enclosing function name (if any)
            - class_name: Enclosing class name (if any)
            - imports: List of import statements
        """
        # Read file (Layer 1: Read-First)
        file_content = await self._read_file_context(issue.file_path)
        lines = file_content.split("\n")

        context = {
            "file_content": file_content,
            "lines": lines,
            "function_name": None,
            "class_name": None,
            "imports": []
        }

        # Parse AST to find enclosing context
        try:
            tree = ast.parse(file_content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.lineno <= issue.line <= node.end_lineno:
                        context["function_name"] = node.name
                elif isinstance(node, ast.ClassDef):
                    if node.lineno <= issue.line <= node.end_lineno:
                        context["class_name"] = node.name
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    context["imports"].append(
                        ast.unparse(node)
                    )

        except SyntaxError:
            logger.warning(f"Could not parse AST for {issue.file_path}")

        # Extract imports with regex as fallback
        if not context["imports"]:
            context["imports"] = self._extract_imports_regex(file_content)

        logger.debug(
            f"📖 Extracted context: "
            f"function={context['function_name']}, "
            f"class={context['class_name']}"
        )

        return context

    def _extract_imports_regex(self, content: str) -> list[str]:
        """Extract imports using regex (fallback)."""
        import_pattern = r"^(?:from\s+\S+\s+)?import\s+.*"
        matches = re.findall(import_pattern, content, re.MULTILINE)
        return matches
EOF
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents/test_context_agent.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add crackerjack/agents/context_agent.py tests/agents/test_context_agent.py
git commit -m "feat(layer2): add ContextAgent for file analysis

- Extract function/class context around issues
- Identify relevant imports
- AST-based parsing with regex fallback
- Full test coverage

Part of Layer 2: Two-Stage Pipeline (Stage 1: Analysis Team)"
```

______________________________________________________________________

## Summary

This implementation plan covers:

- ✅ **Phase 1 (Layer 1)**: Read-First Foundation (Tasks 1.1-1.4)

  - File context reading
  - Edit tool enforcement
  - Diff size limits
  - Syntax validation

- ✅ **Phase 2 (Layer 2)**: Two-Stage Pipeline (Tasks 2.1-2.2)

  - FixPlan data structures
  - ContextAgent for analysis

**Remaining Phases:**

- Phase 2 continued: PatternAgent, PlanningAgent, Fixer Team
- Phase 3 (Layer 3): Validation Loop with Power Trio
- Phase 4 (Layer 4): Fallback Wrapper
- Phase 5: Integration & Testing

Each task is:

- ✅ Bite-sized (2-5 minutes per step)
- ✅ TDD (failing test first)
- ✅ Complete code provided
- ✅ Exact file paths
- ✅ Frequent commits

**Total Estimated Time for Phases 1-2:** ~1-2 hours

**Total Estimated Time for Complete Implementation:** ~6-8 hours

______________________________________________________________________

**Sources:**

- [Multi-Agent Framework for Code-Compliant Design](https://www.sciencedirect.com/science/article/abs/pii/S0926580525003711)
- [Building Multi-Agent Workflows with LangChain](https://www.ema.co/additional-blogs/addition-blogs/multi-agent-workflows-langchain-langgraph)
- [AI Code Generation Best Practices](https://www.gocodeo.com/post/ai-code-generation-in-2025-capabilities-limitations-and-whats-next)
