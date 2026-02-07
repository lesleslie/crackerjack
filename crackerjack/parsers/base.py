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
        import logging

        logger = logging.getLogger(__name__)

        try:
            output = output.strip()
            if not output:
                from crackerjack.parsers.factory import ParsingError

                raise ParsingError(
                    "Empty output",
                    tool_name=tool_name,
                    output=output,
                )

            brace_idx = output.find("{")
            bracket_idx = output.find("[")

            if brace_idx == -1:
                start_idx = bracket_idx
            elif bracket_idx == -1:
                start_idx = brace_idx
            else:
                start_idx = min(brace_idx, bracket_idx)

            if start_idx == -1:
                from crackerjack.parsers.factory import ParsingError

                raise ParsingError(
                    "No JSON found in output",
                    tool_name=tool_name,
                    output=output[:200],
                )

            if output[start_idx] == "{":
                depth = 0

                for i in range(start_idx, len(output)):
                    if output[i] == "{":
                        depth += 1
                    elif output[i] == "}":
                        depth -= 1
                        if depth == 0:
                            output = output[start_idx : i + 1]
                            break
            else:
                depth = 0
                for i in range(start_idx, len(output)):
                    if output[i] == "[":
                        depth += 1
                    elif output[i] == "]":
                        depth -= 1
                        if depth == 0:
                            output = output[start_idx : i + 1]
                            break

            data = json.loads(output)
            logger.debug(
                f"🐛 PARSE DEBUG ({tool_name}): json.loads() returned {type(data).__name__}"
            )
        except json.JSONDecodeError as e:
            from crackerjack.parsers.factory import ParsingError

            raise ParsingError(
                f"Invalid JSON output: {e}",
                tool_name=tool_name,
                output=output[:500],
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
