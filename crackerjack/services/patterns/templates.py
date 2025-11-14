"""Template parsing and processing patterns."""

import re

from .core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "extract_template_variables": ValidatedPattern(
        name="extract_template_variables",
        pattern=r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}",
        replacement=r"\1",
        description="Extract template variables from {{variable}} patterns",
        test_cases=[
            ("Hello {{name}}", "Hello name"),
            ("{{user_name}}", "user_name"),
            ("{{ spaced_var }}", "spaced_var"),
            ("text {{var1}} and {{var2}}", "text var1 and {{var2}}"),
        ],
    ),
    "extract_template_sections": ValidatedPattern(
        name="extract_template_sections",
        pattern=r"\{\%\s*section\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\%\}",
        replacement=r"\1",
        description="Extract section names from {% section name %} patterns",
        test_cases=[
            ("{% section intro %}", "intro"),
            ("{%  section  main_content  %}", "main_content"),
            ("text {% section footer %} more", "text footer more"),
            ("{% section header_1 %}", "header_1"),
        ],
    ),
    "extract_template_blocks": ValidatedPattern(
        name="extract_template_blocks",
        pattern=r"\{\%\s*block\s+(\w+)\s*\%\}(.*?)\{\%\s*endblock\s*\%\}",
        replacement=r"\1",
        description="Extract block names and content from template blocks",
        flags=re.DOTALL,
        test_cases=[
            ("{% block title %}Hello{% endblock %}", "title"),
            ("{%  block  content  %}Text content{% endblock %}", "content"),
            ("{% block main %}Multi\nline{% endblock %}", "main"),
            (
                "prefix {% block nav %}nav content{% endblock %} suffix",
                "prefix nav suffix",
            ),
        ],
    ),
    "replace_template_block": ValidatedPattern(
        name="replace_template_block",
        pattern=r"\{\%\s*block\s+BLOCK_NAME\s*\%\}.*?\{\%\s*endblock\s*\%\}",
        replacement="REPLACEMENT_CONTENT",
        description="Replace a specific template block (use with dynamic pattern substitution)",
        flags=re.DOTALL,
        test_cases=[
            ("{% block BLOCK_NAME %}old{% endblock %}", "REPLACEMENT_CONTENT"),
            (
                "{%  block  BLOCK_NAME  %}old content{% endblock %}",
                "REPLACEMENT_CONTENT",
            ),
        ],
    ),
}
