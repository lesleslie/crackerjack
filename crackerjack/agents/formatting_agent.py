from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from crackerjack.services.regex_patterns import apply_formatting_fixes

from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
    SubAgent,
    agent_registry,
)

if TYPE_CHECKING:
    from crackerjack.models.fix_plan import FixPlan


class FormattingAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.FORMATTING, IssueType.IMPORT_ERROR}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type not in self.get_supported_types():
            return 0.0

        message_lower = issue.message.lower()

        if any(
            keyword in message_lower
            for keyword in (
                "would reformat",
                "trailing whitespace",
                "missing newline",
                "import sorting",
                "unused import",
                "ruff",
                "spelling",
            )
        ):
            return 1.0

        if any(
            keyword in message_lower
            for keyword in (
                "whitespace",
                "indent",
                "spacing",
                "line length",
                "import",
                "style",
                "formatting",
            )
        ):
            return 0.8

        if issue.type == IssueType.FORMATTING:
            return 0.6

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing formatting issue: {issue.message}")

        fixes_applied: list[str] = []
        files_modified: list[str] = []

        try:
            message_lower = issue.message.lower()
            if "spelling" in message_lower:
                spelling_fixes = await self._apply_spelling_fixes(issue)
                fixes_applied.extend(spelling_fixes)
                if spelling_fixes and issue.file_path:
                    files_modified.append(issue.file_path)

            target = [issue.file_path] if issue.file_path else ["."]

            ruff_fixes, ruff_files = await self._apply_ruff_fixes(target)
            fixes_applied.extend(ruff_fixes)
            files_modified.extend(ruff_files)

            whitespace_fixes, whitespace_files = await self._apply_whitespace_fixes(
                target
            )
            fixes_applied.extend(whitespace_fixes)
            files_modified.extend(whitespace_files)

            import_fixes, import_files = await self._apply_import_fixes(target)
            fixes_applied.extend(import_fixes)
            files_modified.extend(import_files)

            if issue.file_path and "spelling" not in message_lower:
                file_fixes = await self._fix_specific_file(issue.file_path, issue)
                fixes_applied.extend(file_fixes)
                if file_fixes and issue.file_path not in files_modified:
                    files_modified.append(issue.file_path)

            success = fixes_applied
            confidence = 0.9 if success else 0.3

            return FixResult(
                success=success,  # type: ignore
                confidence=confidence,
                fixes_applied=fixes_applied,
                files_modified=list(set(files_modified)),
                recommendations=[
                    "Run ruff format regularly for consistent styling",
                    "Configure pre-commit hooks for automatic formatting",
                ]
                if not success
                else [],
            )

        except Exception as e:
            self.log(f"Error fixing formatting issue: {e}", "ERROR")
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to apply formatting fixes: {e}"],
            )

    async def _apply_ruff_fixes(self, target: list[str]) -> tuple[list[str], list[str]]:
        fixes: list[str] = []
        files_modified: list[str] = []

        files_before = self._get_file_state(target)

        returncode, _, stderr = await self.run_command(
            ["uv", "run", "ruff", "format", *target],
        )

        if returncode == 0:
            fixes.append("Applied ruff code formatting")
            self.log("Successfully applied ruff formatting")
            files_modified.extend(self._get_modified_files(files_before, target))
        else:
            self.log(f"Ruff format failed: {stderr}", "WARN")

        returncode, _, stderr = await self.run_command(
            ["uv", "run", "ruff", "check", *target, "--fix"],
        )

        if returncode == 0:
            fixes.append("Applied ruff linting fixes")
            self.log("Successfully applied ruff linting fixes")
            files_modified.extend(self._get_modified_files(files_before, target))
        else:
            self.log(f"Ruff check --fix had issues: {stderr}", "WARN")

        return fixes, list(set(files_modified))

    async def _apply_whitespace_fixes(
        self, target: list[str]
    ) -> tuple[list[str], list[str]]:
        fixes: list[str] = []
        files_modified: list[str] = []

        files_before = self._get_file_state(target)

        returncode, _, _ = await self.run_command(
            [
                "uv",
                "run",
                "python",
                "-m",
                "crackerjack.tools.trailing_whitespace",
                *target,
            ],
        )

        if returncode == 0:
            fixes.append("Fixed trailing whitespace")
            self.log("Fixed trailing whitespace")
            files_modified.extend(self._get_modified_files(files_before, target))

        returncode, _, _ = await self.run_command(
            [
                "uv",
                "run",
                "python",
                "-m",
                "crackerjack.tools.end_of_file_fixer",
                *target,
            ],
        )

        if returncode == 0:
            fixes.append("Fixed end-of-file formatting")
            self.log("Fixed end-of-file formatting")
            files_modified.extend(self._get_modified_files(files_before, target))

        return fixes, list(set(files_modified))

    async def _apply_import_fixes(
        self, target: list[str]
    ) -> tuple[list[str], list[str]]:
        fixes: list[str] = []
        files_modified: list[str] = []

        files_before = self._get_file_state(target)

        returncode, _, _ = await self.run_command(
            [
                "uv",
                "run",
                "ruff",
                "check",
                *target,
                "--select",
                "I, F401",
                "--fix",
            ],
        )

        if returncode == 0:
            fixes.append("Organized imports and removed unused imports")
            self.log("Fixed import organization")
            files_modified.extend(self._get_modified_files(files_before, target))

        return fixes, list(set(files_modified))

    async def _apply_spelling_fixes(self, issue: Issue) -> list[str]:
        fixes: list[str] = []

        if not issue.file_path:
            self.log("No specific file path for spelling fix", "WARNING")
            return fixes

        try:
            self.log(f"Applying spelling fixes to {issue.file_path}")

            returncode, stdout, stderr = await self.run_command(
                ["uv", "run", "codespell", "-w", issue.file_path],
            )

            if returncode == 0:
                fix_count = stdout.count("FIXED") if stdout else 0
                message = f"Fixed {fix_count} spelling error(s) in {issue.file_path}"
                fixes.append(message)
                self.log(message)
            else:
                if "FIXED" in stdout or "fixed" in stdout.lower():
                    fix_count = stdout.count("FIXED")
                    message = (
                        f"Fixed {fix_count} spelling error(s) in {issue.file_path}"
                    )
                    fixes.append(message)
                    self.log(message)
                else:
                    self.log(f"Codespell returned {returncode}: {stderr}", "WARNING")

        except Exception as e:
            self.log(f"Error applying spelling fixes: {e}", "ERROR")

        return fixes

    async def _fix_specific_file(self, file_path: str, issue: Issue) -> list[str]:
        fixes: list[str] = []

        try:
            path = Path(file_path)
            content = self._validate_and_get_file_content(path)
            if not content:
                return fixes

            original_content = content
            cleaned_content = self._apply_content_formatting(content)

            if cleaned_content != original_content:
                if self.context.write_file_content(path, cleaned_content):
                    fixes.append(f"Fixed formatting in {file_path}")
                    self.log(f"Applied file-specific fixes to {file_path}")

        except Exception as e:
            self.log(f"Error fixing file {file_path}: {e}", "ERROR")

        return fixes

    def _validate_and_get_file_content(self, path: Path) -> str | None:
        if not path.exists() or not path.is_file():
            return None

        content = self.context.get_file_content(path)
        return content or None

    def _apply_content_formatting(self, content: str) -> str:
        content = apply_formatting_fixes(content)

        if content == "":
            content = "\n"
        elif not content.endswith("\n"):
            content += "\n"

        return self._convert_tabs_to_spaces(content)

    def _convert_tabs_to_spaces(self, content: str) -> str:
        lines = content.split("\n")
        fixed_lines = [line.expandtabs(4) for line in lines]
        return "\n".join(fixed_lines)

    def _get_file_state(self, target: list[str]) -> dict[str, float]:
        files_before: dict[str, float] = {}

        for t in target:
            if t == ".":
                project_path = self.context.project_path
                for py_file in project_path.rglob("*.py"):
                    if py_file.is_file():
                        files_before[str(py_file)] = py_file.stat().st_mtime
            else:
                file_path = Path(t)
                if file_path.exists() and file_path.is_file():
                    files_before[t] = file_path.stat().st_mtime

        return files_before

    def _get_modified_files(
        self, files_before: dict[str, float], target: list[str]
    ) -> list[str]:
        modified: list[str] = []

        for file_path, mtime_before in files_before.items():
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                try:
                    mtime_after = file_path_obj.stat().st_mtime
                    if mtime_after > mtime_before:
                        modified.append(file_path)
                except OSError:
                    pass

        return modified

    async def execute_fix_plan(self, plan: FixPlan) -> FixResult:  # type: ignore[untyped]

        self.log(
            f"Executing FixPlan for {plan.file_path}:{plan.issue_type} "
            f"({len(plan.changes)} changes, risk={plan.risk_level})"
        )

        if not plan.changes:
            self.log(
                f"Plan has no changes to apply for {plan.file_path}", level="WARNING"
            )
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Plan has no changes to apply"],
                recommendations=["PlanningAgent should generate actual changes"],
            )

        if not plan.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path in plan"],
            )

        try:
            issue = Issue(
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message=plan.rationale or "Formatting fix",
                file_path=plan.file_path,
                line_number=plan.changes[0].line_range[0] if plan.changes else None,
            )

            result = await self.analyze_and_fix(issue)
            return result

        except Exception as e:
            self.log(f"Error executing formatting plan: {e}", "ERROR")
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Formatting execution error: {e}"],
            )


agent_registry.register(FormattingAgent)
