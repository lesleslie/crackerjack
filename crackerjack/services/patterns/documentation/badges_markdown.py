"""Badge and markdown link parsing patterns.

This module provides regex patterns for working with markdown syntax,
particularly coverage badges and links in README files.
"""

import re

from ..core import ValidatedPattern

PATTERNS = {
    "detect_coverage_badge": ValidatedPattern(
        name="detect_coverage_badge",
        pattern=r"!\[Coverage.*?\]\(.*?coverage.*?\)|!\[.*coverage.*?\]\(.*?shields\.io.*?coverage.*?\)|https://img\.shields\.io/badge/coverage-[\d\.]+%25-\w+",
        replacement="",
        description="Detect existing coverage badges in README content",
        flags=re.IGNORECASE,
        test_cases=[
            ("![Coverage](https://example.com/coverage.svg)", ""),
            (
                "![Coverage Badge](https://shields.io/coverage-100%25-green)",
                "",
            ),
            (
                "https://img.shields.io/badge/coverage-95.5%25-brightgreen",
                "",
            ),
            (
                "![test coverage](https://img.shields.io/coverage/repo)",
                "",
            ),
            ("Some text without badge", "Some text without badge"),
        ],
    ),
    "extract_markdown_links": ValidatedPattern(
        name="extract_markdown_links",
        pattern=r"\[([^\]]+)\]\(([^)]+)\)",
        replacement=r"\1 -> \2",
        description="Extract markdown link text and URLs from [text](url) patterns",
        test_cases=[
            ("[Click here](http://example.com)", "Click here -> http://example.com"),
            ("[GitHub](https://github.com)", "GitHub -> https://github.com"),
            (
                "[Documentation](./docs/README.md)",
                "Documentation -> ./docs/README.md",
            ),
            ("No links here", "No links here"),
        ],
    ),
    "update_coverage_badge_any": ValidatedPattern(
        name="update_coverage_badge_any",
        pattern=r"(!\[.*coverage.*?\]\()([^)]+)(\))",
        replacement=r"\1NEW_BADGE_URL\3",
        description="Update any coverage-related badge URL",
        flags=re.IGNORECASE,
        test_cases=[
            ("![Coverage](old_url)", "![Coverage](NEW_BADGE_URL)"),
            ("![coverage badge](old_url)", "![coverage badge](NEW_BADGE_URL)"),
            ("![test coverage](url)", "![test coverage](NEW_BADGE_URL)"),
            ("![Other Badge](url)", "![Other Badge](url)"),
        ],
    ),
    "update_coverage_badge_url": ValidatedPattern(
        name="update_coverage_badge_url",
        pattern=r"(!\[Coverage.*?\]\()([^)]+)(\))",
        replacement=r"\1NEW_BADGE_URL\3",
        description="Update coverage badge URL in markdown links",
        test_cases=[
            ("![Coverage](old_url)", "![Coverage](NEW_BADGE_URL)"),
            ("![Coverage Badge](old_badge_url)", "![Coverage Badge](NEW_BADGE_URL)"),
            ("text ![Coverage](url) more", "text ![Coverage](NEW_BADGE_URL) more"),
            ("no badge here", "no badge here"),
        ],
    ),
    "update_shields_coverage_url": ValidatedPattern(
        name="update_shields_coverage_url",
        pattern=r"(https://img\.shields\.io/badge/coverage-[\d\.]+%25-\w+)",
        replacement="NEW_BADGE_URL",
        description="Update shields.io coverage badge URLs directly",
        test_cases=[
            (
                "https://img.shields.io/badge/coverage-95.5%25-brightgreen",
                "NEW_BADGE_URL",
            ),
            (
                "https://img.shields.io/badge/coverage-100%25-success",
                "NEW_BADGE_URL",
            ),
            (
                "https://img.shields.io/badge/coverage-75.0%25-yellow",
                "NEW_BADGE_URL",
            ),
            ("https://example.com/other-badge", "https://example.com/other-badge"),
        ],
    ),
}
