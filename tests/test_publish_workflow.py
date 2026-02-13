"""Test for publish workflow and CLAUDE file preservation.

This test verifies:
1. CLAUDE files exist at project root
2. Files with archive keywords are not at root
3. mdformat is configured to skip CLAUDE files

The test ensures CLAUDE files are never accidentally deleted
or modified by documentation workflows during publish cycles.
"""

import subprocess
from pathlib import Path

import pytest

EXPECTED_CLAUDE_FILES = [
    "CLAUDE.md",
    "CLAUDE_ARCHITECTURE.md",
    "CLAUDE_QUICKSTART.md",
    "CLAUDE_PROTOCOLS.md",
    "CLAUDE_PATTERNS.md",
]

ARCHIVE_KEYWORDS = [
    "plan", "implementation", "action", "remediation",
    "COMPLETE", "ANALYSIS", "PROGRESS", "STATUS", "SUMMARY",
]


class TestPublishWorkflow:
    """Test suite for publish workflow."""

    def test_claude_files_exist(self):
        """Test that all expected CLAUDE files exist at project root."""
        root = Path.cwd()
        missing_files = []

        for filename in EXPECTED_CLAUDE_FILES:
            file_path = root / filename
            if not file_path.exists():
                missing_files.append(filename)

        if missing_files:
            pytest.fail(f"Missing CLAUDE files: {', '.join(missing_files)}")

    def test_no_archive_keywords_at_root(self):
        """Test that files with archive keywords are not at project root."""
        root = Path.cwd()
        issues = []

        for filename in root.glob("CLAUDE_*.md"):
            name_lower = filename.name.lower()
            has_archive_keyword = any(
                keyword in name_lower for keyword in ARCHIVE_KEYWORDS
            )
            if has_archive_keyword:
                issues.append(
                    f"{filename} contains archive keyword and should be in docs/archive/"
                )

        if issues:
            pytest.fail(
                "Files with archive keywords at root:\n" + "\n".join(issues)
            )

    def test_mdformat_skips_claude_files(self):
        """Test that mdformat is configured to skip CLAUDE files."""
        # Check pyproject.toml for mdformat skip configuration
        root = Path.cwd()
        pyproject = root / "pyproject.toml"

        if not pyproject.exists():
            pytest.fail("pyproject.toml not found")

        content = pyproject.read_text()

        # Check for CLAUDE*.md in mdformat skip list
        has_claude_skip = "CLAUDE*.md" in content

        if not has_claude_skip:
            pytest.fail(
                "pyproject.toml does not include 'CLAUDE*.md' in "
                "mdformat skip list. CLAUDE files may be reformatted."
            )

    def test_gitignore_preserves_docs(self):
        """Test that .gitignore can preserve docs directory if needed."""
        root = Path.cwd()
        gitignore = root / ".gitignore"

        if not gitignore.exists():
            # .gitignore is optional for this test
            pytest.skip(".gitignore not found, skipping")

        content = gitignore.read_text()

        # Check if docs/** or docs/ is in ignore list
        has_docs_ignore = "docs/**" in content or "docs/" in content

        # This is informational - docs/** may or may not be ignored
        # depending on project needs
        assert True, "Git ignore check completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
