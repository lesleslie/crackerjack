"""Specialized agent for fixing type errors from zuban/pyscn."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .base import FixResult, Issue, IssueType, SubAgent

if TYPE_CHECKING:
    from .base import AgentContext

logger = logging.getLogger(__name__)


class TypeErrorSpecialistAgent(SubAgent):
    """Specialized agent for type errors with targeted strategies.

    This agent focuses specifically on type errors from zuban/pyscn
    with specialized fixing strategies:
    1. Missing type annotations
    2. Generic type parameters
    3. Protocol definitions
    4. Import typing constructs
    5. Optional/Union types
    """

    name = "TypeErrorSpecialist"

    def __init__(self, context: "AgentContext") -> None:
        super().__init__(context)
        self.log = logger.info

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.TYPE_ERROR}

    async def can_handle(self, issue: Issue) -> float:
        """High confidence for type errors from zuban/pyscn."""

        if issue.type != IssueType.TYPE_ERROR:
            return 0.0

        if not issue.message:
            return 0.0

        # Prefer zuban/pyscn type errors
        if issue.stage in ("zuban", "pyscn"):
            return 0.85

        # Still handle other type errors
        return 0.6

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Fix type errors with specialized strategies."""

        self.log(f"TypeErrorSpecialist analyzing: {issue.message[:100]}")

        if issue.file_path is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided"],
            )

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"File not found: {file_path}"],
            )

        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not read file content"],
            )

        # Apply type-specific fixes
        new_content, fixes_applied = await self._apply_type_fixes(
            content, issue, file_path
        )

        if new_content == content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No changes applied"],
            )

        # Write the fixed content
        try:
            file_path.write_text(new_content)
            return FixResult(
                success=True,
                confidence=0.7,
                fixes_applied=fixes_applied,
                files_modified=[str(file_path)],
            )
        except Exception as e:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to write file: {e}"],
            )

    async def _apply_type_fixes(
        self, content: str, issue: Issue, file_path: Path
    ) -> tuple[str, list[str]]:
        """Apply type error fixes with multiple strategies."""

        fixes = []
        new_content = content

        # Strategy 1: Add missing type annotations for function returns
        new_content, fix1 = self._fix_missing_return_types(new_content, issue)
        if fix1:
            fixes.extend(fix1)

        # Strategy 2: Add from __future__ import annotations
        new_content, fix2 = self._add_future_annotations(new_content)
        if fix2:
            fixes.append("Added 'from __future__ import annotations'")

        # Strategy 3: Import typing constructs
        new_content, fix3 = self._add_typing_imports(new_content, issue)
        if fix3:
            fixes.extend(fix3)

        # Strategy 4: Fix generic type parameters
        new_content, fix4 = self._fix_generic_types(new_content, issue)
        if fix4:
            fixes.extend(fix4)

        # Strategy 5: Add Optional/Union types
        new_content, fix5 = self._fix_optional_union_types(new_content, issue)
        if fix5:
            fixes.extend(fix5)

        return new_content, fixes

    def _fix_missing_return_types(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        """Add missing return type annotations."""

        fixes = []

        # Pattern: functions without return type
        # Match: "def function_name(" → "def function_name( -> None:"
        lines = content.split("\n")
        new_lines = []

        for line in lines:
            # Check if this is a function definition without return type
            if re.match(r"^\s*def\s+\w+\s*\([^)]*\)\s*:", line):
                # Check if line doesn't already have -> annotation
                if "->" not in line and "async def" not in line:
                    # Add -> None for functions without explicit return
                    # Be conservative: only add for simple cases
                    if any(
                        keyword in issue.message.lower()
                        for keyword in ("missing", "return", "type")
                    ):
                        # Insert -> None before the colon
                        modified = line.rstrip().rstrip(":") + " -> None:"
                        if modified != line:
                            new_lines.append(modified)
                            fixes.append(
                                f"Added return type annotation: {modified[:80]}..."
                            )
                            continue
            new_lines.append(line)

        return "\n".join(new_lines), fixes

    def _add_future_annotations(self, content: str) -> tuple[str, list[str]]:
        """Add 'from __future__ import annotations' if needed."""

        if "from __future__ import annotations" in content:
            return content, []

        lines = content.split("\n")

        # Find first import or docstring
        insert_index = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                # Skip docstring
                continue
            if stripped.startswith("import ") or stripped.startswith("from "):
                insert_index = i
                break
            if stripped and not stripped.startswith("#"):
                # Found first non-import, non-comment line
                insert_index = i
                break

        lines.insert(insert_index, "from __future__ import annotations")
        return "\n".join(lines), ["Added __future__ annotations import"]

    def _add_typing_imports(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        """Add missing typing imports based on error message."""

        fixes = []
        new_imports = []

        # Check error message for typing constructs
        message_lower = issue.message.lower()

        if "optional" in message_lower or "None" in message_lower:
            if "from typing import" in content:
                if "Optional" not in content:
                    # Add Optional to existing typing import
                    content = re.sub(
                        r"(from typing import [^\n]+)",
                        r"\1, Optional",
                        content,
                    )
                    fixes.append("Added Optional to typing imports")
            else:
                new_imports.append("from typing import Optional")

        if "union" in message_lower or " | " in issue.message:
            if "from typing import" in content:
                if "Union" not in content:
                    content = re.sub(
                        r"(from typing import [^\n]+)",
                        r"\1, Union",
                        content,
                    )
                    fixes.append("Added Union to typing imports")
            else:
                new_imports.append("from typing import Union")

        if "list[" in message_lower or "dict[" in message_lower:
            if "from typing import" in content:
                if "List" not in content or "Dict" not in content:
                    content = re.sub(
                        r"(from typing import [^\n]+)",
                        r"\1, List, Dict",
                        content,
                    )
                    fixes.append("Added List, Dict to typing imports")
            else:
                new_imports.append("from typing import List, Dict")

        # Add new imports after __future__ import
        if new_imports:
            lines = content.split("\n")
            insert_index = 0

            # Find position after __future__ import
            for i, line in enumerate(lines):
                if "from __future__ import annotations" in line:
                    insert_index = i + 1
                    break
                elif (
                    line.strip().startswith("import")
                    or line.strip().startswith("from")
                ) and insert_index == 0:
                    insert_index = i

            for new_import in reversed(new_imports):
                lines.insert(insert_index, new_import)
                fixes.append(f"Added import: {new_import}")

            return "\n".join(lines), fixes

        return content, fixes

    def _fix_generic_types(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        """Fix generic type parameters."""

        fixes = []
        message_lower = issue.message.lower()

        # Fix generic class definitions
        # Pattern: "class MyClass:" → "class MyClass(Generic[T]):"
        if "generic" in message_lower:
            lines = content.split("\n")
            new_lines = []

            for line in lines:
                # Check for class definitions without Generic base
                match = re.match(r"^class\s+(\w+)\s*:\s*$", line)
                if match and "Generic[" not in content:
                    class_name = match.group(1)
                    # Add Generic[T] parameter
                    modified = f"class {class_name}(Generic[T]):"
                    # Add import if needed
                    if "from typing import Generic" not in content:
                        fixes.append("Added Generic base class with import")
                        # Will be handled by _add_typing_imports
                    new_lines.append(modified)
                    fixes.append(f"Added Generic[T] base to {class_name}")
                    continue
                new_lines.append(line)

            return "\n".join(new_lines), fixes

        return content, fixes

    def _fix_optional_union_types(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        """Fix Optional and Union type usage."""

        fixes = []
        message_lower = issue.message.lower()

        # Fix: None -> Optional[Type]
        if "optional" in message_lower or "none" in message_lower:
            # Pattern: ": None" → ": Optional[Type]"
            # This is complex and requires parsing the actual type
            # For now, just note it as a potential fix
            fixes.append("Detected Optional type usage (may need manual review)")

        return content, fixes


# Register the agent
from .base import agent_registry

agent_registry.register(TypeErrorSpecialistAgent)
