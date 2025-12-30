from pathlib import Path

from crackerjack.services.regex_patterns import apply_formatting_fixes

from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


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
            ruff_fixes = await self._apply_ruff_fixes()
            fixes_applied.extend(ruff_fixes)

            whitespace_fixes = await self._apply_whitespace_fixes()
            fixes_applied.extend(whitespace_fixes)

            import_fixes = await self._apply_import_fixes()
            fixes_applied.extend(import_fixes)

            if issue.file_path:
                file_fixes = await self._fix_specific_file(issue.file_path, issue)
                fixes_applied.extend(file_fixes)
                if file_fixes:
                    files_modified.append(issue.file_path)

            success = len(fixes_applied) > 0
            confidence = 0.9 if success else 0.3

            return FixResult(
                success=success,
                confidence=confidence,
                fixes_applied=fixes_applied,
                files_modified=files_modified,
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

    async def _apply_ruff_fixes(self) -> list[str]:
        fixes: list[str] = []

        returncode, _, stderr = await self.run_command(
            ["uv", "run", "ruff", "format", "."],
        )

        if returncode == 0:
            fixes.append("Applied ruff code formatting")
            self.log("Successfully applied ruff formatting")
        else:
            self.log(f"Ruff format failed: {stderr}", "WARN")

        returncode, _, stderr = await self.run_command(
            ["uv", "run", "ruff", "check", ".", "--fix"],
        )

        if returncode == 0:
            fixes.append("Applied ruff linting fixes")
            self.log("Successfully applied ruff linting fixes")
        else:
            self.log(f"Ruff check --fix had issues: {stderr}", "WARN")

        return fixes

    async def _apply_whitespace_fixes(self) -> list[str]:
        fixes: list[str] = []

        returncode, _, _ = await self.run_command(
            [
                "uv",
                "run",
                "python",
                "-m",
                "crackerjack.tools.trailing_whitespace",
            ],
        )

        if returncode == 0:
            fixes.append("Fixed trailing whitespace")
            self.log("Fixed trailing whitespace")

        returncode, _, _ = await self.run_command(
            [
                "uv",
                "run",
                "python",
                "-m",
                "crackerjack.tools.end_of_file_fixer",
            ],
        )

        if returncode == 0:
            fixes.append("Fixed end-of-file formatting")
            self.log("Fixed end-of-file formatting")

        return fixes

    async def _apply_import_fixes(self) -> list[str]:
        fixes: list[str] = []

        returncode, _, _ = await self.run_command(
            [
                "uv",
                "run",
                "ruff",
                "check",
                ".",
                "--select",
                "I, F401",
                "--fix",
            ],
        )

        if returncode == 0:
            fixes.append("Organized imports and removed unused imports")
            self.log("Fixed import organization")

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


agent_registry.register(FormattingAgent)
