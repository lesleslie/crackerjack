"""Comment and code block parsing patterns.

This module provides regex patterns for working with code comments,
TODO markers, and bash/command code blocks in documentation.
"""

import re

from ..core import ValidatedPattern

PATTERNS = {
    "enhance_command_blocks": ValidatedPattern(
        name="enhance_command_blocks",
        pattern=r"```(?:bash|shell|sh)?\n([^`]+)\n```",
        replacement=r"```bash\n\1\n```",
        description="Enhance command blocks with proper bash syntax highlighting",
        test_cases=[
            ("```\npython -m test\n```", "```bash\npython -m test\n```"),
            ("```bash\necho hello\n```", "```bash\necho hello\n```"),
            ("```sh\nls -la\n```", "```bash\nls -la\n```"),
            ("```shell\ncd /tmp\n```", "```bash\ncd /tmp\n```"),
        ],
    ),
    "extract_bash_command_blocks": ValidatedPattern(
        name="extract_bash_command_blocks",
        pattern=r"```bash\n([^`]+)\n```",
        replacement=r"\1",
        description="Extract content from bash command blocks",
        test_cases=[
            ("```bash\necho hello\n```", "echo hello"),
            ("```bash\npython -m test\n```", "python -m test"),
            ("text\n```bash\nls -la\n```\nmore", "text\nls -la\nmore"),
            ("```bash\nmulti\nline\ncommand\n```", "multi\nline\ncommand"),
        ],
    ),
    "extract_step_numbers": ValidatedPattern(
        name="extract_step_numbers",
        pattern=r"^(\s*)(\d+)\.\s*(.+)$",
        replacement=r"\1**Step \2**: \3",
        description="Extract and enhance numbered steps in documentation",
        flags=re.MULTILINE,
        test_cases=[
            ("1. First step", "**Step 1**: First step"),
            ("  2. Indented step", "  **Step 2**: Indented step"),
            ("10. Double digit step", "**Step 10**: Double digit step"),
            ("normal text", "normal text"),
        ],
    ),
    "preserved_comments": ValidatedPattern(
        name="preserved_comments",
        pattern=r"(#.*?(?: coding: | encoding: | type: | noqa | pragma).*)",
        replacement=r"\1",
        description="Match preserved code comments (encoding, type hints, etc.)",
        test_cases=[
            ("# coding: utf-8", "# coding: utf-8"),
            ("# encoding: utf-8", "# encoding: utf-8"),
            ("# type: ignore", "# type: ignore"),
            ("# noqa: F401", "# noqa: F401"),
            (
                "x = 1  # type: int",
                "x = 1  # type: int",
            ),
            (
                "# pragma: no cover",
                "# pragma: no cover",
            ),
            ("# regular comment", "# regular comment"),
        ],
    ),
    "todo_pattern": ValidatedPattern(
        name="todo_pattern",
        pattern=r"(#.*?TODO.*)",
        replacement=r"\1",
        flags=re.IGNORECASE,
        description="Match TODO comments for validation",
        test_cases=[
            ("# TODO: Fix this", "# TODO: Fix this"),
            ("# todo: implement feature", "# todo: implement feature"),
            ("# Todo: Update docs", "# Todo: Update docs"),
            ("# FIXME: not a TODO", "# FIXME: not a TODO"),
        ],
    ),
}
