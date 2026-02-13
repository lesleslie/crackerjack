"""Simplified test to verify CLAUDE files exist and are preserved."""

from pathlib import Path

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


def test_all_claude_files_exist():
    """Test that all expected CLAUDE files exist at project root."""
    root = Path.cwd()
    missing_files = []

    for filename in EXPECTED_CLAUDE_FILES:
        file_path = root / filename
        if not file_path.exists():
            missing_files.append(filename)

    if missing_files:
        raise AssertionError(f"Missing CLAUDE files: {', '.join(missing_files)}")

    # All files exist
    assert all((root / fname).exists() for fname in EXPECTED_CLAUDE_FILES)


def test_files_dont_have_archive_keywords():
    """Test that files with archive keywords are not at project root."""
    root = Path.cwd()
    issues = []

    for filename in root.glob("CLAUDE_*.md"):
        # Check if filename contains archive keywords (case-insensitive)
        name_lower = filename.name.lower()
        has_archive_keyword = any(keyword in name_lower for keyword in ARCHIVE_KEYWORDS)
        if has_archive_keyword:
            issues.append(
                f"{filename} contains archive keyword and should be in docs/archive/"
            )

    if issues:
        raise AssertionError(f"Files with archive keywords at root:\n" + "\n".join(issues))

    # No files with archive keywords at root
    assert not any(
        keyword.lower() in Path(name).name.lower()
        for keyword in ARCHIVE_KEYWORDS
        for name in root.glob("CLAUDE_*.md")
    )


if __name__ == "__main__":
    test_all_claude_files_exist()
    test_files_dont_have_archive_keywords()
    print("✅ All CLAUDE preservation tests passed!")
