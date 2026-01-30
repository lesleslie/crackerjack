"""Parser factory for tool output parsing.

This module provides a factory for creating appropriate parsers for each tool
and validates parsing results to ensure correctness.
"""

import json
import logging

from crackerjack.agents.base import Issue
from crackerjack.models.tool_config import supports_json
from crackerjack.parsers.base import JSONParser, RegexParser, ToolParser

logger = logging.getLogger(__name__)


class ParsingError(Exception):
    """Error raised when parsing fails validation.

    This exception provides detailed context about parsing failures,
    including the tool name, expected vs actual issue counts, and
    output preview for debugging.
    """

    def __init__(
        self,
        message: str,
        tool_name: str,
        expected_count: int | None = None,
        actual_count: int | None = None,
        output: str | None = None,
    ) -> None:
        """Initialize a ParsingError.

        Args:
            message: Error message
            tool_name: Name of the tool that failed to parse
            expected_count: Expected number of issues
            actual_count: Actual number of issues parsed
            output: Raw tool output (for debugging)
        """
        super().__init__(message)
        self.tool_name = tool_name
        self.expected_count = expected_count
        self.actual_count = actual_count
        self.output = output

    def __str__(self) -> str:
        """Return detailed error message."""
        parts = [super().__str__()]

        if self.expected_count is not None and self.actual_count is not None:
            parts.append(
                f"  Expected: {self.expected_count} issues, "
                f"got: {self.actual_count} issues"
            )

        if self.output:
            preview = self.output[:200]
            if len(self.output) > 200:
                preview += "..."
            parts.append(f"  Output preview: {preview}")

        return "\n".join(parts)


class ParserFactory:
    """Factory for creating tool output parsers with validation.

    This factory automatically selects the appropriate parser (JSON or regex)
    based on tool configuration and validates that parsing succeeds correctly.

    Attributes:
        _json_parsers: Registry of JSON parser classes
        _regex_parsers: Registry of regex parser classes
        _parser_cache: Cache of parser instances
    """

    def __init__(self) -> None:
        """Initialize the parser factory."""
        self._json_parsers: dict[str, type[JSONParser]] = {}
        self._regex_parsers: dict[str, type[RegexParser]] = {}
        self._parser_cache: dict[str, ToolParser] = {}

        # Register parsers (will be populated by JSON parsers module)
        self._register_parsers()

    def _register_parsers(self) -> None:
        """Register available parsers.

        This is called during initialization to populate the parser registries.
        JSON parsers are imported and registered here.
        """
        # Import and register JSON parsers
        try:
            from crackerjack.parsers.json_parsers import (
                register_json_parsers,
            )

            register_json_parsers(self)
        except ImportError as e:
            logger.warning(f"Failed to import JSON parsers: {e}")

        # Import and register regex parsers
        try:
            from crackerjack.parsers.regex_parsers import (
                register_regex_parsers,
            )

            register_regex_parsers(self)
        except ImportError as e:
            logger.warning(f"Failed to import regex parsers: {e}")

    def register_json_parser(
        self, tool_name: str, parser_class: type[JSONParser]
    ) -> None:
        """Register a JSON parser for a tool.

        Args:
            tool_name: Name of the tool
            parser_class: JSON parser class
        """
        self._json_parsers[tool_name] = parser_class
        logger.debug(f"Registered JSON parser for '{tool_name}'")

    def register_regex_parser(
        self, tool_name: str, parser_class: type[RegexParser]
    ) -> None:
        """Register a regex parser for a tool.

        Args:
            tool_name: Name of the tool
            parser_class: Regex parser class
        """
        self._regex_parsers[tool_name] = parser_class
        logger.debug(f"Registered regex parser for '{tool_name}'")

    def create_parser(self, tool_name: str) -> ToolParser:
        """Create appropriate parser for a tool.

        Strategy:
        1. Check cache for existing parser instance
        2. If tool supports JSON and has JSON parser, use it
        3. Otherwise, use regex parser if available
        4. Fall back to generic parser

        Args:
            tool_name: Name of the tool

        Returns:
            Parser instance (cached or newly created)

        Raises:
            ValueError: If no parser is available for the tool
        """
        # Check cache first
        if tool_name in self._parser_cache:
            return self._parser_cache[tool_name]

        # Select parser type
        if supports_json(tool_name) and tool_name in self._json_parsers:
            logger.debug(f"Using JSON parser for '{tool_name}'")
            parser = self._json_parsers[tool_name]()
        elif tool_name in self._regex_parsers:
            logger.debug(f"Using regex parser for '{tool_name}'")
            parser = self._regex_parsers[tool_name]()
        else:
            raise ValueError(f"No parser available for tool '{tool_name}'")

        # Cache the instance
        self._parser_cache[tool_name] = parser
        return parser

    def parse_with_validation(
        self,
        tool_name: str,
        output: str,
        expected_count: int | None = None,
    ) -> list[Issue]:
        """Parse tool output with validation.

        This method automatically detects JSON vs text output, parses accordingly,
        and validates that the expected number of issues were extracted.

        Args:
            tool_name: Name of the tool
            output: Raw tool output (JSON or text)
            expected_count: Expected number of issues (for validation)

        Returns:
            List of parsed Issue objects

        Raises:
            ParsingError: If validation fails or parsing encounters an error
        """
        parser = self.create_parser(tool_name)

        # Detect if output is JSON
        is_json = self._is_json_output(output)

        if is_json:
            issues = self._parse_json_output(parser, output, tool_name)
        else:
            issues = self._parse_text_output(parser, output, tool_name)

        # Validation
        if expected_count is not None:
            self._validate_issue_count(issues, expected_count, tool_name, output)

        return issues

    def _is_json_output(self, output: str) -> bool:
        """Detect if output is JSON format.

        Args:
            output: Raw tool output

        Returns:
            True if output appears to be JSON, False otherwise
        """
        stripped = output.strip()
        return stripped.startswith(("{", "["))

    def _parse_json_output(
        self, parser: ToolParser, output: str, tool_name: str
    ) -> list[Issue]:
        """Parse JSON output.

        Args:
            parser: Parser instance (should be JSONParser)
            output: Raw JSON output
            tool_name: Name of the tool

        Returns:
            List of parsed Issue objects

        Raises:
            ParsingError: If JSON is invalid or parser doesn't support JSON
        """
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from '{tool_name}': {e}")
            logger.debug(f"Output preview: {output[:500]}")
            raise ParsingError(
                f"Invalid JSON output from {tool_name}: {e}",
                tool_name=tool_name,
                output=output,
            ) from e

        # Check if parser supports JSON
        if not isinstance(parser, JSONParser):
            logger.warning(
                f"JSON output detected but parser for '{tool_name}' "
                f"doesn't support JSON, falling back to text parsing"
            )
            # For now, return empty list - could try text parsing as fallback
            return []

        try:
            return parser.parse_json(data)
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to parse JSON data from '{tool_name}': {e}")
            raise ParsingError(
                f"Error parsing JSON data from {tool_name}: {e}",
                tool_name=tool_name,
                output=output,
            ) from e

    def _parse_text_output(
        self, parser: ToolParser, output: str, tool_name: str
    ) -> list[Issue]:
        """Parse text output.

        Args:
            parser: Parser instance (should be RegexParser)
            output: Raw text output
            tool_name: Name of the tool

        Returns:
            List of parsed Issue objects
        """
        if isinstance(parser, RegexParser):
            return parser.parse_text(output)
        else:
            # Fallback: call generic parse method
            return parser.parse(output, tool_name)

    def _validate_issue_count(
        self,
        issues: list[Issue],
        expected_count: int,
        tool_name: str,
        output: str,
    ) -> None:
        """Validate that parsed issue count matches expected.

        Args:
            issues: Parsed issues
            expected_count: Expected number of issues
            tool_name: Name of the tool
            output: Raw tool output

        Raises:
            ParsingError: If count doesn't match
        """
        actual_count = len(issues)

        if actual_count != expected_count:
            error_msg = (
                f"Issue count mismatch for '{tool_name}': "
                f"expected {expected_count}, parsed {actual_count}"
            )

            logger.error(error_msg)
            logger.debug(f"Output preview: {output[:500]}")
            logger.debug(f"Parsed issues: {[str(i)[:100] for i in issues[:5]]}")

            raise ParsingError(
                error_msg,
                tool_name=tool_name,
                expected_count=expected_count,
                actual_count=actual_count,
                output=output,
            )

        logger.debug(
            f"Validation passed for '{tool_name}': "
            f"{actual_count} issues parsed (expected {expected_count})"
        )
