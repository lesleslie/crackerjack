import logging

from crackerjack.agents.base import Issue
from crackerjack.models.tool_config import supports_json
from crackerjack.parsers.base import JSONParser, RegexParser

logger = logging.getLogger(__name__)


class ParsingError(Exception):
    def __init__(
        self,
        message: str,
        tool_name: str,
        expected_count: int | None = None,
        actual_count: int | None = None,
        output: str | None = None,
    ) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.expected_count = expected_count
        self.actual_count = actual_count
        self.output = output

    def __str__(self) -> str:
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
    def __init__(self) -> None:
        self._json_parsers: dict[str, type[JSONParser]] = {}
        self._regex_parsers: dict[str, type[RegexParser]] = {}
        self._parser_cache: dict[str, JSONParser | RegexParser] = {}

        self._register_parsers()

    def _register_parsers(self) -> None:
        try:
            from crackerjack.parsers.json_parsers import (
                register_json_parsers,
            )

            register_json_parsers(self)
        except ImportError as e:
            logger.warning(f"Failed to import JSON parsers: {e}")

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
        self._json_parsers[tool_name] = parser_class
        logger.debug(f"Registered JSON parser for '{tool_name}'")

    def register_regex_parser(
        self, tool_name: str, parser_class: type[RegexParser]
    ) -> None:
        self._regex_parsers[tool_name] = parser_class
        logger.debug(f"Registered regex parser for '{tool_name}'")

    def create_parser(self, tool_name: str) -> JSONParser | RegexParser:
        if tool_name in self._parser_cache:
            return self._parser_cache[tool_name]

        parser: JSONParser | RegexParser
        if supports_json(tool_name) and tool_name in self._json_parsers:
            logger.debug(f"Using JSON parser for '{tool_name}'")
            parser = self._json_parsers[tool_name]()
        elif tool_name in self._regex_parsers:
            logger.debug(f"Using regex parser for '{tool_name}'")
            parser = self._regex_parsers[tool_name]()
        else:
            raise ValueError(f"No parser available for tool '{tool_name}'")

        self._parser_cache[tool_name] = parser
        return parser

    def parse_with_validation(
        self,
        tool_name: str,
        output: str,
        expected_count: int | None = None,
    ) -> list[Issue]:
        parser = self.create_parser(tool_name)

        is_json = self._is_json_output(output)

        if is_json:
            issues = self._parse_json_output(parser, output, tool_name)
        else:
            issues = self._parse_text_output(parser, output, tool_name)

        if expected_count is not None:
            self._validate_issue_count(issues, expected_count, tool_name, output)

        return issues

    def _is_json_output(self, output: str) -> bool:

        lines = output.split("\n")

        stripped = output.strip()
        if stripped in ("[*]", "[^)]"):
            return True

        for i, line in enumerate(lines):
            stripped_line = line.lstrip()
            if stripped_line.startswith(("{", "[")):
                sample = "\n".join(lines[i:]).lstrip()[:200]

                if ('"' in sample or "'" in sample) and (":" in sample):
                    return True

                if any(k in sample for k in ('"version"', '"results"', '"errors"')):
                    return True

        return False

    def _parse_json_output(
        self, parser: JSONParser | RegexParser, output: str, tool_name: str
    ) -> list[Issue]:

        stripped = output.strip()

        if stripped == "[*]":
            logger.debug(f"Detected ruff empty output pattern '[*]' for '{tool_name}'")
            output = "[]"

        if stripped == "[^)]":
            logger.debug(f"Detected ruff empty output pattern '[^)]' for '{tool_name}'")
            output = "[]"

        try:
            if isinstance(parser, JSONParser):
                return parser.parse(output, tool_name)
            else:
                logger.warning(
                    f"JSON output detected but using RegexParser for '{tool_name}', "
                    "attempting direct JSON parse"
                )
                import json

                json.loads(output)
                return (
                    parser.parse_text(output) if isinstance(parser, RegexParser) else []
                )
        except ParsingError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse JSON from '{tool_name}': {e}")
            logger.debug(f"Output preview: {output[:500]}")
            raise ParsingError(
                f"Invalid JSON output from {tool_name}: {e}",
                tool_name=tool_name,
                output=output,
            ) from e

    def _parse_text_output(
        self, parser: JSONParser | RegexParser, output: str, tool_name: str
    ) -> list[Issue]:
        if isinstance(parser, RegexParser):
            return parser.parse_text(output)

        return parser.parse(output, tool_name)

    def _validate_issue_count(
        self,
        issues: list[Issue],
        expected_count: int,
        tool_name: str,
        output: str,
    ) -> None:
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
