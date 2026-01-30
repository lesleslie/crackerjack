"""Base parser interfaces and protocols.

This module defines the protocol-based interfaces that all parsers must implement,
following crackerjack's architecture pattern of protocol-based dependency injection.
"""

from abc import ABC, abstractmethod
from typing import Protocol

from crackerjack.agents.base import Issue


class ToolParser(Protocol):
    """Protocol for tool output parsers.

    All parsers must implement this protocol to ensure consistent interface
    across different parsing strategies (JSON, regex, custom).
    """

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        """Parse tool output into Issue objects.

        Args:
            output: Raw tool output (JSON or text)
            tool_name: Name of the tool for logging/context

        Returns:
            List of parsed Issue objects

        Raises:
            ParsingError: If output cannot be parsed
        """
        ...

    def validate_output(
        self,
        output: str,
        expected_count: int | None = None,
    ) -> bool:
        """Validate that output was parsed correctly.

        Args:
            output: Raw tool output
            expected_count: Expected number of issues (for validation)

        Returns:
            True if validation passes

        Raises:
            ParsingError: If validation fails
        """
        ...


class JSONParser(ABC):
    """Base class for JSON-based parsers.

    JSON parsers work with structured data from tools that support JSON output.
    This is the preferred parsing strategy for tools that support it.
    """

    @abstractmethod
    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        """Parse JSON data into Issue objects.

        Args:
            data: Parsed JSON data (dict or list)

        Returns:
            List of Issue objects

        Raises:
            KeyError: If required fields are missing
            TypeError: If data structure is invalid
        """
        ...

    @abstractmethod
    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        """Extract issue count from JSON data.

        Args:
            data: Parsed JSON data

        Returns:
            Number of issues in the data

        Note:
            This is used for validation to ensure all issues were parsed.
        """
        ...

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        """Parse JSON output string into Issue objects.

        This is a convenience method that handles JSON parsing and delegation
        to parse_json(). Subclasses that need custom JSON extraction (like
        reading from files) should override this method.

        Args:
            output: Raw JSON string output from tool
            tool_name: Name of the tool (for logging, currently unused)

        Returns:
            List of Issue objects

        Raises:
            ParsingError: If JSON is invalid or parsing fails
        """
        import json

        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            from crackerjack.parsers.factory import ParsingError

            raise ParsingError(
                f"Invalid JSON output: {e}",
                tool_name=tool_name,
                output=output,
            ) from e

        return self.parse_json(data)


class RegexParser(ABC):
    """Base class for regex-based parsers.

    Regex parsers are used as fallback for tools that don't support JSON output.
    These parsers use pattern matching to extract issues from text output.
    """

    @abstractmethod
    def parse_text(self, output: str) -> list[Issue]:
        """Parse text output into Issue objects.

        Args:
            output: Raw text output from tool

        Returns:
            List of Issue objects

        Note:
            Lines that don't match the expected pattern are silently skipped,
            but the total count should be validated against expected_count.
        """
        ...

    def get_line_count(self, output: str) -> int:
        """Count potential issue lines in text output.

        Args:
            output: Raw text output from tool

        Returns:
            Estimated number of issue lines

        Note:
            This is a rough estimate for validation. The actual count may differ
            due to multi-line issues, summary lines, etc.
        """
        if not output:
            return 0

        lines = output.split("\n")
        return len([line for line in lines if line.strip() and ":" in line])
