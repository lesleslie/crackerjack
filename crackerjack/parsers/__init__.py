"""Parser package for tool output parsing.

This package provides JSON-based and regex-based parsers for various quality tools,
replacing fragile regex-only parsing with robust structured data parsing.
"""

from crackerjack.parsers.base import JSONParser, RegexParser, ToolParser
from crackerjack.parsers.factory import ParserFactory, ParsingError

__all__ = [
    "ToolParser",
    "JSONParser",
    "RegexParser",
    "ParserFactory",
    "ParsingError",
]
