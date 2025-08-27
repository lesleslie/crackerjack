import re
import subprocess
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from .base import (
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class DocumentationAgent(SubAgent):
    """Agent specialized in maintaining documentation consistency and changelog updates."""

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DOCUMENTATION}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.DOCUMENTATION:
            return 0.8
        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing documentation issue: {issue.message}")

        try:
            # Detect what type of documentation update is needed
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
        """Update CHANGELOG.md with recent changes."""
        self.log("Updating changelog with recent changes")

        changelog_path = Path("CHANGELOG.md")

        # Get recent commits since last version tag
        recent_changes = self._get_recent_changes()

        if not recent_changes:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No recent changes to add to changelog"],
            )

        # Generate changelog entry
        changelog_entry = self._generate_changelog_entry(recent_changes)

        # Update or create changelog
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
        """Fix consistency issues across documentation files."""
        self.log("Checking documentation consistency")

        # Find all markdown files
        md_files = list(Path().glob("*.md")) + list(Path("docs").glob("*.md"))

        # Check agent count consistency
        agent_count_issues = self._check_agent_count_consistency(md_files)

        files_modified: list[str] = []
        fixes_applied: list[str] = []

        for file_path, current_count, expected_count in agent_count_issues:
            content = self.context.get_file_content(file_path)
            if content:
                # Fix agent count references
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
        """Update API documentation when public interfaces change."""
        self.log("Updating API documentation")

        # Check for API changes by analyzing recent modifications
        api_changes = self._detect_api_changes()

        if not api_changes:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=[
                    "No API changes detected requiring documentation updates",
                ],
            )

        # Update README examples
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
        """Handle general documentation updates."""
        self.log("Performing general documentation update")

        # Add review comments for manual review

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
        """Get recent git commits since last version tag."""
        try:
            commit_range = self._get_commit_range()
            if not commit_range:
                return []

            commit_messages = self._get_commit_messages(commit_range)
            return self._parse_commit_messages(commit_messages)

        except Exception:
            return []

    def _get_commit_range(self) -> str:
        """Determine the commit range for changelog generation."""
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            last_tag = result.stdout.strip()
            return f"{last_tag}..HEAD"

        # No tags found, get last 10 commits
        return "-10"

    def _get_commit_messages(self, commit_range: str) -> str:
        """Get formatted commit messages for the given range."""
        result = subprocess.run(
            ["git", "log", commit_range, "--pretty=format:%s|%h|%an"],
            capture_output=True,
            text=True,
            check=False,
        )

        return result.stdout.strip() if result.returncode == 0 else ""

    def _parse_commit_messages(self, commit_output: str) -> list[dict[str, str]]:
        """Parse git log output into structured change information."""
        changes: list[dict[str, str]] = []

        for line in commit_output.split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 2:
                    change_info: dict[str, str] = {
                        "message": parts[0],
                        "hash": parts[1],
                        "author": parts[2] if len(parts) > 2 else "Unknown",
                    }
                    changes.append(change_info)

        return changes

    def _generate_changelog_entry(self, changes: list[dict[str, str]]) -> str:
        """Generate a formatted changelog entry."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        entry_lines = [f"## [Unreleased] - {date_str}", ""]

        categorized_changes = self._categorize_changes(changes)
        self._add_categorized_changes_to_entry(entry_lines, categorized_changes)

        return "\n".join(entry_lines)

    def _categorize_changes(
        self,
        changes: list[dict[str, str]],
    ) -> dict[str, list[str]]:
        """Categorize changes by type."""
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
        """Determine the category for a change message."""
        if message.startswith(("feat:", "feature:")):
            return "features"
        if message.startswith("fix:"):
            return "fixes"
        if message.startswith(("refactor:", "refact:")):
            return "refactors"
        return "other"

    def _add_categorized_changes_to_entry(
        self,
        entry_lines: list[str],
        categories: dict[str, list[str]],
    ) -> None:
        """Add categorized changes to the entry lines."""
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
        """Add a section with items to the entry lines."""
        entry_lines.append(section_title)
        for item in items:
            entry_lines.append(f"- {item}")
        entry_lines.append("")

    def _insert_changelog_entry(self, content: str, entry: str) -> str:
        """Insert new changelog entry at the top."""
        lines = content.split("\n")

        # Find where to insert (after title and before first entry)
        insert_index = 0
        for i, line in enumerate(lines):
            if line.startswith(("# ", "## ")):
                if i > 0:  # Skip the main title
                    insert_index = i
                    break

        # Insert the new entry
        new_lines = (
            lines[:insert_index] + entry.split("\n") + [""] + lines[insert_index:]
        )
        return "\n".join(new_lines)

    def _create_initial_changelog(self, entry: str) -> str:
        """Create initial CHANGELOG.md with first entry."""
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
        """Check for inconsistent agent count references across documentation."""
        expected_count = 9  # Current total with DocumentationAgent
        issues: list[tuple[Path, int, int]] = []
        patterns = self._get_agent_count_patterns()

        for file_path in md_files:
            issue = self._check_file_agent_count(file_path, patterns, expected_count)
            if issue:
                issues.append(issue)

        return issues

    def _get_agent_count_patterns(self) -> list[str]:
        """Get regex patterns for detecting agent count references."""
        return [
            r"(\d+)\s+agents",
            r"(\d+)\s+specialized\s+agents",
            r'total_agents["\']:\s*(\d+)',
            r"(\d+)\s+sub-agents",
        ]

    def _check_file_agent_count(
        self,
        file_path: Path,
        patterns: list[str],
        expected_count: int,
    ) -> tuple[Path, int, int] | None:
        """Check a single file for agent count inconsistencies."""
        with suppress(Exception):
            content = self.context.get_file_content(file_path)
            if not content:
                return None

            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    count = int(match)
                    if (
                        count != expected_count and count > 4
                    ):  # Filter out unrelated numbers
                        return (file_path, count, expected_count)

        return None

    def _fix_agent_count_references(
        self,
        content: str,
        current_count: int,
        expected_count: int,
    ) -> str:
        """Fix agent count references in documentation."""
        # Replace various agent count patterns
        patterns_replacements = [
            (rf"\b{current_count}\s+agents\b", f"{expected_count} agents"),
            (
                rf"\b{current_count}\s+specialized\s+agents\b",
                f"{expected_count} specialized agents",
            ),
            (
                rf'total_agents["\']:\s*{current_count}',
                f'total_agents": {expected_count}',
            ),
            (rf"\b{current_count}\s+sub-agents\b", f"{expected_count} sub-agents"),
        ]

        updated_content = content
        for pattern, replacement in patterns_replacements:
            updated_content = re.sub(
                pattern,
                replacement,
                updated_content,
                flags=re.IGNORECASE,
            )

        return updated_content

    def _detect_api_changes(self) -> list[dict[str, str]]:
        """Detect recent API changes that might affect documentation."""
        # This is a simplified implementation - in practice would use AST analysis
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

    def _update_readme_examples(
        self,
        content: str,
        api_changes: list[dict[str, str]],
    ) -> str:
        """Update README examples based on API changes."""
        # This is a placeholder - real implementation would parse and update code examples
        # For now, just add a comment noting API changes
        if api_changes and "TODO: Update examples" not in content:
            # Add a note about updating examples
            lines = content.split("\n")
            # Insert near the top after the title
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
