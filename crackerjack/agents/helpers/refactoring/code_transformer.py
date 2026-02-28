import logging
import typing as t

from crackerjack.agents.base import AgentContext
from crackerjack.services.regex_patterns import SAFE_PATTERNS


class CodeTransformer:
    def __init__(self, context: AgentContext) -> None:
        self.context = context

    def refactor_complex_functions(
        self,
        content: str,
        complex_functions: list[dict[str, t.Any]],
    ) -> str:
        lines = content.split("\n")

        for func_info in complex_functions:
            func_name = func_info.get("name", "unknown")

            if func_name == "detect_agent_needs":
                refactored = self.refactor_detect_agent_needs_pattern(content)
                if refactored != content:
                    return refactored

            func_content = self._extract_function_content(lines, func_info)
            if func_content:
                extracted_helpers = self._extract_logical_sections(
                    func_content,
                    func_info,
                )
                if extracted_helpers:
                    modified_content = self._apply_function_extraction(
                        content,
                        func_info,
                        extracted_helpers,
                    )
                    if modified_content != content:
                        return modified_content

        return content

    def apply_enhanced_strategies(self, content: str) -> str:
        return self._apply_enhanced_complexity_patterns(content)

    def _apply_enhanced_complexity_patterns(self, content: str) -> str:
        operations = [
            self._extract_nested_conditions,
            self._simplify_boolean_expressions,
            self._extract_validation_patterns,
            self._simplify_data_structures,
        ]

        valid_operations = []
        for op in operations:
            method_name = op.__name__ if hasattr(op, "__name__") else str(op)
            if hasattr(self, method_name):
                valid_operations.append(op)
            else:
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"CodeTransformer operation '{method_name}' not implemented - skipping"
                )

        modified_content = content
        for operation in valid_operations:
            modified_content = operation(modified_content)

        return modified_content

    @staticmethod
    def _extract_nested_conditions(content: str) -> str:
        # This method currently does not implement helper extraction.
        # Return content unchanged to avoid breaking indentation.
        # Future enhancement: implement proper helper method extraction.
        return content

    @staticmethod
    def _simplify_boolean_expressions(content: str) -> str:
        lines = content.split("\n")
        modified_lines = []

        for line in lines:
            simplified = CodeTransformer._apply_boolean_simplifications(line)
            modified_lines.append(simplified)

        return "\n".join(modified_lines)

    @staticmethod
    def _apply_boolean_simplifications(line: str) -> str:
        patterns = [
            ("simplify_double_negation", [" not (not ", "not(not "]),
            ("simplify_and_true", [" and True", "and True "]),
            ("simplify_or_false", [" or False", "or False "]),
            ("simplify_is_true", [" is True"]),
            ("simplify_is_false", [" is False"]),
        ]

        simplified = line
        for pattern_name, indicators in patterns:
            simplified = CodeTransformer._try_apply_pattern(
                simplified, pattern_name, indicators
            )

        return simplified

    @staticmethod
    def _try_apply_pattern(line: str, pattern_name: str, indicators: list[str]) -> str:
        if not CodeTransformer._should_apply_pattern(line, indicators):
            return line

        if pattern_name in SAFE_PATTERNS:
            return SAFE_PATTERNS[pattern_name].apply(line)

        return line

    @staticmethod
    def _should_apply_pattern(line: str, indicators: list[str]) -> bool:
        return any(indicator in line for indicator in indicators)

    @staticmethod
    def _extract_validation_patterns(content: str) -> str:
        if "validation_extract" in SAFE_PATTERNS:
            content = SAFE_PATTERNS["validation_extract"].apply(content)
        else:
            pattern_obj = SAFE_PATTERNS["match_validation_patterns"]
            if pattern_obj.test(content):
                matches = len(
                    [line for line in content.split("\n") if pattern_obj.test(line)],
                )
                if matches > 2:
                    pass

        return content

    @staticmethod
    def _simplify_data_structures(content: str) -> str:
        lines = content.split("\n")
        modified_lines = []

        for line in lines:
            stripped = line.strip()

            if (
                "[" in stripped
                and "for" in stripped
                and "if" in stripped
                and len(stripped) > 80
            ) or (stripped.count(": ") > 5 and stripped.count(", ") > 5):
                pass

            modified_lines.append(line)

        return "\n".join(modified_lines)

    @staticmethod
    def refactor_detect_agent_needs_pattern(content: str) -> str:
        detect_func_start = "async def detect_agent_needs("
        if detect_func_start not in content:
            return content

        original_pattern = """ recommendations = {
        "urgent_agents": [],
        "suggested_agents": [],
        "workflow_recommendations": [],
        "detection_reasoning": "",
    }

    if error_context: """

        replacement_pattern = """ recommendations = {
        "urgent_agents": [],
        "suggested_agents": [],
        "workflow_recommendations": [],
        "detection_reasoning": "",
    }

    _add_urgent_agents_for_errors(recommendations, error_context)
    _add_python_project_suggestions(recommendations, file_patterns)
    _set_workflow_recommendations(recommendations)
    _generate_detection_reasoning(recommendations)

    return json.dumps(recommendations, indent=2)"""

        if original_pattern in content:
            modified_content = content.replace(original_pattern, replacement_pattern)
            if modified_content != content:
                return modified_content

        return content

    def _extract_logical_sections(
        self,
        func_content: str,
        func_info: dict[str, t.Any],
    ) -> list[dict[str, str]]:
        sections: list[dict[str, str]] = []
        lines = func_content.split("\n")
        current_section: list[str] = []
        section_type: str | None = None

        for line in lines:
            stripped = line.strip()

            if self._should_start_new_section(stripped, section_type):
                if current_section:
                    sections.append(
                        self._create_section(
                            current_section,
                            section_type,
                            len(sections),
                        ),
                    )

                current_section, section_type = self._initialize_new_section(
                    line,
                    stripped,
                )
            else:
                current_section.append(line)

        if current_section:
            sections.append(
                self._create_section(current_section, section_type, len(sections)),
            )

        return [s for s in sections if len(s["content"].split("\n")) >= 3]

    @staticmethod
    def _should_start_new_section(
        stripped: str,
        current_section_type: str | None,
    ) -> bool:
        if stripped.startswith("if ") and len(stripped) > 50:
            return True
        return (
            stripped.startswith(("for ", "while ")) and current_section_type != "loop"
        )

    @staticmethod
    def _initialize_new_section(line: str, stripped: str) -> tuple[list[str], str]:
        if stripped.startswith("if ") and len(stripped) > 50:
            return [line], "conditional"
        if stripped.startswith(("for ", "while ")):
            return [line], "loop"
        return [line], "general"

    @staticmethod
    def _create_section(
        current_section: list[str],
        section_type: str | None,
        section_count: int,
    ) -> dict[str, str]:
        effective_type = section_type or "general"
        name_prefix = "handle" if effective_type == "conditional" else "process"

        return {
            "type": effective_type,
            "content": "\n".join(current_section),
            "name": f"_{name_prefix}_{effective_type}_{section_count + 1}",
        }

    @staticmethod
    def _extract_function_content(lines: list[str], func_info: dict[str, t.Any]) -> str:
        start_line = func_info["line_start"] - 1
        end_line = func_info.get("line_end", len(lines)) - 1

        if start_line < 0 or end_line >= len(lines):
            return ""

        return "\n".join(lines[start_line : end_line + 1])

    @staticmethod
    def _apply_function_extraction(
        content: str,
        func_info: dict[str, t.Any],
        extracted_helpers: list[dict[str, str]],
    ) -> str:
        lines = content.split("\n")

        if not CodeTransformer._is_extraction_valid(
            lines,
            func_info,
            extracted_helpers,
        ):
            return "\n".join(lines)

        return CodeTransformer._perform_extraction(lines, func_info, extracted_helpers)

    @staticmethod
    def _is_extraction_valid(
        lines: list[str],
        func_info: dict[str, t.Any],
        extracted_helpers: list[dict[str, str]],
    ) -> bool:
        start_line = func_info["line_start"] - 1
        end_line = func_info.get("line_end", len(lines)) - 1

        return bool(extracted_helpers) and start_line >= 0 and end_line < len(lines)

    @staticmethod
    def _perform_extraction(
        lines: list[str],
        func_info: dict[str, t.Any],
        extracted_helpers: list[dict[str, str]],
    ) -> str:
        new_lines = CodeTransformer._replace_function_with_calls(
            lines,
            func_info,
            extracted_helpers,
        )
        return CodeTransformer._add_helper_definitions(
            new_lines,
            func_info,
            extracted_helpers,
        )

    @staticmethod
    def _replace_function_with_calls(
        lines: list[str],
        func_info: dict[str, t.Any],
        extracted_helpers: list[dict[str, str]],
    ) -> list[str]:
        start_line = func_info["line_start"] - 1
        end_line = func_info.get("line_end", len(lines)) - 1
        func_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
        indent = " " * (func_indent + 4)

        new_func_lines = [lines[start_line]]
        for helper in extracted_helpers:
            new_func_lines.append(f"{indent}self.{helper['name']}()")

        return lines[:start_line] + new_func_lines + lines[end_line + 1 :]

    @staticmethod
    def _add_helper_definitions(
        new_lines: list[str],
        func_info: dict[str, t.Any],
        extracted_helpers: list[dict[str, str]],
    ) -> str:
        start_line = func_info["line_start"] - 1
        class_end = CodeTransformer._find_class_end(new_lines, start_line)

        for helper in extracted_helpers:
            helper_lines = helper["content"].split("\n")
            new_lines = [
                *new_lines[:class_end],
                "",
                *helper_lines,
                *new_lines[class_end:],
            ]
            class_end += len(helper_lines) + 1

        return "\n".join(new_lines)

    @staticmethod
    def _find_class_end(lines: list[str], func_start: int) -> int:
        class_indent = CodeTransformer._find_class_indent(lines, func_start)
        if class_indent is None:
            return len(lines)
        return CodeTransformer._find_class_end_line(lines, func_start, class_indent)

    @staticmethod
    def _find_class_indent(lines: list[str], func_start: int) -> int | None:
        for i in range(func_start, -1, -1):
            if lines[i].strip().startswith("class "):
                return len(lines[i]) - len(lines[i].lstrip())
        return None

    @staticmethod
    def _find_class_end_line(
        lines: list[str],
        func_start: int,
        class_indent: int,
    ) -> int:
        for i in range(func_start + 1, len(lines)):
            line = lines[i]
            if line.strip() and len(line) - len(line.lstrip()) <= class_indent:
                return i
        return len(lines)
