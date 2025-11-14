"""Code pattern descriptions."""

import re

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "list_append_inefficiency_pattern": ValidatedPattern(
        name="list_append_inefficiency_pattern",
        pattern=r"(\s*)(\w+)\s*\+=\s*\[([^]]+)\]",
        replacement=r"\1\2.append(\3)",
        test_cases=[
            (" items += [new_item]", " items.append(new_item)"),
            ("results += [result]", "results.append(result)"),
            (" data += [value, other]", " data.append(value, other)"),
        ],
        description="Replace inefficient list[t.Any] concatenation with append for"
        " performance",
    ),
    "string_concatenation_pattern": ValidatedPattern(
        name="string_concatenation_pattern",
        pattern=r"(\s*)(\w+)\s*\+=\s*(.+)",
        replacement=r"\1\2_parts.append(\3)",
        test_cases=[
            (" text += new_text", " text_parts.append(new_text)"),
            ("result += line", "result_parts.append(line)"),
            (" output += data", " output_parts.append(data)"),
        ],
        description="Replace string concatenation with list[t.Any] append for performance "
        "optimization",
    ),
    "nested_loop_detection_pattern": ValidatedPattern(
        name="nested_loop_detection_pattern",
        pattern=r"(\s*)(for\s+\w+\s+in\s+.*: )",
        replacement=r"\1# Performance: Potential nested loop - check complexity\n\1\2",
        test_cases=[
            (
                " for j in other: ",
                " # Performance: Potential nested loop - check complexity\n "
                "for j in other: ",
            ),
            (
                "for i in items: ",
                "# Performance: Potential nested loop - check complexity\nfor i"
                " in items: ",
            ),
        ],
        description="Detect loop patterns that might be nested creating O(n²)"
        " complexity",
        flags=re.MULTILINE,
    ),
    "list_extend_optimization_pattern": ValidatedPattern(
        name="list_extend_optimization_pattern",
        pattern=r"(\s*)(\w+)\s*\+=\s*\[([^]]+(?: , \s*[^]]+)*)\]",
        replacement=r"\1\2.extend([\3])",
        test_cases=[
            (" items += [a, b, c]", " items.extend([a, b, c])"),
            ("results += [x, y]", "results.extend([x, y])"),
            (" data += [single_item]", " data.extend([single_item])"),
        ],
        description="Replace list[t.Any] concatenation with extend for better performance with multiple items",
    ),
    "inefficient_string_join_pattern": ValidatedPattern(
        name="inefficient_string_join_pattern",
        pattern=r"(\s*)(\w+)\s*=\s*([\"'])([\"'])\s*\.\s*join\(\s*\[\s*\]\s*\)",
        replacement=r"\1\2 = \3\4 # Performance: Use empty string directly instead"
        r" of join",
        test_cases=[
            (
                ' text = "".join([])',
                ' text = "" # Performance: Use empty string directly instead of join',
            ),
            (
                "result = ''.join([])",
                "result = '' # Performance: Use empty string directly instead of join",
            ),
        ],
        description="Replace inefficient empty list[t.Any] join with direct empty string"
        " assignment",
    ),
    "repeated_len_in_loop_pattern": ValidatedPattern(
        name="repeated_len_in_loop_pattern",
        pattern=r"(\s*)(len\(\s*(\w+)\s*\))",
        replacement=r"\1# Performance: Consider caching len(\3) if used "
        r"repeatedly\n\1\2",
        test_cases=[
            (
                " len(items)",
                " # Performance: Consider caching len(items) if used repeatedly\n"
                " len(items)",
            ),
            (
                "len(data)",
                "# Performance: Consider caching len(data) if used "
                "repeatedly\nlen(data)",
            ),
        ],
        description="Suggest caching len() calls that might be repeated",
    ),
    "list_comprehension_optimization_pattern": ValidatedPattern(
        name="list_comprehension_optimization_pattern",
        pattern=r"(\s*)(\w+)\.append\(([^)]+)\)",
        replacement=r"\1# Performance: Consider list[t.Any] comprehension if this is in a "
        r"simple loop\n\1\2.append(\3)",
        test_cases=[
            (
                " results.append(item * 2)",
                " # Performance: Consider list[t.Any] comprehension if this is in a "
                "simple loop\n results.append(item * 2)",
            ),
            (
                "data.append(value)",
                "# Performance: Consider list[t.Any] comprehension if this is in a simple"
                " loop\ndata.append(value)",
            ),
        ],
        description="Suggest list[t.Any] comprehensions for simple append patterns",
    ),
}
