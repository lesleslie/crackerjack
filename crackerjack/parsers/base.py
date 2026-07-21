from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from crackerjack.agents.base import Issue


class ToolParser(Protocol):
    def parse(self, output: str, tool_name: str) -> list[Issue]: ...

    def validate_output(
        self,
        output: str,
        expected_count: int | None = None,
    ) -> bool: ...


class JSONParser(ABC):
    @abstractmethod
    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]: ...

    @abstractmethod
    def get_issue_count(self, data: dict[str, object] | list[object]) -> int: ...

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        import logging

        logging.getLogger(__name__)

        output = output.strip()
        if not output:
            from crackerjack.parsers.factory import ParsingError

            raise ParsingError(
                "Empty output",
                tool_name=tool_name,
                output=output,
            )

        start_idx = self._find_json_start(output)

        if start_idx == -1:
            from crackerjack.parsers.factory import ParsingError

            raise ParsingError(
                "No JSON found in output",
                tool_name=tool_name,
                output=output[:200],
            )

        json_str = self._extract_json_string(output, start_idx)
        data = self._parse_json_string(json_str, tool_name, output)
        return self.parse_json(data)

    @staticmethod
    def _find_json_start(output: str) -> int:
        brace_idx = output.find("{")
        bracket_idx = output.find("[")
        if brace_idx == -1:
            return bracket_idx
        if bracket_idx == -1:
            return brace_idx
        return min(brace_idx, bracket_idx)

    def _extract_json_string(self, output: str, start_idx: int) -> str:
        if output[start_idx] == "{":
            return self._extract_json_by_braces(output, start_idx, "{", "}")
        return self._extract_json_by_braces(output, start_idx, "[", "]")

    @staticmethod
    def _extract_json_by_braces(
        output: str, start_idx: int, open_brace: str, close_brace: str
    ) -> str:
        depth = 0
        for i in range(start_idx, len(output)):
            if output[i] == open_brace:
                depth += 1
            elif output[i] == close_brace:
                depth -= 1
                if depth == 0:
                    return output[start_idx : i + 1]
        return output[start_idx:]

    @staticmethod
    def _parse_json_string(
        json_str: str, tool_name: str, original_output: str
    ) -> dict[str, object] | list[object]:
        import json

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            from crackerjack.parsers.factory import ParsingError

            raise ParsingError(
                f"Invalid JSON output: {e}",
                tool_name=tool_name,
                output=original_output[:500],
            ) from e


class RegexParser(ABC):
    @abstractmethod
    def parse_text(self, output: str) -> list[Issue]: ...

    def get_line_count(self, output: str) -> int:
        if not output:
            return 0

        lines = output.split("\n")
        return len([line for line in lines if line.strip() and ":" in line])
