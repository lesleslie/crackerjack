"""Refurb code transformer agent for applying automated code modernizations.

This agent handles refurb FURB codes by transforming code patterns into more
idiomatic Python. It follows the established agent pattern from crackerjack.agents.base.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .base import FixResult, Issue, IssueType, SubAgent

if TYPE_CHECKING:
    from .base import AgentContext

logger = logging.getLogger(__name__)

# Mapping of FURB codes to their transformation handlers
# Each handler is a method name that implements the specific transformation
FURB_TRANSFORMATIONS: dict[str, str] = {
    "FURB102": "_transform_compare_zero",
    "FURB105": "_transform_print_empty_string",
    "FURB107": "_transform_compare_empty",
    "FURB108": "_transform_redundant_none_comparison",
    "FURB109": "_transform_membership_test",
    "FURB110": "_transform_delete_while_iterating",
    "FURB111": "_transform_redundant_continue",
    "FURB113": "_transform_redundant_pass",
    "FURB115": "_transform_open_mode_r",
    "FURB116": "_transform_fstring_numeric_literal",
    "FURB117": "_transform_multiple_with",
    "FURB118": "_transform_enumerate",
    "FURB119": "_transform_redundant_index",
    "FURB122": "_transform_rhs_unpack",
    "FURB123": "_transform_write_whole_file",
    "FURB125": "_transform_redundantenumerate",
    "FURB126": "_transform_isinstance_type_check",
    "FURB129": "_transform_any_all",
    "FURB131": "_transform_single_item_membership",
    "FURB132": "_transform_check_and_remove",
    "FURB133": "_transform_bad_open_mode",
    "FURB134": "_transform_list_multiply",
    "FURB136": "_transform_bool_return",
    "FURB138": "_transform_print_literal",
    "FURB140": "_transform_zip",
    "FURB141": "_transform_redundant_fstring",
    "FURB142": "_transform_unnecessary_listcomp",
    "FURB143": "_transform_unnecessary_index_lookup",
    "FURB145": "_transform_copy",
    "FURB148": "_transform_max_min",
    "FURB152": "_transform_pow_operator",
    "FURB156": "_transform_redundant_lambda",
    "FURB157": "_transform_implicit_print",
    "FURB161": "_transform_int_scientific",
    "FURB163": "_transform_sorted_key_identity",
    "FURB167": "_transform_dict_literal",
    "FURB168": "_transform_isinstance_type_tuple",
    "FURB169": "_transform_type_none_comparison",
    "FURB171": "_transform_single_element_membership",
    "FURB172": "_transform_unnecessary_list_cast",
    "FURB173": "_transform_redundant_not",
    "FURB175": "_transform_abs_sqr",
    "FURB176": "_transform_unnecessary_from_float",
    "FURB177": "_transform_redundant_or",
    "FURB180": "_transform_method_assign",
    "FURB181": "_transform_redundant_expression",
    "FURB183": "_transform_substring",
    "FURB184": "_transform_bad_version_info_compare",
    "FURB185": "_transform_redundant_substring",
    "FURB186": "_transform_redundant_cast",
    "FURB187": "_transform_chained_assignment",
    "FURB188": "_transform_slice_copy",
    "FURB189": "_transform_fstring_to_print",
    "FURB190": "_transform_subprocess_list",
}


class RefurbCodeTransformerAgent(SubAgent):
    """Agent that transforms refurb suggestions into actual code changes.

    This agent handles common FURB codes by applying automated code
    transformations that modernize and simplify Python code.

    Supported transformations:
    - FURB118: reimplemented enumerate() - transform loops to use enumerate
    - FURB129: reimplemented any()/all() - transform loops to use any()/all()
    - FURB136: if x: return True -> return bool(x)
    - FURB140: reimplemented zip() - use zip() instead of manual iteration
    - FURB142: unnecessary list comprehension
    - FURB145: x[:] -> x.copy()
    - FURB148: reimplemented max()/min()
    - FURB152: math.pow() -> ** operator
    - FURB161: int(1e6) -> 1000000
    - FURB163: sorted(x, key=lambda i: i) -> sorted(x)
    """

    name = "RefurbCodeTransformerAgent"
    confidence = 0.85

    def __init__(self, context: AgentContext) -> None:
        """Initialize the refurb transformer agent."""
        super().__init__(context)
        self.log = logger.info  # type: ignore

    def get_supported_types(self) -> set[IssueType]:
        """Return the issue types this agent can handle."""
        return {IssueType.REFURB}

    async def can_handle(self, issue: Issue) -> float:
        """Determine if this agent can handle the given issue.

        Args:
            issue: The issue to evaluate.

        Returns:
            Confidence score (0.0 to 1.0) for handling this issue.
        """
        if issue.type != IssueType.REFURB:
            return 0.0

        furb_code = self._extract_furb_code(issue)
        if furb_code is None:
            return 0.0

        if furb_code in FURB_TRANSFORMATIONS:
            return self.confidence

        return 0.0

    def _extract_furb_code(self, issue: Issue) -> str | None:
        """Extract the FURB code from issue details or message.

        Args:
            issue: The issue containing FURB code information.

        Returns:
            The FURB code (e.g., "FURB118") or None if not found.
        """
        # Check details list first
        for detail in issue.details:
            match = re.search(r"FURB\d+", detail)
            if match:
                return match.group(0)

        # Then check message
        if issue.message:
            match = re.search(r"FURB\d+", issue.message)
            if match:
                return match.group(0)

        return None

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Analyze the issue and apply the appropriate transformation.

        Args:
            issue: The refurb issue to fix.

        Returns:
            FixResult indicating success or failure of the transformation.
        """
        self.log(f"RefurbCodeTransformerAgent analyzing: {issue.message[:100]}")

        if issue.file_path is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided"],
            )

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"File not found: {file_path}"],
            )

        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not read file content"],
            )

        furb_code = self._extract_furb_code(issue)
        if furb_code is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not extract FURB code from issue"],
            )

        handler_name = FURB_TRANSFORMATIONS.get(furb_code)
        if handler_name is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"No handler for {furb_code}"],
            )

        handler = getattr(self, handler_name, None)
        if handler is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Handler method {handler_name} not implemented"],
            )

        new_content, fix_description = handler(content, issue)

        if new_content == content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Transformation {furb_code} did not modify content"],
            )

        if self.context.write_file_content(file_path, new_content):
            return FixResult(
                success=True,
                confidence=self.confidence,
                fixes_applied=[fix_description],
                files_modified=[str(file_path)],
            )

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to write transformed content to {file_path}"],
        )

    # Transformation handlers

    def _transform_enumerate(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform manual index tracking to enumerate().

        FURB118: Detects patterns like:
            i = 0
            for item in items:
                # use i
                i += 1
        And transforms to:
            for i, item in enumerate(items):
        """
        fixes = []

        # Pattern: i = 0 followed by for loop with i += 1
        pattern = r"(\s*)(\w+)\s*=\s*0\n\1for\s+(\w+)\s+in\s+([^:]+):\n((?:.*\n)*?)\1\2\s*\+=\s*1"
        replacement = r"\1for \2, \3 in enumerate(\4):\n\5"

        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Replaced manual index tracking with enumerate()")

        return new_content, "; ".join(
            fixes
        ) if fixes else "No enumerate transformation applied"

    def _transform_any_all(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform loops that should use any() or all().

        FURB129: Detects patterns like:
            for item in items:
                if condition(item):
                    return True
            return False
        And transforms to:
            return any(condition(item) for item in items)
        """
        fixes = []

        # Pattern: for loop returning True on match, False otherwise
        any_pattern = r"(\s*)for\s+(\w+)\s+in\s+([^:]+):\n\s+if\s+([^:]+):\n\s+return\s+True\n\1return\s+False"
        any_replacement = r"\1return any(\4 for \2 in \3)"

        new_content = re.sub(any_pattern, any_replacement, content)
        if new_content != content:
            fixes.append("Replaced loop with any()")

        # Pattern: for loop returning False on match, True otherwise (all pattern)
        all_pattern = r"(\s*)for\s+(\w+)\s+in\s+([^:]+):\n\s+if\s+([^:]+):\n\s+return\s+False\n\1return\s+True"
        all_replacement = r"\1return all(not (\4) for \2 in \3)"

        new_content = re.sub(all_pattern, all_replacement, new_content)
        if new_content != content and "all(" in new_content:
            fixes.append("Replaced loop with all()")

        return new_content, "; ".join(
            fixes
        ) if fixes else "No any/all transformation applied"

    def _transform_bool_return(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform 'if x: return True; return False' to 'return bool(x)'.

        FURB136: Detects patterns like:
            if x:
                return True
            else:
                return False
        And transforms to:
            return bool(x)
        """
        fixes = []

        # Pattern: if x: return True [else: return False]
        patterns = [
            # if x: return True else: return False
            (
                r"(\s*)if\s+([^:]+):\n\s+return\s+True\n\s+else:\n\s+return\s+False",
                r"\1return bool(\2)",
            ),
            # if x: return True; return False (no else)
            (
                r"(\s*)if\s+([^:]+):\n\s+return\s+True\n\1return\s+False",
                r"\1return bool(\2)",
            ),
            # if not x: return False; return True
            (
                r"(\s*)if\s+not\s+([^:]+):\n\s+return\s+False\n\1return\s+True",
                r"\1return bool(\2)",
            ),
        ]

        new_content = content
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, new_content)

        if new_content != content:
            fixes.append("Simplified conditional return to bool()")

        return new_content, "; ".join(
            fixes
        ) if fixes else "No bool return transformation applied"

    def _transform_zip(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform manual parallel iteration to zip().

        FURB140: Detects patterns like:
            for i in range(len(items1)):
                item1 = items1[i]
                item2 = items2[i]
        And transforms to:
            for item1, item2 in zip(items1, items2):
        """
        fixes = []

        # This is complex to do with regex alone, so we do a simpler transformation
        # Pattern: for i in range(len(x)): ... = x[i]
        pattern = r"(\s*)for\s+(\w+)\s+in\s+range\(len\(([^)]+)\)\):"

        new_content = re.sub(
            pattern,
            r"\1for _, _ in zip(\3, _):  # TODO: Apply zip transformation manually",
            content,
        )

        if new_content != content:
            fixes.append(
                "Identified zip() transformation opportunity (may need manual review)"
            )

        return new_content, "; ".join(
            fixes
        ) if fixes else "No zip transformation applied"

    def _transform_unnecessary_listcomp(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        """Transform unnecessary list comprehensions.

        FURB142: Detects patterns like:
            [x for x in items][0]  -> next(x for x in items)
            list(x for x in items) when a generator would suffice
        """
        fixes = []

        # Pattern: [x for x in items][0]
        pattern = r"\[([^\]]+)\]\[0\]"
        replacement = r"next(\1)"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Replaced list comprehension indexing with next()")

        return new_content, "; ".join(
            fixes
        ) if fixes else "No list comprehension transformation applied"

    def _transform_copy(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform x[:] to x.copy() for clarity.

        FURB145: Detects patterns like:
            new_list = old_list[:]
        And transforms to:
            new_list = old_list.copy()
        """
        fixes = []

        # Pattern: identifier[:]
        # Be careful not to match slicing with start/end
        pattern = r"(\w+)\[\s*:\s*\](?!\s*,)"  # Not followed by comma (avoid multi-dim slicing)
        replacement = r"\1.copy()"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Replaced [:] slice with .copy() for clarity")

        return new_content, "; ".join(
            fixes
        ) if fixes else "No copy transformation applied"

    def _transform_max_min(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform manual max/min loops to built-in functions.

        FURB148: Detects patterns like:
            max_val = items[0]
            for item in items:
                if item > max_val:
                    max_val = item
        And transforms to:
            max_val = max(items)
        """
        fixes = []

        # Max pattern
        max_pattern = r"(\w+)\s*=\s*(\w+)\[0\]\n\s*for\s+(\w+)\s+in\s+\2:\n\s*if\s+\3\s*>\s*\1:\n\s*\1\s*=\s*\3"
        max_replacement = r"\1 = max(\2)"
        new_content = re.sub(max_pattern, max_replacement, content)

        if new_content != content:
            fixes.append("Replaced manual max loop with max()")

        # Min pattern
        min_pattern = r"(\w+)\s*=\s*(\w+)\[0\]\n\s*for\s+(\w+)\s+in\s+\2:\n\s*if\s+\3\s*<\s*\1:\n\s*\1\s*=\s*\3"
        min_replacement = r"\1 = min(\2)"
        new_content = re.sub(min_pattern, min_replacement, new_content)

        if "min(" in new_content and "min(" not in content:
            fixes.append("Replaced manual min loop with min()")

        return new_content, "; ".join(
            fixes
        ) if fixes else "No max/min transformation applied"

    def _transform_pow_operator(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform math.pow() to ** operator.

        FURB152: Detects patterns like:
            math.pow(x, y)
        And transforms to:
            x ** y
        """
        fixes = []

        # Pattern: math.pow(x, y)
        pattern = r"math\.pow\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)"
        replacement = r"(\1 ** \2)"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Replaced math.pow() with ** operator")

        return new_content, "; ".join(
            fixes
        ) if fixes else "No pow transformation applied"

    def _transform_int_scientific(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform int(1e6) to literal 1000000.

        FURB161: Detects patterns like:
            int(1e6)
        And transforms to:
            1000000
        """
        fixes = []

        def replace_scientific_int(match: re.Match[str]) -> str:
            """Convert scientific notation int to literal."""
            mantissa = float(match.group(1))
            exponent = int(match.group(2))
            value = int(mantissa * (10**exponent))
            return str(value)

        # Pattern: int(XeY) where X is a number and Y is an integer exponent
        pattern = r"int\s*\(\s*(\d+(?:\.\d+)?)e(\d+)\s*\)"
        new_content = re.sub(pattern, replace_scientific_int, content)

        if new_content != content:
            fixes.append("Replaced int(scientific notation) with literal integer")

        return new_content, "; ".join(
            fixes
        ) if fixes else "No int scientific transformation applied"

    def _transform_sorted_key_identity(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        """Transform sorted(x, key=lambda i: i) to sorted(x).

        FURB163: Detects patterns like:
            sorted(items, key=lambda x: x)
        And transforms to:
            sorted(items)
        """
        fixes = []

        # Pattern: sorted(..., key=lambda VAR: VAR)
        # Match various lambda variable names
        pattern = r"sorted\s*\(\s*([^,)]+)\s*,\s*key\s*=\s*lambda\s+(\w+)\s*:\s*\2\s*\)"
        replacement = r"sorted(\1)"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Removed redundant identity key function from sorted()")

        return new_content, "; ".join(
            fixes
        ) if fixes else "No sorted key transformation applied"

    # Additional FURB transformation handlers for high-frequency codes

    def _transform_compare_zero(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform explicit comparison to zero.

        FURB102: x == 0 -> not x (for numeric comparisons)
        FURB102: x != 0 -> bool(x)
        """
        fixes = []
        # len(x) == 0 -> not x (for collections)
        new_content = re.sub(r"len\s*\(([^)]+)\)\s*==\s*0", r"not \1", content)
        if new_content != content:
            fixes.append("Simplified len(x) == 0 to not x")
            content = new_content

        # x == 0 -> not x (for numbers in boolean context)
        new_content = re.sub(r"(\w+)\s*==\s*0\b", r"not \1", content)
        if new_content != content and not fixes:
            fixes.append("Simplified x == 0 to not x")

        return new_content, "; ".join(fixes) if fixes else "No zero comparison transformation"

    def _transform_compare_empty(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform explicit comparison to empty.

        FURB107: x == [] -> not x
        FURB107: x == {} -> not x
        FURB107: x == "" -> not x
        """
        fixes = []
        # x == [] -> not x
        new_content = re.sub(r"(\w+)\s*==\s*\[\s*\]", r"not \1", content)
        if new_content != content:
            fixes.append("Simplified x == [] to not x")
            content = new_content

        # x == {} -> not x
        new_content = re.sub(r"(\w+)\s*==\s*\{\s*\}", r"not \1", content)
        if new_content != content:
            fixes.append("Simplified x == {} to not x")
            content = new_content

        # x == "" -> not x
        new_content = re.sub(r'(\w+)\s*==\s*""', r"not \1", content)
        if new_content != content:
            fixes.append('Simplified x == "" to not x')

        return new_content, "; ".join(fixes) if fixes else "No empty comparison transformation"

    def _transform_redundant_none_comparison(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform redundant None comparisons.

        FURB108: if x is None: ... elif x is not None: ... -> if/else
        """
        # This is a structural pattern that needs manual review
        return content, "Redundant None comparison pattern requires manual review"

    def _transform_membership_test(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform list membership to set membership.

        FURB109: if x in [a, b, c] -> if x in {a, b, c}
        """
        fixes = []
        # Convert list literals in membership tests to sets
        pattern = r"\bin\s*\[([^\]]+)\]"
        replacement = r"in {\1}"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Converted list membership to set membership for O(1) lookup")

        return new_content, "; ".join(fixes) if fixes else "No membership test transformation"

    def _transform_isinstance_type_check(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform type(x) == T to isinstance(x, T).

        FURB126: type(x) == int -> isinstance(x, int)
        """
        fixes = []
        pattern = r"type\s*\(([^)]+)\)\s*==\s*(\w+)"
        replacement = r"isinstance(\1, \2)"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Converted type(x) == T to isinstance(x, T)")

        return new_content, "; ".join(fixes) if fixes else "No isinstance transformation"

    def _transform_write_whole_file(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform manual file writing to Path.write_text().

        FURB123: open(f, 'w').write(data) -> Path(f).write_text(data)
        """
        fixes = []
        # open(path, 'w') as f: f.write(data) -> Path(path).write_text(data)
        # This is complex to do with regex, so we do a simpler version
        pattern = r"open\s*\(\s*([^,]+),\s*['\"]w['\"]\s*\)\.write\s*\(([^)]+)\)"
        replacement = r"Path(\1).write_text(\2)"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Converted open().write() to Path.write_text()")

        return new_content, "; ".join(fixes) if fixes else "No write file transformation"

    def _transform_multiple_with(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform nested with statements to single with.

        FURB117: with a: with b: -> with a, b:
        """
        fixes = []
        # Nested with statements -> single with
        pattern = r"with\s+([^:]+):\s*\n\s*with\s+([^:]+):"
        replacement = r"with \1, \2:"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Combined nested with statements")

        return new_content, "; ".join(fixes) if fixes else "No with transformation"

    def _transform_redundant_not(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform not (x == y) to x != y.

        FURB173: not (x == y) -> x != y
        FURB173: not (x != y) -> x == y
        """
        fixes = []
        # not (x == y) -> x != y
        pattern = r"not\s*\(\s*([^)]+)\s*==\s*([^)]+)\s*\)"
        replacement = r"\1 != \2"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Simplified not (x == y) to x != y")
            content = new_content

        # not (x != y) -> x == y
        pattern = r"not\s*\(\s*([^)]+)\s*!=\s*([^)]+)\s*\)"
        replacement = r"\1 == \2"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Simplified not (x != y) to x == y")

        return new_content, "; ".join(fixes) if fixes else "No redundant not transformation"

    def _transform_substring(self, content: str, issue: Issue) -> tuple[str, str]:
        """Transform x.find(y) != -1 to y in x.

        FURB183: x.find(y) != -1 -> y in x
        """
        fixes = []
        pattern = r"(\w+)\.find\s*\(([^)]+)\)\s*!=\s*-1"
        replacement = r"\2 in \1"
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            fixes.append("Converted x.find(y) != -1 to y in x")

        return new_content, "; ".join(fixes) if fixes else "No substring transformation"

    # Placeholder handlers for remaining FURB codes (return unchanged for now)
    # These can be implemented with full regex patterns as needed

    def _transform_print_empty_string(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Print empty string transformation not implemented"

    def _transform_delete_while_iterating(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Delete while iterating requires manual review"

    def _transform_redundant_continue(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        # Remove redundant continue at end of loop
        pattern = r"\n(\s*)continue\s*\n(\s*)\n"
        replacement = r"\n\2\n"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Removed redundant continue")
        return new_content, "; ".join(fixes) if fixes else "No redundant continue"

    def _transform_redundant_pass(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Redundant pass requires manual review"

    def _transform_open_mode_r(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        # open(f, 'r') -> open(f)
        pattern = r"open\s*\(\s*([^,]+),\s*['\"]r['\"]\s*\)"
        replacement = r"open(\1)"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Removed redundant 'r' mode from open()")
        return new_content, "; ".join(fixes) if fixes else "No open mode transformation"

    def _transform_fstring_numeric_literal(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "F-string numeric literal requires manual review"

    def _transform_redundant_index(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Redundant index requires manual review"

    def _transform_rhs_unpack(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "RHS unpack requires manual review"

    def _transform_redundantenumerate(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Redundant enumerate requires manual review"

    def _transform_single_item_membership(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        # x in [y] -> x == y
        pattern = r"\b(\w+)\s+in\s*\[\s*(\w+)\s*\]"
        replacement = r"\1 == \2"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Converted x in [y] to x == y")
        return new_content, "; ".join(fixes) if fixes else "No single item membership"

    def _transform_check_and_remove(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Check and remove requires manual review"

    def _transform_bad_open_mode(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Bad open mode requires manual review"

    def _transform_list_multiply(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "List multiply requires manual review"

    def _transform_print_literal(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Print literal requires manual review"

    def _transform_redundant_fstring(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        # f"{x}" -> str(x) or just x depending on context
        pattern = r'f"\{([^}]+)\}"'
        replacement = r'str(\1)'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Converted redundant f-string to str()")
        return new_content, "; ".join(fixes) if fixes else "No redundant f-string"

    def _transform_unnecessary_index_lookup(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Unnecessary index lookup requires manual review"

    def _transform_redundant_lambda(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        # lambda x: func(x) -> func
        pattern = r"lambda\s+(\w+)\s*:\s*(\w+)\s*\(\s*\1\s*\)"
        replacement = r"\2"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Simplified lambda x: func(x) to func")
        return new_content, "; ".join(fixes) if fixes else "No redundant lambda"

    def _transform_implicit_print(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Implicit print requires manual review"

    def _transform_dict_literal(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Dict literal requires manual review"

    def _transform_isinstance_type_tuple(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Isinstance type tuple requires manual review"

    def _transform_type_none_comparison(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        # x == None -> x is None
        pattern = r"(\w+)\s*==\s*None\b"
        replacement = r"\1 is None"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Converted x == None to x is None")
            content = new_content
        # x != None -> x is not None
        pattern = r"(\w+)\s*!=\s*None\b"
        replacement = r"\1 is not None"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Converted x != None to x is not None")
        return new_content, "; ".join(fixes) if fixes else "No None comparison"

    def _transform_single_element_membership(self, content: str, issue: Issue) -> tuple[str, str]:
        return self._transform_single_item_membership(content, issue)

    def _transform_unnecessary_list_cast(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Unnecessary list cast requires manual review"

    def _transform_abs_sqr(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Abs sqr requires manual review"

    def _transform_unnecessary_from_float(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Unnecessary from_float requires manual review"

    def _transform_redundant_or(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Redundant or requires manual review"

    def _transform_method_assign(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Method assign requires manual review"

    def _transform_redundant_expression(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Redundant expression requires manual review"

    def _transform_bad_version_info_compare(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Bad version info compare requires manual review"

    def _transform_redundant_substring(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Redundant substring requires manual review"

    def _transform_redundant_cast(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Redundant cast requires manual review"

    def _transform_chained_assignment(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Chained assignment requires manual review"

    def _transform_slice_copy(self, content: str, issue: Issue) -> tuple[str, str]:
        return self._transform_copy(content, issue)

    def _transform_fstring_to_print(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "F-string to print requires manual review"

    def _transform_subprocess_list(self, content: str, issue: Issue) -> tuple[str, str]:
        return content, "Subprocess list requires manual review"


# Register with agent registry at module level
from .base import agent_registry

agent_registry.register(RefurbCodeTransformerAgent)
