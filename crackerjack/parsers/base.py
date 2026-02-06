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
        self._process_general_1()
        self._process_loop_2()

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        self._process_general_1()
        self._process_loop_2()

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        self._process_general_1()
        self._process_loop_2()

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        self._process_general_1()
        self._process_loop_2()

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        self._process_general_1()
        self._process_loop_2()

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        import json

        try:
            # Tool may output error messages or text before/after JSON
            # Extract only the JSON portion by finding the first { and last }
            output = output.strip()
            if not output:
                from crackerjack.parsers.factory import ParsingError

                raise ParsingError(
                    "Empty output",
                    tool_name=tool_name,
                    output=output,
                )

            # Find JSON object boundaries
            start_idx = output.find("{")
            if start_idx == -1:
                start_idx = output.find("[")  # Handle JSON arrays

            if start_idx == -1:
                from crackerjack.parsers.factory import ParsingError

                raise ParsingError(
                    "No JSON found in output",
                    tool_name=tool_name,
                    output=output[:200],
                )

            # Find matching end bracket
            if output[start_idx] == "{":
                # Find matching closing brace
                depth = 0

                for i in range(start_idx, len(output)):
                    if output[i] == "{":
                        depth += 1
                    elif output[i] == "}":
                        depth -= 1
                        if depth == 0:
                            output = output[start_idx : i + 1]
                            break
            else:  # Array start
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
