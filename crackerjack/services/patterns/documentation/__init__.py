"""Documentation-related regex patterns.

This package provides patterns for working with documentation elements including
docstrings, markdown badges, links, comments, and code blocks.
"""

from .badges_markdown import PATTERNS as BADGES_MARKDOWN_PATTERNS
from .comments_blocks import PATTERNS as COMMENTS_BLOCKS_PATTERNS
from .docstrings import PATTERNS as DOCSTRINGS_PATTERNS

# Merge all documentation patterns into a single registry
PATTERNS = DOCSTRINGS_PATTERNS | BADGES_MARKDOWN_PATTERNS | COMMENTS_BLOCKS_PATTERNS

__all__ = ["PATTERNS"]
