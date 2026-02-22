import re
import subprocess
import typing as t
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from crackerjack.models.fix_plan import FixPlan
from crackerjack.services.regex_patterns import SAFE_PATTERNS

from .base import (
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class DocumentationAgent(SubAgent):
    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DOCUMENTATION}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.DOCUMENTATION:
            return 0.8
        return 0.0

    async def execute_fix_plan(self, plan: FixPlan) -> FixResult:
        """Execute a FixPlan for documentation issues.

        This method handles broken links by extracting the target from the
        rationale (which preserves the original message pattern) and fixing
        or removing the broken link.

        Args:
            plan: The FixPlan containing the fix details

        Returns:
            FixResult indicating success or failure
        """
        self.log(f"Executing fix plan for {plan.file_path}: {plan.rationale}")

        # Handle broken link issues
        if self._is_broken_link_plan(plan):
            return await self._fix_broken_link_from_plan(plan)

        # Handle other documentation issues
        if "changelog" in plan.rationale.lower():
            return await self._update_changelog_from_plan(plan)

        # For general documentation issues, provide recommendations
        return FixResult(
            success=True,
            confidence=0.6,
            recommendations=[
                f"Documentation issue in {plan.file_path}: {plan.rationale}",
                "Manual review recommended for optimal documentation updates",
            ],
        )

    def _is_broken_link_plan(self, plan: FixPlan) -> bool:
        """Check if this plan is for a broken link issue."""
        rationale_lower = plan.rationale.lower()
        return (
            "broken link" in rationale_lower
            or "file not found" in rationale_lower
            or ("link" in rationale_lower and "fix" in rationale_lower)
        )

    async def _fix_broken_link_from_plan(self, plan: FixPlan) -> FixResult:
        """Fix a broken link issue from a FixPlan.

        Extracts the target file from the rationale or changes and fixes
        or removes the broken link.
        """
        self.log(f"Fixing broken link in {plan.file_path}")

        # Extract target file from rationale (format: "Broken link: <target> - <message>")
        target_file = self._extract_target_from_rationale(plan.rationale)

        # Also try to get line number from changes if available
        line_number = None
        if plan.changes:
            line_number = plan.changes[0].line_range[0]

        content = self._read_file_content(plan.file_path)
        if content is None:
            return self._create_error_result(f"Failed to read {plan.file_path}")

        # If we have changes, apply them directly
        if plan.changes:
            return self._apply_fix_plan_changes(plan, content)

        # If no line number but we have a target, search for it in the file
        if line_number is None and target_file:
            line_number = self._find_line_with_target(content, target_file)
            if line_number:
                self.log(f"Found broken link at line {line_number}")

        # Otherwise, try to fix the broken link ourselves
        updated_content = self._fix_or_remove_broken_link_line(
            content, plan.file_path, line_number, target_file
        )

        return self._write_fixed_content(plan.file_path, updated_content, target_file)

    def _find_line_with_target(self, content: str, target_file: str) -> int | None:
        """Find the line number containing a link to the target file.

        Args:
            content: File content to search
            target_file: Target file path to search for

        Returns:
            1-indexed line number or None if not found
        """
        lines = content.split("\n")
        # Create a pattern to match markdown links containing the target
        # Handle various path formats (relative, with ../, etc.)
        re.escape(target_file)

        for i, line in enumerate(lines):
            # Check if line contains a markdown link with the target
            if target_file in line and "](" in line:
                return i + 1  # Return 1-indexed line number

        return None

    def _extract_target_from_rationale(self, rationale: str) -> str | None:
        """Extract the target file from a broken link rationale.

        Handles formats like:
        - "Broken link: File not found: ./some/file.md - Broken link"
        - "Broken link: ./some/file.md - File not found"
        - "Fix broken link to ./docs/guide.md"
        - "./missing/file.md does not exist"
        """
        # Pattern 1: "File not found: <path>" - common format from check-local-links
        match = re.search(r"File not found:\s*([^\s\-]+)", rationale, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Pattern 2: "Broken link: <path>" followed by more text
        match = re.search(r"Broken link:\s*([^\s\-]+)", rationale, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Pattern 3: "link to <target>"
        match = re.search(r"link to\s+([^\s]+)", rationale, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Pattern 3: Look for file-like paths in the message
        match = re.search(r"([\.\/][^\s]*\.(md|rst|txt|html))", rationale)
        if match:
            return match.group(1).strip()

        return None

    def _apply_fix_plan_changes(self, plan: FixPlan, content: str) -> FixResult:
        """Apply changes from a FixPlan to the file content."""
        lines = content.split("\n")

        # Sort changes by line number in reverse to apply from bottom to top
        sorted_changes = sorted(
            plan.changes, key=lambda c: c.line_range[0], reverse=True
        )

        for change in sorted_changes:
            start_line = change.line_range[0] - 1  # Convert to 0-indexed
            end_line = change.line_range[1] - 1

            if start_line < 0 or end_line >= len(lines):
                self.log(f"Warning: Line range {change.line_range} out of bounds")
                continue

            # Replace the lines
            new_lines = change.new_code.split("\n")
            lines[start_line : end_line + 1] = new_lines

        updated_content = "\n".join(lines)
        success = self.context.write_file_content(plan.file_path, updated_content)

        if success:
            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=[
                    f"Applied {len(plan.changes)} fixes to {plan.file_path}"
                ],
                files_modified=[plan.file_path],
            )

        return self._create_error_result(
            f"Failed to write fixed content to {plan.file_path}"
        )

    async def _update_changelog_from_plan(self, plan: FixPlan) -> FixResult:
        """Update changelog based on a FixPlan."""
        # Create a synthetic issue for the changelog update
        issue = Issue(
            type=IssueType.DOCUMENTATION,
            severity=plan.risk_level,
            message=plan.rationale,
            file_path=plan.file_path,
        )
        return await self._update_changelog(issue)

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing documentation issue: {issue.message}")

        try:
            if (
                "broken documentation link" in issue.message.lower()
                or "file not found" in issue.message.lower()
            ):
                return await self._fix_broken_link(issue)
            if "changelog" in issue.message.lower():
                return await self._update_changelog(issue)
            if (
                "agent count" in issue.message.lower()
                or "consistency" in issue.message.lower()
            ):
                return await self._fix_documentation_consistency(issue)
            if "api" in issue.message.lower() or "readme" in issue.message.lower():
                return await self._update_api_documentation(issue)
            return await self._general_documentation_update(issue)

        except Exception as e:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Error processing documentation: {e}"],
            )

    async def _update_changelog(self, issue: Issue) -> FixResult:
        self.log("Updating changelog with recent changes")

        changelog_path = Path("CHANGELOG.md")

        recent_changes = self._get_recent_changes()

        if not recent_changes:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No recent changes to add to changelog"],
            )

        changelog_entry = self._generate_changelog_entry(recent_changes)

        if changelog_path.exists():
            content = self.context.get_file_content(changelog_path)
            if content is None:
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[f"Failed to read {changelog_path}"],
                )
            updated_content = self._insert_changelog_entry(content, changelog_entry)
        else:
            updated_content = self._create_initial_changelog(changelog_entry)

        success = self.context.write_file_content(changelog_path, updated_content)

        if success:
            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=[
                    f"Updated CHANGELOG.md with {len(recent_changes)} recent changes",
                ],
                files_modified=[str(changelog_path)],
            )

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Failed to write changelog updates"],
        )

    async def _fix_documentation_consistency(self, issue: Issue) -> FixResult:
        self.log("Checking documentation consistency")

        md_files = list[t.Any](Path().glob("*.md")) + list[t.Any](
            Path("docs").glob("*.md"),
        )

        agent_count_issues = self._check_agent_count_consistency(md_files)

        files_modified: list[str] = []
        fixes_applied: list[str] = []

        for file_path, current_count, expected_count in agent_count_issues:
            content = self.context.get_file_content(file_path)
            if content:
                updated_content = self._fix_agent_count_references(
                    content,
                    current_count,
                    expected_count,
                )
                if updated_content != content:
                    success = self.context.write_file_content(
                        file_path,
                        updated_content,
                    )
                    if success:
                        files_modified.append(str(file_path))
                        fixes_applied.append(f"Updated agent count in {file_path.name}")

        if files_modified:
            return FixResult(
                success=True,
                confidence=0.85,
                fixes_applied=fixes_applied,
                files_modified=files_modified,
            )

        return FixResult(
            success=True,
            confidence=0.8,
            recommendations=["Documentation is already consistent"],
        )

    async def _update_api_documentation(self, issue: Issue) -> FixResult:
        self.log("Updating API documentation")

        api_changes = self._detect_api_changes()

        if not api_changes:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=[
                    "No API changes detected requiring documentation updates",
                ],
            )

        readme_path = Path("README.md")
        if readme_path.exists():
            content = self.context.get_file_content(readme_path)
            if content is None:
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[f"Failed to read {readme_path}"],
                )
            updated_content = self._update_readme_examples(content, api_changes)

            if updated_content != content:
                success = self.context.write_file_content(readme_path, updated_content)
                if success:
                    return FixResult(
                        success=True,
                        confidence=0.8,
                        fixes_applied=["Updated README.md examples for API changes"],
                        files_modified=[str(readme_path)],
                    )

        return FixResult(
            success=False,
            confidence=0.5,
            remaining_issues=["Could not update API documentation"],
            recommendations=["Manual review of API documentation may be needed"],
        )

    async def _general_documentation_update(self, issue: Issue) -> FixResult:
        self.log("Performing general documentation update")

        return FixResult(
            success=True,
            confidence=0.6,
            recommendations=[
                f"Documentation issue identified: {issue.message}",
                "Manual review recommended for optimal documentation updates",
                "Consider adding specific patterns to DocumentationAgent",
            ],
        )

    def _get_recent_changes(self) -> list[dict[str, str]]:
        try:
            commit_range = self._get_commit_range()
            if not commit_range:
                return []

            commit_messages = self._get_commit_messages(commit_range)
            return self._parse_commit_messages(commit_messages)

        except Exception:
            return []

    def _get_commit_range(self) -> str:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            last_tag = result.stdout.strip()
            return f"{last_tag}..HEAD"

        return "-10"

    def _get_commit_messages(self, commit_range: str) -> str:
        result = subprocess.run(
            ["git", "log", commit_range, "--pretty=format: %s|%h|%an"],
            capture_output=True,
            text=True,
            check=False,
        )

        return result.stdout.strip() if result.returncode == 0 else ""

    def _parse_commit_messages(self, commit_output: str) -> list[dict[str, str]]:
        changes: list[dict[str, str]] = []

        for line in commit_output.split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 2:
                    change_info: dict[str, str] = {
                        "message": parts[0].strip(),
                        "hash": parts[1].strip(),
                        "author": parts[2].strip() if len(parts) > 2 else "Unknown",
                    }
                    changes.append(change_info)

        return changes

    def _generate_changelog_entry(self, changes: list[dict[str, str]]) -> str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        entry_lines = [f"## [Unreleased] - {date_str}", ""]

        categorized_changes = self._categorize_changes(changes)
        self._add_categorized_changes_to_entry(entry_lines, categorized_changes)

        return "\n".join(entry_lines)

    def _categorize_changes(
        self,
        changes: list[dict[str, str]],
    ) -> dict[str, list[str]]:
        categories: dict[str, list[str]] = {
            "features": [],
            "fixes": [],
            "refactors": [],
            "other": [],
        }

        for change in changes:
            message = change["message"]
            category = self._get_change_category(message)
            categories[category].append(message)

        return categories

    def _get_change_category(self, message: str) -> str:
        if message.startswith(("feat: ", "feature: ")):
            return "features"
        if message.startswith("fix: "):
            return "fixes"
        if message.startswith(("refactor: ", "refact: ")):
            return "refactors"
        return "other"

    def _add_categorized_changes_to_entry(
        self,
        entry_lines: list[str],
        categories: dict[str, list[str]],
    ) -> None:
        section_mappings = {
            "features": "### Added",
            "fixes": "### Fixed",
            "refactors": "### Changed",
            "other": "### Other",
        }

        for category, section_title in section_mappings.items():
            items = categories[category]
            if items:
                self._add_section_to_entry(entry_lines, section_title, items)

    def _add_section_to_entry(
        self,
        entry_lines: list[str],
        section_title: str,
        items: list[str],
    ) -> None:
        entry_lines.append(section_title)
        for item in items:
            entry_lines.append(f"- {item}")
        entry_lines.append("")

    def _insert_changelog_entry(self, content: str, entry: str) -> str:
        lines = content.split("\n")

        insert_index = 0
        for i, line in enumerate(lines):
            if line.startswith(("# ", "## ")) and i > 0:
                insert_index = i
                break

        new_lines = (
            lines[:insert_index] + entry.split("\n") + [""] + lines[insert_index:]
        )
        return "\n".join(new_lines)

    def _create_initial_changelog(self, entry: str) -> str:
        return f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

{entry}
"""

    def _check_agent_count_consistency(
        self,
        md_files: list[Path],
    ) -> list[tuple[Path, int, int]]:
        expected_count = 9
        issues: list[tuple[Path, int, int]] = []
        patterns = self._get_agent_count_patterns()

        for file_path in md_files:
            issue = self._check_file_agent_count(file_path, patterns, expected_count)
            if issue:
                issues.append(issue)

        return issues

    def _get_agent_count_patterns(self) -> list[str]:
        return [
            SAFE_PATTERNS["agent_count_pattern"].pattern,
            SAFE_PATTERNS["specialized_agent_count_pattern"].pattern,
            SAFE_PATTERNS["total_agents_config_pattern"].pattern,
            SAFE_PATTERNS["sub_agent_count_pattern"].pattern,
        ]

    def _check_file_agent_count(
        self,
        file_path: Path,
        patterns: list[str],
        expected_count: int,
    ) -> tuple[Path, int, int] | None:
        with suppress(Exception):
            content = self.context.get_file_content(file_path)
            if not content:
                return None

            return self._analyze_file_content_for_agent_count(
                file_path,
                content,
                patterns,
                expected_count,
            )

        return None

    def _analyze_file_content_for_agent_count(
        self,
        file_path: Path,
        content: str,
        patterns: list[str],
        expected_count: int,
    ) -> tuple[Path, int, int] | None:
        pattern_map = self._get_safe_pattern_map()

        for pattern in patterns:
            result = self._check_pattern_for_count_mismatch(
                pattern,
                pattern_map,
                content,
                file_path,
                expected_count,
            )
            if result:
                return result

        return None

    def _get_safe_pattern_map(self) -> dict[str, str]:
        return {
            SAFE_PATTERNS["agent_count_pattern"].pattern: "agent_count_pattern",
            SAFE_PATTERNS[
                "specialized_agent_count_pattern"
            ].pattern: "specialized_agent_count_pattern",
            SAFE_PATTERNS[
                "total_agents_config_pattern"
            ].pattern: "total_agents_config_pattern",
            SAFE_PATTERNS["sub_agent_count_pattern"].pattern: "sub_agent_count_pattern",
        }

    def _check_pattern_for_count_mismatch(
        self,
        pattern: str,
        pattern_map: dict[str, str],
        content: str,
        file_path: Path,
        expected_count: int,
    ) -> tuple[Path, int, int] | None:
        if pattern not in pattern_map:
            return None

        safe_pattern = SAFE_PATTERNS[pattern_map[pattern]]
        if not safe_pattern.test(content):
            return None

        return self._find_count_mismatch_in_matches(
            safe_pattern,
            content,
            file_path,
            expected_count,
        )

    def _find_count_mismatch_in_matches(
        self,
        safe_pattern: t.Any,
        content: str,
        file_path: Path,
        expected_count: int,
    ) -> tuple[Path, int, int] | None:
        matches = safe_pattern.findall(content)

        for match in matches:
            count = int(match)
            if self._is_count_mismatch(count, expected_count):
                return (file_path, count, expected_count)

        return None

    def _is_count_mismatch(self, count: int, expected_count: int) -> bool:
        return count != expected_count and count > 4

    def _fix_agent_count_references(
        self,
        content: str,
        current_count: int,
        expected_count: int,
    ) -> str:
        updated_content = content

        agent_pattern = SAFE_PATTERNS["update_agent_count"]
        specialized_pattern = SAFE_PATTERNS["update_specialized_agent_count"]
        config_pattern = SAFE_PATTERNS["update_total_agents_config"]
        sub_agent_pattern = SAFE_PATTERNS["update_sub_agent_count"]

        updated_content = agent_pattern.apply(updated_content).replace(
            "NEW_COUNT",
            str(expected_count),
        )
        updated_content = specialized_pattern.apply(updated_content).replace(
            "NEW_COUNT",
            str(expected_count),
        )
        updated_content = config_pattern.apply(updated_content).replace(
            "NEW_COUNT",
            str(expected_count),
        )
        return sub_agent_pattern.apply(updated_content).replace(
            "NEW_COUNT",
            str(expected_count),
        )

    def _detect_api_changes(self) -> list[dict[str, str]]:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~5..HEAD", "*.py"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return []

            changed_files = result.stdout.strip().split("\n")
            api_changes: list[dict[str, str]] = []

            for file_path in changed_files:
                if file_path and (
                    "api" in file_path.lower() or "__init__" in file_path
                ):
                    change_info: dict[str, str] = {
                        "file": file_path,
                        "type": "potential_api_change",
                    }
                    api_changes.append(change_info)

            return api_changes

        except Exception:
            return []

    async def _fix_broken_link(self, issue: Issue) -> FixResult:
        self.log(f"Fixing broken link in {issue.file_path}")

        if not issue.file_path:
            return self._create_error_result(
                "No file path provided for broken link fix"
            )

        target_file = self._extract_target_file_from_details(issue.details)
        content = self._read_file_content(issue.file_path)
        if content is None:
            return self._create_error_result(f"Failed to read {issue.file_path}")

        updated_content = self._fix_or_remove_broken_link_line(
            content, issue.file_path, issue.line_number, target_file
        )

        return self._write_fixed_content(issue.file_path, updated_content, target_file)

    def _extract_target_file_from_details(self, details: list[str]) -> str | None:
        for detail in details:
            if detail.startswith("Target file:"):
                return detail.split(":", 1)[1].strip()
        return None

    def _read_file_content(self, file_path: str) -> str | None:
        return self.context.get_file_content(file_path)

    def _create_error_result(self, message: str) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[message],
        )

    def _fix_or_remove_broken_link_line(
        self,
        content: str,
        file_path: str,
        line_number: int | None,
        target_file: str | None,
    ) -> str:
        """Fix or remove a broken link line.

        If line_number is provided, fix that specific line.
        Otherwise, search for the target file reference in the content.
        """
        lines = content.split("\n")
        updated_lines = []
        fixed = False

        for i, line in enumerate(lines):
            # Check if this is the line to fix
            should_fix = False
            if line_number is not None and i + 1 == line_number:
                should_fix = True
            elif target_file and not fixed and target_file in line:
                # No line number, but found the target in this line
                should_fix = True

            if should_fix:
                fixed_line = self._attempt_link_fix(target_file, line, file_path, i + 1)
                if fixed_line is not None:
                    updated_lines.append(fixed_line)
                    fixed = True
                # If fixed_line is None, the line is removed entirely
            else:
                updated_lines.append(line)

        return "\n".join(updated_lines)

    def _attempt_link_fix(
        self,
        target_file: str | None,
        line: str,
        file_path: str,
        line_number: int | None,
    ) -> str | None:
        if target_file:
            fixed_link = self._find_and_fix_link(target_file, line, file_path)
            if fixed_link != line:
                self.log(f"Fixed link to {target_file} in {file_path}:{line_number}")
                return fixed_link

        self.log(f"Removing unfixable broken link in {file_path}:{line_number}")
        return None

    def _write_fixed_content(
        self, file_path: str, updated_content: str, target_file: str | None
    ) -> FixResult:
        success = self.context.write_file_content(file_path, updated_content)

        if not success:
            return self._create_error_result(
                f"Failed to write fixed content to {file_path}"
            )

        message = self._create_success_message(file_path, target_file)
        return FixResult(
            success=True,
            confidence=0.85,
            fixes_applied=[message],
            files_modified=[file_path],
        )

    def _create_success_message(self, file_path: str, target_file: str | None) -> str:
        if target_file:
            return f"Fixed broken link to '{target_file}' in {file_path}"
        return f"Removed broken link from {file_path}"

    def _find_and_fix_link(self, target_file: str, line: str, source_file: str) -> str:
        search_paths = [
            Path(target_file),
            Path("docs") / target_file,
            Path("docs") / "reference" / target_file,
            Path("docs") / "features" / target_file,
            Path("docs") / "guides" / target_file,
        ]

        for path in search_paths:
            if path.exists():
                source_path = Path(source_file).parent
                with suppress(ValueError):
                    relative_path = path.relative_to(source_path)

                    new_link = str(relative_path)

                    import re

                    pattern = r"\[([^\]]+)\]\([^)]*?" + re.escape(target_file) + r"\)"

                    def replace_link(match: t.Match[str]) -> str:
                        text = match.group(1)
                        return f"[{text}]({new_link})"

                    fixed_line = re.sub(pattern, replace_link, line)
                    return fixed_line

        return line

    def _update_readme_examples(
        self,
        content: str,
        api_changes: list[dict[str, str]],
    ) -> str:
        if api_changes and "TODO: Update examples" not in content:
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if line.startswith("# ") and i < len(lines) - 1:
                    lines.insert(
                        i + 2,
                        "<!-- TODO: Update examples after recent API changes -->",
                    )
                    break
            return "\n".join(lines)

        return content


agent_registry.register(DocumentationAgent)
