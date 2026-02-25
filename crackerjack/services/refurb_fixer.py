from __future__ import annotations

import ast
import logging
import re
import typing as t
from pathlib import Path

logger = logging.getLogger(__name__)


class SafeRefurbFixer:
    def __init__(self) -> None:
        self.fixes_applied = 0

    def fix_file(self, file_path: Path) -> int:
        if not file_path.exists() or not file_path.is_file():
            return 0

        if file_path.suffix != ".py":
            return 0

        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return 0

        new_content, fixes = self._apply_fixes(content)

        if new_content != content:
            try:
                file_path.write_text(new_content, encoding="utf-8")
                self.fixes_applied += fixes
                logger.info(f"Applied {fixes} safe refurb fixes to {file_path}")
                return fixes
            except OSError as e:
                logger.warning(f"Could not write {file_path}: {e}")
                return 0

        return 0

    def fix_package(self, package_dir: Path) -> int:
        if not package_dir.exists() or not package_dir.is_dir():
            logger.warning(f"Package directory not found: {package_dir}")
            return 0

        total_fixes = 0
        for py_file in package_dir.rglob("*.py"):
            if "__pycache__" in str(py_file) or any(
                part.startswith(".") for part in py_file.parts
            ):
                continue

            fixes = self.fix_file(py_file)
            total_fixes += fixes

        logger.info(f"Total safe refurb fixes applied: {total_fixes}")
        return total_fixes

    def _apply_fixes(self, content: str) -> tuple[str, int]:
        total_fixes = 0

        # FURB102: x.startswith(y) or x.startswith(z) -> x.startswith((y, z))
        content, fixes_102 = self._fix_furb102_regex(content)
        total_fixes += fixes_102

        # FURB107: try/except/pass -> with suppress() (only for single except with pass)
        content, fixes_107 = self._fix_furb107(content)
        total_fixes += fixes_107

        # FURB109: in (...) -> in (...)
        content, fixes_109 = self._fix_furb109(content)
        total_fixes += fixes_109

        # FURB113: x.append(a); x.append(b) -> x.extend((a, b))
        content, fixes_113 = self._fix_furb113(content)
        total_fixes += fixes_113

        # FURB118: lambda x: x[n] -> operator.itemgetter(n)
        content, fixes_118 = self._fix_furb118(content)
        total_fixes += fixes_118

        # FURB115: not x -> not x, x -> x
        content, fixes_115 = self._fix_furb115(content)
        total_fixes += fixes_115

        # FURB126: else: return x -> return x
        content, fixes_126 = self._fix_furb126(content)
        total_fixes += fixes_126

        # FURB110: x or y -> x or y
        content, fixes_110 = self._fix_furb110(content)
        total_fixes += fixes_110

        # FURB123: path_var -> path_var (only for path-like variable names)
        content, fixes_123 = self._fix_furb123(content)
        total_fixes += fixes_123

        # FURB142: for x in y: z.add(x) -> z.update(y)
        content, fixes_142 = self._fix_furb142(content)
        total_fixes += fixes_142

        # FURB148: for i, x in enumerate(y) -> for x in y (if i unused)
        content, fixes_148 = self._fix_furb148(content)
        total_fixes += fixes_148

        # FURB161: 1000000 -> 1000000
        content, fixes_161 = self._fix_furb161(content)
        total_fixes += fixes_161

        # FURB124: x == y == z -> x == y == z
        content, fixes_124 = self._fix_furb124(content)
        total_fixes += fixes_124

        # FURB138: for loop with append -> list comprehension
        content, fixes_138 = self._fix_furb138(content)
        total_fixes += fixes_138

        # FURB108: y in (x, z) -> y in (x, z)
        content, fixes_108 = self._fix_furb108(content)
        total_fixes += fixes_108

        return content, total_fixes

    def _fix_furb102_regex(self, content: str) -> tuple[str, int]:
        """FURB102: x.startswith(y) or x.startswith(z) -> x.startswith((y, z))."""
        total_fixes = 0
        new_content = content

        # Pattern: x.startswith(a) or x.startswith(b) -> x.startswith((a, b))
        # Only match at start of line (after indentation) to avoid docstrings
        pattern = r"^(\s*)(\w+)\.startswith\(([^)]+)\)\s+or\s+\2\.startswith\(([^)]+)\)"
        for match in re.finditer(pattern, new_content, re.MULTILINE):
            indent, var, arg1, arg2 = (
                match.group(1),
                match.group(2),
                match.group(3),
                match.group(4),
            )
            old_text = match.group(0)
            new_text = f"{indent}{var}.startswith(({arg1}, {arg2}))"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        # Pattern: not x.startswith(a) and not x.startswith(b)
        pattern = r"^(\s*)not\s+(\w+)\.startswith\(([^)]+)\)\s+and\s+not\s+\2\.startswith\(([^)]+)\)"
        for match in re.finditer(pattern, new_content, re.MULTILINE):
            indent, var, arg1, arg2 = (
                match.group(1),
                match.group(2),
                match.group(3),
                match.group(4),
            )
            old_text = match.group(0)
            new_text = f"{indent}not {var}.startswith(({arg1}, {arg2}))"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb107(self, content: str) -> tuple[str, int]:
        """FURB107: try/except/pass -> with suppress().

        Only converts try/except blocks that have:
        - Exactly ONE except handler
        - The handler body is ONLY 'pass'
        - No nested blocks in the try body
        """
        total_fixes = 0
        lines = content.split("\n")
        result_lines = lines.copy()
        i = 0

        while i < len(lines):
            line = lines[i]
            # Look for try: statements
            try_match = re.match(r"^(\s*)try:\s*$", line)
            if not try_match:
                i += 1
                continue

            indent = try_match.group(1)
            body_indent = indent + "    "

            # Scan for ALL except blocks in this try statement
            total_except_count = 0
            pass_only_except = None  # (except_line_idx, pass_line_idx, exception_type)
            j = i + 1

            while j < len(lines):
                curr_line = lines[j]

                # Check if we've exited the try block scope
                if curr_line.strip() and not curr_line.startswith(indent):
                    break

                # Check for any except line (including 'except X as e:' syntax)
                except_match = re.match(
                    rf"^{re.escape(indent)}except\s+(\w+(?:\s*,\s*\w+)*)(?:\s+as\s+\w+)?:",
                    curr_line,
                ) or re.match(rf"^{re.escape(indent)}except\s*:", curr_line)

                if except_match:
                    total_except_count += 1
                    exception_type = (
                        except_match.group(1) if except_match.lastindex else "Exception"
                    )

                    # Check if this except has only pass
                    # Case 1: inline pass (except X: pass)
                    inline_pass = re.match(
                        rf"^{re.escape(indent)}except\s+\w+(?:\s*,\s*\w+)*(?:\s+as\s+\w+)?:\s*pass\s*$",
                        curr_line,
                    ) or re.match(
                        rf"^{re.escape(indent)}except\s*:\s*pass\s*$", curr_line
                    )

                    if inline_pass:
                        if pass_only_except is None:
                            pass_only_except = (j, None, exception_type)
                    else:
                        # Case 2: pass on next line
                        if j + 1 < len(lines):
                            pass_match = re.match(
                                rf"^{re.escape(body_indent)}pass\s*$", lines[j + 1]
                            )
                            if pass_match:
                                if pass_only_except is None:
                                    pass_only_except = (j, j + 1, exception_type)
                                j += 1  # Skip the pass line in scanning
                            else:
                                # This except has actual code, not pass
                                pass_only_except = "INVALID"  # Mark as invalid
                        else:
                            pass_only_except = "INVALID"

                j += 1

            # Only convert if there's exactly ONE except block AND it's pass-only
            if (
                total_except_count != 1
                or pass_only_except is None
                or pass_only_except == "INVALID"
            ):
                i += 1
                continue

            except_line_idx, pass_line_idx, exception_type = pass_only_except

            # Check try body for nested blocks
            try_body = lines[i + 1 : except_line_idx]
            has_nested = any(
                re.match(rf"^{re.escape(body_indent)}\w+.*:\s*$", line)
                for line in try_body
                if line.strip()
            )
            if has_nested:
                i += 1
                continue

            # Perform the transformation
            result_lines[i] = f"{indent}with suppress({exception_type}):"
            # Remove the except line and optionally the pass line
            if pass_line_idx is not None:
                del result_lines[pass_line_idx]
                del result_lines[except_line_idx]
                i = pass_line_idx
            else:
                del result_lines[except_line_idx]
                i = except_line_idx
            total_fixes += 1

        return "\n".join(result_lines), total_fixes

    def _fix_furb109(self, content: str) -> tuple[str, int]:
        """FURB109: in (...) -> in (...)."""
        total_fixes = 0
        new_content = content

        # Handle for loops: for x in (...) -> for x in (...)
        # Only match single-line lists to avoid complex multiline cases
        for_pattern = r"^(\s*)for\s+(.+?)\s+in\s+\[([^\]\n]+)\]:"
        matches = list(re.finditer(for_pattern, new_content, re.MULTILINE))
        for match in reversed(matches):  # Reverse to preserve positions
            indent, var_name, list_contents = (
                match.group(1),
                match.group(2).strip(),
                match.group(3),
            )
            # Check if it's a simple list (no nested structures)
            if "[" not in list_contents and "{" not in list_contents:
                old_text = match.group(0)
                new_text = f"{indent}for {var_name} in ({list_contents}):"
                new_content = (
                    new_content[: match.start()] + new_text + new_content[match.end() :]
                )
                total_fixes += 1

        # Handle membership tests: in (...) -> in (...)
        # Only match single-line lists
        in_pattern = r"\bin\s+\[([^\]\n]+)\]"
        for match in re.finditer(in_pattern, new_content):
            list_contents = match.group(1)
            if "[" not in list_contents and "{" not in list_contents:
                old_text = match.group(0)
                new_text = f"in ({list_contents})"
                new_content = new_content.replace(old_text, new_text, 1)
                total_fixes += 1

        return new_content, total_fixes

    def _fix_furb113(self, content: str) -> tuple[str, int]:
        """FURB113: x.append(a); x.append(b) -> x.extend((a, b)).

        VERY CONSERVATIVE: Only converts simple append calls with:
        - Single argument (no commas to avoid keyword args)
        - No nested parentheses
        """
        total_fixes = 0
        new_content = content

        # Pattern: consecutive append calls on same variable
        # Only match single simple argument (no commas, no nested parens)
        # x.append(a)
        # x.append(b)
        # The argument must not contain commas (to avoid matching keyword args)
        pattern = r"(\w+)\.append\(([^(),\n]+)\)\n(\s+)\1\.append\(([^(),\n]+)\)"

        # Keep applying until no more matches
        while True:
            match = re.search(pattern, new_content)
            if not match:
                break

            var, arg1, indent, arg2 = (
                match.group(1),
                match.group(2).strip(),
                match.group(3),
                match.group(4).strip(),
            )
            old_text = match.group(0)
            new_text = f"{var}.extend(({arg1}, {arg2}))\n{indent}"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb118(self, content: str) -> tuple[str, int]:
        """FURB118: lambda x: x[n] -> operator.itemgetter(n).

        IMPORTANT: Only matches lambda patterns, NOT existing operator.itemgetter calls.
        Uses f-strings to build replacement, not regex backreferences.
        """
        total_fixes = 0
        new_content = content

        # Pattern: lambda x: x[n] where x is any variable name
        # For numeric index: operator.itemgetter(1) -> operator.itemgetter(1)
        numeric_pattern = r"lambda\s+(\w+)\s*:\s*\1\s*\[\s*(\d+)\s*\]"
        for match in re.finditer(numeric_pattern, new_content):
            old_text = match.group(0)
            index = match.group(2)  # The numeric index
            new_text = f"operator.itemgetter({index})"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        # For string key: operator.itemgetter("key") -> operator.itemgetter("key")
        string_pattern = r'lambda\s+(\w+)\s*:\s*\1\s*\[\s*["\']([^"\']+)["\']\s*\]'
        for match in re.finditer(string_pattern, new_content):
            old_text = match.group(0)
            key = match.group(2)  # The string key
            new_text = f'operator.itemgetter("{key}")'
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb115(self, content: str) -> tuple[str, int]:
        """FURB115: not x -> not x, x -> x, x -> x."""
        total_fixes = 0
        new_content = content

        patterns = [
            # not x -> not x
            (r"\blen\(([^()]+)\)\s*==\s*0\b", r"not \1"),
            # x -> bool(x) or just x (use x for truthiness)
            (r"\blen\(([^()]+)\)\s*>=\s*1\b", r"\1"),
            # x -> x
            (r"\blen\(([^()]+)\)\s*>\s*0\b", r"\1"),
        ]

        for pattern, replacement in patterns:
            for match in re.finditer(pattern, new_content):
                old_text = match.group(0)
                var = match.group(1).strip()
                # Build replacement using f-string
                if "not" in replacement:
                    new_text = f"not {var}"
                else:
                    new_text = var
                new_content = new_content.replace(old_text, new_text, 1)
                total_fixes += 1

        return new_content, total_fixes

    def _fix_furb126(self, content: str) -> tuple[str, int]:
        """FURB126: else: return x -> return x (in functions).

        This removes the else: and dedents the return statement.
        Only handles simple cases where else: is followed by return on next line.
        """
        total_fixes = 0
        lines = content.split("\n")
        result_lines = lines.copy()

        i = 0
        while i < len(lines) - 1:
            line = lines[i]
            next_line = lines[i + 1] if i + 1 < len(lines) else ""

            # Look for: else:
            #              return something
            else_match = re.match(r"^(\s*)else:\s*$", line)
            if not else_match:
                i += 1
                continue

            indent = else_match.group(1)
            body_indent = indent + "    "

            # Check if next line is a return statement
            return_match = re.match(rf"^{re.escape(body_indent)}return\b", next_line)
            if not return_match:
                i += 1
                continue

            # Check that this isn't followed by more code at the same level as else
            # (if there is, we shouldn't remove the else)
            has_more_code = False
            block_pattern = "^" + re.escape(indent) + r"}?\w"
            for j in range(i + 2, len(lines)):
                if lines[j].strip() == "":
                    continue
                if re.match(block_pattern, lines[j]):
                    has_more_code = True
                    break
                if not lines[j].startswith(indent):
                    break

            if has_more_code:
                i += 1
                continue

            # Remove the else: line and dedent the return
            result_lines[i] = ""
            result_lines[i + 1] = next_line.replace(body_indent, indent, 1)
            total_fixes += 1
            i += 2

        # Remove empty lines we created (but preserve trailing newline structure)
        new_content = "\n".join(line for line in result_lines)
        return new_content, total_fixes

    def _fix_furb110(self, content: str) -> tuple[str, int]:
        """FURB110: x or y -> x or y.

        Only handles simple variable cases: var or other
        """
        total_fixes = 0
        new_content = content

        # Pattern: x or y (simple variable case)
        pattern = r"\b(\w+)\s+if\s+\1\s+else\s+(\w+)\b"
        for match in re.finditer(pattern, new_content):
            var1, var2 = match.group(1), match.group(2)
            old_text = match.group(0)
            new_text = f"{var1} or {var2}"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb123(self, content: str) -> tuple[str, int]:
        """FURB123: Replace redundant copy operations.

        Handles:
        - list(x) -> x.copy() when x is clearly a list
        - set(x) -> x.copy() when x is clearly a set
        - dict(x) -> x.copy() when x is clearly a dict
        - str(p) -> p when p is clearly a Path

        VERY CONSERVATIVE: Only handles cases where the type is obvious.
        """
        total_fixes = 0
        new_content = content

        # path_var -> path_var (when var name suggests it's a Path object)
        str_pattern = r"\bstr\(([a-z_]*path[a-z_]*)\)"
        for match in re.finditer(str_pattern, new_content):
            var_name = match.group(1)
            old_text = match.group(0)
            new_content = new_content.replace(old_text, var_name, 1)
            total_fixes += 1

        # list(var) -> var.copy() when var is clearly a list
        list_pattern = r"\blist\(([a-z_]*lines[a-z_]*|[a-z_]*list[a-z_]*|results|items|nodes|args)\)"
        for match in re.finditer(list_pattern, new_content):
            var_name = match.group(1)
            old_text = match.group(0)
            new_text = f"{var_name}.copy()"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        # set(var) -> var.copy() when var is clearly a set
        set_pattern = r"\bset\(([a-z_]*set[a-z_]*|[a-z_]*_set)\)"
        for match in re.finditer(set_pattern, new_content):
            var_name = match.group(1)
            old_text = match.group(0)
            new_text = f"{var_name}.copy()"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        # dict(var) -> var.copy() when var is clearly a dict
        dict_pattern = (
            r"\bdict\(([a-z_]*dict[a-z_]*|[a-z_]*_dict|mapping|data|config)\)"
        )
        for match in re.finditer(dict_pattern, new_content):
            var_name = match.group(1)
            old_text = match.group(0)
            new_text = f"{var_name}.copy()"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb142(self, content: str) -> tuple[str, int]:
        """FURB142: for x in y: z.add(x) -> z.update(y).

        Only handles simple cases where the loop iterates directly over a variable.
        """
        total_fixes = 0
        new_content = content

        # Pattern: for x in y:\n    z.add(x)
        # Only match when iterating over a simple variable (not expression)
        pattern = r"for\s+(\w+)\s+in\s+(\w+):\s*\n(\s+)(\w+)\.add\(\1\)"
        for match in re.finditer(pattern, new_content):
            _var, iterable, _indent, set_var = (
                match.group(1),
                match.group(2),
                match.group(3),
                match.group(4),
            )
            old_text = match.group(0)
            new_text = f"{set_var}.update({iterable})"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb148(self, content: str) -> tuple[str, int]:
        """FURB148: for i, x in enumerate(y) -> for x in y (if i unused).

        Very conservative - only handles simple cases where enumerate is used
        but the index variable is clearly not used in the loop body.
        """
        total_fixes = 0
        lines = content.split("\n")
        result_lines = lines.copy()
        i = 0

        while i < len(lines):
            line = lines[i]
            # Look for: for i, var in enumerate(...):
            enum_match = re.match(
                r"^(\s*)for\s+(\w+)\s*,\s*(\w+)\s+in\s+enumerate\(([^)]+)\):\s*$", line
            )
            if not enum_match:
                i += 1
                continue

            indent, idx_var, val_var, iterable = enum_match.groups()

            # Check if idx_var is used in the loop body
            idx_used = False
            for j in range(i + 1, len(lines)):
                body_line = lines[j]
                # Stop at next block at same level
                if body_line.strip() and not body_line.startswith(indent + "    "):
                    if body_line.startswith(indent) and not body_line.startswith(
                        indent + " "
                    ):
                        break
                    break
                # Check for index variable usage (but not in comments)
                code_part = body_line.split("#")[0] if "#" in body_line else body_line
                if re.search(rf"\b{re.escape(idx_var)}\b", code_part):
                    idx_used = True
                    break

            if not idx_used:
                # Convert to simple for loop
                result_lines[i] = f"{indent}for {val_var} in {iterable}:"
                total_fixes += 1

            i += 1

        return "\n".join(result_lines), total_fixes

    def _fix_furb161(self, content: str) -> tuple[str, int]:
        """FURB161: 1000000 -> 1000000."""
        total_fixes = 0
        new_content = content

        # Pattern: int(1eN) where N is digits
        pattern = r"\bint\((\d+(?:\.\d+)?)e(\d+)\)"
        for match in re.finditer(pattern, new_content):
            base, exp = match.group(1), match.group(2)
            old_text = match.group(0)
            try:
                value = int(float(f"{base}e{exp}"))
                new_text = str(value)
                new_content = new_content.replace(old_text, new_text, 1)
                total_fixes += 1
            except (ValueError, OverflowError):
                continue

        return new_content, total_fixes

    def _fix_furb124(self, content: str) -> tuple[str, int]:
        """FURB124: x == y == z -> x == y == z.

        Handles two cases:
        1. x == y == z (common value on right side)
        2. x == y == z (common value is right of first, left of second)

        VERY CONSERVATIVE: Only handles simple variable comparisons.
        """
        total_fixes = 0
        new_content = content

        # Case 1: x == y == z (y on right of both)
        # Pattern: var1 == common == var2
        pattern1 = r"\b(\w+)\s*==\s*(\w+)\s+and\s+(\w+)\s*==\s*\2\b"
        for match in re.finditer(pattern1, new_content):
            var1, common, var2 = match.group(1), match.group(2), match.group(3)
            # Skip if variables are the same (x == y and x == y)
            if var1 == var2:
                continue
            old_text = match.group(0)
            new_text = f"{var1} == {common} == {var2}"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        # Case 2: x == y == z (y is right of first, left of second)
        # Pattern: var1 == common == var2
        pattern2 = r"\b(\w+)\s*==\s*(\w+)\s+and\s+\2\s*==\s*(\w+)\b"
        for match in re.finditer(pattern2, new_content):
            var1, common, var2 = match.group(1), match.group(2), match.group(3)
            # Skip if variables are the same
            if var1 == var2:
                continue
            old_text = match.group(0)
            new_text = f"{var1} == {common} == {var2}"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb138(self, content: str) -> tuple[str, int]:
        """FURB138: for loop with single append -> list comprehension.

        Transforms:
            result = []
            for x in items:
                result.append(f(x))
        Into:
            result = [f(x) for x in items]

        VERY CONSERVATIVE:
        - Only single-statement for loops
        - Only simple append with single argument
        - No nested structures in the for body
        """
        total_fixes = 0
        lines = content.split("\n")
        result_lines = lines.copy()
        i = 0

        while i < len(lines) - 2:
            line = lines[i]

            # Look for: var = []
            init_match = re.match(r"^(\s*)(\w+)\s*=\s*\[\]\s*$", line)
            if not init_match:
                i += 1
                continue

            indent, var_name = init_match.group(1), init_match.group(2)

            # Next line should be a for loop
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            for_match = re.match(
                rf"^{re.escape(indent)}for\s+(\w+)\s+in\s+(.+?):\s*$", next_line
            )
            if not for_match:
                i += 1
                continue

            loop_var, iterable = for_match.group(1), for_match.group(2).strip()

            # Line after for should be an append
            append_line = lines[i + 2] if i + 2 < len(lines) else ""
            body_indent = indent + "    "
            append_match = re.match(
                rf"^{re.escape(body_indent)}{re.escape(var_name)}\.append\(([^)]+)\)\s*$",
                append_line,
            )
            if not append_match:
                i += 1
                continue

            append_arg = append_match.group(1).strip()

            # Safety checks:
            # 1. The append argument should use the loop variable
            if not re.search(rf"\b{re.escape(loop_var)}\b", append_arg):
                i += 1
                continue

            # 2. No more lines in the for loop body (single statement)
            if i + 3 < len(lines):
                following = lines[i + 3]
                if following.startswith(body_indent) and following.strip():
                    i += 1
                    continue

            # Perform the transformation
            list_comp = (
                f"{indent}{var_name} = [{append_arg} for {loop_var} in {iterable}]"
            )
            result_lines[i] = list_comp
            result_lines[i + 1] = ""  # Remove for line
            result_lines[i + 2] = ""  # Remove append line
            total_fixes += 1
            i += 3

        # Remove empty lines
        new_content = "\n".join(line for line in result_lines)
        return new_content, total_fixes

    def _fix_furb108(self, content: str) -> tuple[str, int]:
        """FURB108: y in (x, z) -> y in (x, z).

        Handles equality comparisons where the same value is compared to multiple values.
        Pattern: common in (var1, var2) -> common in (var1, var2)
        """
        total_fixes = 0
        new_content = content

        # Pattern: y in (x, z) (common value on right side)
        pattern = r"\b(\w+)\s*==\s*(\w+)\s+or\s+(\w+)\s*==\s*\2\b"
        for match in re.finditer(pattern, new_content):
            var1, common, var2 = match.group(1), match.group(2), match.group(3)
            # Skip if variables are the same
            if var1 == var2:
                continue
            old_text = match.group(0)
            new_text = f"{common} in ({var1}, {var2})"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes


class _StartswithTupleTransformer(ast.NodeTransformer):
    def __init__(self) -> None:
        self.fixes = 0

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:

        if not isinstance(node.op, ast.Or):
            return self.generic_visit(node)

        startswith_groups = self._group_startswith_calls(node.values)

        for obj_key, calls in startswith_groups.items():
            result = self._try_transform_group(node, calls)
            if result is not None:
                return result

        return self.generic_visit(node)

    def _group_startswith_calls(
        self, values: list[ast.AST]
    ) -> dict[int, list[ast.Call]]:
        groups: dict[int, list[ast.Call]] = {}

        for value in values:
            if not self._is_startswith_call(value):
                continue

            call = t.cast(ast.Call, value)
            if not isinstance(call.func, ast.Attribute):
                continue

            obj_key = self._get_object_key(call.func.value)
            if obj_key is not None:
                groups.setdefault(obj_key, []).append(call)

        return groups

    def _try_transform_group(
        self, node: ast.BoolOp, calls: list[ast.Call]
    ) -> ast.AST | None:
        if len(calls) < 2:
            return None

        if not all(self._is_simple_string_arg(call) for call in calls):
            return None

        string_args = self._extract_string_args(calls)
        if len(string_args) < 2:
            return None

        new_call = self._create_combined_call(calls[0], string_args)

        return self._build_replacement(node, calls, new_call)

    def _extract_string_args(self, calls: list[ast.Call]) -> list[ast.Constant]:
        string_args: list[ast.Constant] = []
        for call in calls:
            arg = call.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                string_args.append(ast.Constant(value=arg.value))
        return string_args

    def _create_combined_call(
        self, template: ast.Call, string_args: list[ast.Constant]
    ) -> ast.Call:
        tuple_arg = ast.Tuple(elts=string_args, ctx=ast.Load())
        return ast.Call(
            func=template.func,
            args=[tuple_arg],
            keywords=template.keywords,
        )

    def _build_replacement(
        self, node: ast.BoolOp, calls: list[ast.Call], new_call: ast.Call
    ) -> ast.AST:
        new_values: list[ast.AST] = []
        replaced_ids = {id(c) for c in calls}

        for value in node.values:
            if id(value) not in replaced_ids:
                new_values.append(self.visit(value))

        new_values.append(new_call)
        self.fixes += 1

        if len(new_values) == 1:
            return new_values[0]
        return ast.BoolOp(op=ast.Or(), values=new_values)

    def _is_startswith_call(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False

        if not isinstance(node.func, ast.Attribute):
            return False

        if node.func.attr != "startswith":
            return False

        return len(node.args) == 1

    def _is_simple_string_arg(self, call: ast.Call) -> bool:
        if not call.args:
            return False

        arg = call.args[0]
        return isinstance(arg, ast.Constant) and isinstance(arg.value, str)

    def _get_object_key(self, node: ast.AST) -> int | None:
        try:
            return hash(ast.dump(node))
        except Exception:
            return None


class _MembershipTupleTransformer(ast.NodeTransformer):
    def __init__(self) -> None:
        self.fixes = 0

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        new_comparators: list[ast.AST] = []
        original_ids = [id(c) for c in node.comparators]

        for op, comparator in zip(node.ops, node.comparators):
            if self._should_convert_to_tuple(op, comparator):
                new_tuple = ast.Tuple(elts=comparator.elts, ctx=ast.Load())
                new_comparators.append(new_tuple)
                self.fixes += 1
            else:
                new_comparators.append(self.visit(comparator))

        new_ids = [id(c) for c in new_comparators]
        if new_ids != original_ids:
            return ast.Compare(
                left=self.visit(node.left),
                ops=node.ops,
                comparators=new_comparators,
            )

        return self.generic_visit(node)

    def _should_convert_to_tuple(self, op: ast.cmpop, comparator: ast.AST) -> bool:
        if not isinstance(op, (ast.In, ast.NotIn)):
            return False

        if not isinstance(comparator, ast.List):
            return False

        return self._is_safe_list(comparator)

    def _is_safe_list(self, node: ast.List) -> bool:
        return all(self._is_simple_element(elt) for elt in node.elts)

    def _is_simple_element(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return True

        if isinstance(node, ast.Name):
            return True

        if isinstance(node, ast.Attribute):
            return self._is_simple_element(node.value)

        return False


class _ForLoopTupleTransformer(ast.NodeTransformer):
    """Transform for x in (...) to for x in (...)."""

    def __init__(self) -> None:
        self.fixes = 0

    def visit_For(self, node: ast.For) -> ast.AST:
        # Check if iter is a list literal
        if isinstance(node.iter, ast.List):
            if self._is_safe_list(node.iter):
                # Convert list to tuple
                node.iter = ast.Tuple(elts=node.iter.elts, ctx=ast.Load())
                self.fixes += 1
        return self.generic_visit(node)

    def _is_safe_list(self, node: ast.List) -> bool:
        return all(self._is_simple_element(elt) for elt in node.elts)

    def _is_simple_element(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.Name):
            return True
        if isinstance(node, ast.Attribute):
            return self._is_simple_element(node.value)
        return False


def fix_file(file_path: Path) -> int:
    fixer = SafeRefurbFixer()
    return fixer.fix_file(file_path)


def fix_package(package_dir: Path) -> int:
    fixer = SafeRefurbFixer()
    return fixer.fix_package(package_dir)
