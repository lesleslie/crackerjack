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
    @abstractmethod
    def parse_text(self, output: str) -> list[Issue]: ...

    def get_line_count(self, output: str) -> int:
        if not output:
            return 0

        lines = output.split("\n")
        return len([line for line in lines if line.strip() and ":" in line])
