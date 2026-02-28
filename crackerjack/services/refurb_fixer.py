from __future__ import annotations

import ast
import json
import logging
import re
import shutil
import subprocess
import typing as t
from pathlib import Path

logger = logging.getLogger(__name__)


AST_GREP_RULES = {
    "furb102-startswith-tuple": {
        "id": "furb102-startswith-tuple",
        "language": "python",
        "rule": {"pattern": "not $X.startswith($A) and not $X.startswith($B)"},
        "fix": "not $X.startswith(($A, $B))",
    },
    "furb102-startswith-tuple-or": {
        "id": "furb102-startswith-tuple-or",
        "language": "python",
        "rule": {"pattern": "$X.startswith($A) or $X.startswith($B)"},
        "fix": "$X.startswith(($A, $B))",
    },
}


class SafeRefurbFixer:
    def __init__(self) -> None:
        self.fixes_applied = 0
        self._ast_grep_available: bool | None = None

    def _check_ast_grep(self) -> bool:
        if self._ast_grep_available is not None:
            return self._ast_grep_available

        self._ast_grep_available = shutil.which("ast-grep") is not None
        if not self._ast_grep_available:
            logger.debug("ast-grep not available, using regex-only mode")
        return self._ast_grep_available

    def _run_ast_grep_fix(self, content: str, rule: dict) -> tuple[str, int]:
        if not self._check_ast_grep():
            return content, 0

        rule_json = json.dumps(rule)
        try:
            result = subprocess.run(
                ["ast-grep", "scan", "--inline-rules", rule_json, "--stdin", "--json"],
                input=content,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0 or not result.stdout.strip():
                return content, 0

            matches = json.loads(result.stdout)
            if not matches:
                return content, 0

            matches.sort(
                key=lambda m: m.get("range", {}).get("byteOffset", {}).get("start", 0),
                reverse=True,
            )

            new_content = content
            fixes = 0
            for match in matches:
                range_info = match.get("range", {})
                byte_offset = range_info.get("byteOffset", {})
                start = byte_offset.get("start", 0)
                end = byte_offset.get("end", 0)

                if start == 0 == end:
                    continue

                matched_text = match.get("text", "")
                if not matched_text:
                    continue

                fix_pattern = rule.get("fix", "")
                if not fix_pattern:
                    continue

                meta_vars = match.get("metaVariables", {}).get("single", {})

                replacement = fix_pattern
                for var_name, var_info in meta_vars.items():
                    var_text = var_info.get("text", "")

                    replacement = replacement.replace(f"${var_name}", var_text)

                new_content = new_content[:start] + replacement + new_content[end:]
                fixes += 1

            return new_content, fixes

        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            logger.debug(f"ast-grep execution failed: {e}")
            return content, 0

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

        content, fixes_102_ast = self._fix_furb102_ast_grep(content)
        total_fixes += fixes_102_ast

        content, fixes_102 = self._fix_furb102_regex(content)
        total_fixes += fixes_102

        content, fixes_107 = self._fix_furb107(content)
        total_fixes += fixes_107

        content, fixes_109 = self._fix_furb109(content)
        total_fixes += fixes_109

        content, fixes_113 = self._fix_furb113(content)
        total_fixes += fixes_113

        content, fixes_118 = self._fix_furb118(content)
        total_fixes += fixes_118

        content, fixes_115 = self._fix_furb115(content)
        total_fixes += fixes_115

        content, fixes_126 = self._fix_furb126(content)
        total_fixes += fixes_126

        content, fixes_110 = self._fix_furb110(content)
        total_fixes += fixes_110

        content, fixes_123 = self._fix_furb123(content)
        total_fixes += fixes_123

        content, fixes_142 = self._fix_furb142(content)
        total_fixes += fixes_142

        content, fixes_148 = self._fix_furb148(content)
        total_fixes += fixes_148

        content, fixes_161 = self._fix_furb161(content)
        total_fixes += fixes_161

        content, fixes_124 = self._fix_furb124(content)
        total_fixes += fixes_124

        content, fixes_138 = self._fix_furb138(content)
        total_fixes += fixes_138

        content, fixes_108 = self._fix_furb108(content)
        total_fixes += fixes_108

        content, fixes_117 = self._fix_furb117(content)
        total_fixes += fixes_117

        content, fixes_173 = self._fix_furb173(content)
        total_fixes += fixes_173

        content, fixes_183 = self._fix_furb183(content)
        total_fixes += fixes_183

        content, fixes_143 = self._fix_furb143(content)
        total_fixes += fixes_143

        content, fixes_141 = self._fix_furb141(content)
        total_fixes += fixes_141

        content, fixes_135 = self._fix_furb135(content)
        total_fixes += fixes_135

        content, fixes_111 = self._fix_furb111(content)
        total_fixes += fixes_111

        return content, total_fixes

    def _fix_furb102_ast_grep(self, content: str) -> tuple[str, int]:
        total_fixes = 0

        content, fixes = self._run_ast_grep_fix(
            content, AST_GREP_RULES["furb102-startswith-tuple"]
        )
        total_fixes += fixes

        content, fixes = self._run_ast_grep_fix(
            content, AST_GREP_RULES["furb102-startswith-tuple-or"]
        )
        total_fixes += fixes

        return content, total_fixes

    def _fix_furb102_regex(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content

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

        multiline_pattern = r"(\bif\s+)not\s+(.+?)\.startswith\(([^)]+)\)\s+and\s*\(\s*\n\s+not\s+\2\.startswith\(([^)]+)\)\s*\n\s*\):"
        for match in re.finditer(multiline_pattern, new_content, re.MULTILINE):
            prefix, expr, arg1, arg2 = match.groups()
            expr = expr.strip()
            old_text = match.group(0)
            new_text = f"{prefix}not {expr}.startswith(({arg1}, {arg2})):"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        separate_lines_pattern = r"and\s*\(\s*not\s+(.+?)\.startswith\(([^)]+)\)\s*\)\s*\n\s*and\s*\(\s*not\s+\1\.startswith\(((?:[^()]*|\([^()]*\))*)\)"
        for match in re.finditer(separate_lines_pattern, new_content, re.MULTILINE):
            expr, arg1, arg2 = match.groups()
            expr = expr.strip()
            old_text = match.group(0)

            if arg2.startswith("(") and arg2.endswith(")"):
                inner = arg2[1:-1].strip()
                combined = f"({arg1}, {inner})"
            else:
                combined = f"({arg1}, {arg2})"

            new_text = f"and (not {expr}.startswith({combined}))"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb107(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        lines = content.split("\n")

        matches_to_fix = []

        for i, line in enumerate(lines):
            try_match = re.match(r"^(\s*)try:\s*$", line)
            if not try_match:
                continue

            indent = try_match.group(1)
            body_indent = indent + "    "

            total_except_count = 0
            pass_only_except = None
            j = i + 1

            while j < len(lines):
                curr_line = lines[j]

                if curr_line.strip() and not curr_line.startswith(indent):
                    break

                except_match = re.match(
                    rf"^{re.escape(indent)}except\s+(\([^)]+\)|\w+(?:\s*,\s*\w+)*)(?:\s+as\s+\w+)?:",
                    curr_line,
                ) or re.match(rf"^{re.escape(indent)}except\s*:", curr_line)

                if except_match:
                    total_except_count += 1
                    exception_type = (
                        except_match.group(1) if except_match.lastindex else "Exception"
                    )

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
                        if j + 1 < len(lines):
                            pass_match = re.match(
                                rf"^{re.escape(body_indent)}pass\s*$", lines[j + 1]
                            )
                            if pass_match:
                                if pass_only_except is None:
                                    pass_only_except = (j, j + 1, exception_type)
                                j += 1
                            else:
                                pass_only_except = "INVALID"
                        else:
                            pass_only_except = "INVALID"

                j += 1

            if (
                total_except_count != 1
                or pass_only_except is None
                or pass_only_except == "INVALID"
            ):
                continue

            matches_to_fix.append((i, pass_only_except))

        result_lines = lines.copy()
        for try_idx, (except_line_idx, pass_line_idx, exception_type) in reversed(
            matches_to_fix
        ):
            indent = re.match(r"^(\s*)try:\s*$", lines[try_idx]).group(1)

            result_lines[try_idx] = f"{indent}with suppress({exception_type}):"

            if pass_line_idx is not None:
                del result_lines[pass_line_idx]
                del result_lines[except_line_idx]
            else:
                del result_lines[except_line_idx]

            total_fixes += 1

        return "\n".join(result_lines), total_fixes

    def _fix_furb109(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content

        for_pattern = r"^(\s*)for\s+(.+?)\s+in\s+\[([^\]\n]+)\]:"
        matches = list(re.finditer(for_pattern, new_content, re.MULTILINE))
        for match in reversed(matches):
            indent, var_name, list_contents = (
                match.group(1),
                match.group(2).strip(),
                match.group(3),
            )

            if "[" not in list_contents and "{" not in list_contents:
                old_text = match.group(0)
                new_text = f"{indent}for {var_name} in ({list_contents}):"
                new_content = (
                    new_content[: match.start()] + new_text + new_content[match.end() :]
                )
                total_fixes += 1

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
        total_fixes = 0
        new_content = content

        pattern = r"(\w+)\.append\(([^(),\n]+)\)\n(\s+)\1\.append\(([^(),\n]+)\)"

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
        total_fixes = 0
        new_content = content

        numeric_pattern = r"lambda\s+(\w+)\s*:\s*\1\s*\[\s*(\d+)\s*\]"
        for match in re.finditer(numeric_pattern, new_content):
            old_text = match.group(0)
            index = match.group(2)
            new_text = f"operator.itemgetter({index})"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        string_pattern = r'lambda\s+(\w+)\s*:\s*\1\s*\[\s*["\']([^"\']+)["\']\s*\]'
        for match in re.finditer(string_pattern, new_content):
            old_text = match.group(0)
            key = match.group(2)
            new_text = f'operator.itemgetter("{key}")'
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb115(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content

        patterns = [
            (r"\blen\(([^()]+)\)\s*==\s*0\b", r"not \1"),
            (r"\blen\(([^()]+)\)\s*>=\s*1\b", r"\1"),
            (r"\blen\(([^()]+)\)\s*>\s*0\b", r"\1"),
        ]

        for pattern, replacement in patterns:
            for match in re.finditer(pattern, new_content):
                old_text = match.group(0)
                var = match.group(1).strip()

                if "not" in replacement:
                    new_text = f"not {var}"
                else:
                    new_text = var
                new_content = new_content.replace(old_text, new_text, 1)
                total_fixes += 1

        return new_content, total_fixes

    def _fix_furb126(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        lines = content.split("\n")
        result_lines = lines.copy()

        i = 0
        while i < len(lines) - 1:
            line = lines[i]
            next_line = lines[i + 1] if i + 1 < len(lines) else ""

            else_match = re.match(r"^(\s*)else:\s*$", line)
            if not else_match:
                i += 1
                continue

            indent = else_match.group(1)
            body_indent = indent + "    "

            return_match = re.match(rf"^{re.escape(body_indent)}return\b", next_line)
            if not return_match:
                i += 1
                continue

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

            result_lines[i] = ""
            result_lines[i + 1] = next_line.replace(body_indent, indent, 1)
            total_fixes += 1
            i += 2

        new_content = "\n".join(line for line in result_lines)
        return new_content, total_fixes

    def _fix_furb110(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content

        pattern = r"\b(\w+)\s+if\s+\1\s+else\s+(\w+)\b"
        for match in re.finditer(pattern, new_content):
            var1, var2 = match.group(1), match.group(2)
            old_text = match.group(0)
            new_text = f"{var1} or {var2}"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb123(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content


        str_pattern = r"\bstr\(([a-z_]*path[a-z_]*|p)\)"
        for match in re.finditer(str_pattern, new_content):
            var_name = match.group(1)
            old_text = match.group(0)
            new_content = new_content.replace(old_text, var_name, 1)
            total_fixes += 1

        list_pattern = r"\blist\(([a-z_]*(?:lines|list|results|items|nodes|args|plans|details|paths|batch_results)[a-z_]*)\)"
        for match in re.finditer(list_pattern, new_content):
            var_name = match.group(1)
            old_text = match.group(0)
            new_text = f"{var_name}.copy()"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        list_attr_pattern = r"\blist\(([a-z_]+\.[a-z_]+)\)"
        for match in re.finditer(list_attr_pattern, new_content):
            var_name = match.group(1)
            old_text = match.group(0)
            new_text = f"{var_name}.copy()"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        set_pattern = r"\bset\(([a-z_]*(?:set|_set|param_names)[a-z_]*)\)"
        for match in re.finditer(set_pattern, new_content):
            var_name = match.group(1)
            old_text = match.group(0)
            new_text = f"{var_name}.copy()"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        dict_self_pattern = r"\bdict\(self\.([a-z_]+)\)"
        for match in re.finditer(dict_self_pattern, new_content):
            attr_name = match.group(1)
            old_text = match.group(0)
            new_text = f"self.{attr_name}.copy()"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        dict_pattern = r"\bdict\(([a-z_]*(?:dict|_dict|mapping|data|config)[a-z_]*)\)"
        for match in re.finditer(dict_pattern, new_content):
            var_name = match.group(1)
            old_text = match.group(0)
            new_text = f"{var_name}.copy()"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb142(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content

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
        total_fixes = 0
        lines = content.split("\n")
        result_lines = lines.copy()
        i = 0

        while i < len(lines):
            line = lines[i]

            enum_match = re.match(
                r"^(\s*)for\s+(\w+)\s*,\s*(\w+)\s+in\s+enumerate\(([^)]+)\):\s*$", line
            )
            if not enum_match:
                i += 1
                continue

            indent, idx_var, val_var, iterable = enum_match.groups()

            idx_used = False
            for j in range(i + 1, len(lines)):
                body_line = lines[j]

                if body_line.strip() and not body_line.startswith(indent + "    "):
                    if body_line.startswith(indent) and not body_line.startswith(
                        indent + " "
                    ):
                        break
                    break

                code_part = body_line.split("#")[0] if "#" in body_line else body_line
                if re.search(rf"\b{re.escape(idx_var)}\b", code_part):
                    idx_used = True
                    break

            if not idx_used:
                result_lines[i] = f"{indent}for {val_var} in {iterable}:"
                total_fixes += 1

            i += 1

        return "\n".join(result_lines), total_fixes

    def _fix_furb161(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content

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
        total_fixes = 0
        new_content = content

        pattern1 = r"\b(\w+)\s*==\s*(\w+)\s+and\s+(\w+)\s*==\s*\2\b"
        for match in re.finditer(pattern1, new_content):
            var1, common, var2 = match.group(1), match.group(2), match.group(3)

            if var1 == var2:
                continue
            old_text = match.group(0)
            new_text = f"{var1} == {common} == {var2}"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        pattern2 = r"\b(\w+)\s*==\s*(\w+)\s+and\s+\2\s*==\s*(\w+)\b"
        for match in re.finditer(pattern2, new_content):
            var1, common, var2 = match.group(1), match.group(2), match.group(3)

            if var1 == var2:
                continue
            old_text = match.group(0)
            new_text = f"{var1} == {common} == {var2}"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb138(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        lines = content.split("\n")
        result_lines = lines.copy()
        i = 0

        while i < len(lines) - 2:
            line = lines[i]

            init_match = re.match(r"^(\s*)(\w+)\s*=\s*\[\]\s*$", line)
            if not init_match:
                i += 1
                continue

            indent, var_name = init_match.group(1), init_match.group(2)

            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            for_match = re.match(
                rf"^{re.escape(indent)}for\s+(\w+)\s+in\s+(.+?):\s*$", next_line
            )
            if not for_match:
                i += 1
                continue

            loop_var, iterable = for_match.group(1), for_match.group(2).strip()

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

            if not re.search(rf"\b{re.escape(loop_var)}\b", append_arg):
                i += 1
                continue

            if i + 3 < len(lines):
                following = lines[i + 3]
                if following.startswith(body_indent) and following.strip():
                    i += 1
                    continue

            list_comp = (
                f"{indent}{var_name} = [{append_arg} for {loop_var} in {iterable}]"
            )
            result_lines[i] = list_comp
            result_lines[i + 1] = ""
            result_lines[i + 2] = ""
            total_fixes += 1
            i += 3

        new_content = "\n".join(line for line in result_lines)
        return new_content, total_fixes

    def _fix_furb108(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content

        pattern = r"\b(\w+)\s*==\s*(\w+)\s+or\s+(\w+)\s*==\s*\2\b"
        for match in re.finditer(pattern, new_content):
            var1, common, var2 = match.group(1), match.group(2), match.group(3)

            if var1 == var2:
                continue
            old_text = match.group(0)
            new_text = f"{common} in ({var1}, {var2})"
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb117(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content


        pattern = r'\bopen\(([a-z_]*(?:path|file)[a-z_]*),\s*(".*?")\)'
        for match in re.finditer(pattern, new_content):
            var_name = match.group(1)
            mode = match.group(2)
            old_text = match.group(0)
            new_text = f'{var_name}.open({mode})'
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb173(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content


        pattern = r'\{\*\*([a-z_][a-z0-9_.]*),\s*\*\*([a-z_][a-z0-9_.]*)\}'
        for match in re.finditer(pattern, new_content):
            dict1 = match.group(1)
            dict2 = match.group(2)
            old_text = match.group(0)
            new_text = f'{dict1} | {dict2}'
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1


        complex_pattern = r'\{\*\*([a-z_][a-z0-9_.]*),\s*("[^"]+":\s*[^,}]+),\s*\*\*([a-z_][a-z0-9_.]*)\}'
        for match in re.finditer(complex_pattern, new_content):
            dict1 = match.group(1)
            literal = match.group(2)
            dict2 = match.group(3)
            old_text = match.group(0)
            new_text = f'{dict1} | {{{literal}}} | {dict2}'
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb183(self, content: str) -> tuple[str, int]:
        """Fix FURB183: Replace f"{x}" with str(x) - ONLY for f-strings with single expression."""
        total_fixes = 0
        new_content = content

        # Pattern: f"{single_expr}" where f-string contains ONLY one expression
        # Must NOT match f"text{expr}" or f"{expr}text" - only f"{expr}"
        # The pattern ensures no text before or after the {...}
        pattern = r'\bf"\{([a-z_][a-z0-9_.]*(?:\([^)]*\))?(?:\.[a-z_]+)*)\}"'
        for match in re.finditer(pattern, new_content, re.IGNORECASE):
            expr = match.group(1)
            old_text = match.group(0)
            # Verify this is a standalone f-string with only the expression
            # by checking the matched text is exactly f"{...}"
            if old_text == f'f"{{{expr}}}"':
                new_text = f'str({expr})'
                new_content = new_content.replace(old_text, new_text, 1)
                total_fixes += 1

        return new_content, total_fixes

    def _fix_furb143(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content


        pattern = r'\b([a-z_]*(?:output|str|text|message|msg|result|data|content|value|response)[a-z_]*)\s+or\s+""'
        for match in re.finditer(pattern, new_content, re.IGNORECASE):
            var_name = match.group(1)
            old_text = match.group(0)
            new_content = new_content.replace(old_text, var_name, 1)
            total_fixes += 1


        dict_pattern = r'\b([a-z_]*(?:dict|mapping|config|data|params|options|meta)[a-z_]*)\s+or\s+\{\}'
        for match in re.finditer(dict_pattern, new_content, re.IGNORECASE):
            var_name = match.group(1)
            old_text = match.group(0)
            new_content = new_content.replace(old_text, var_name, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb141(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content


        pattern = r'\bos\.path\.exists\(([a-z_][a-z0-9_.]*)\)'
        for match in re.finditer(pattern, new_content):
            path_arg = match.group(1)
            old_text = match.group(0)
            new_text = f'Path({path_arg}).exists()'
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb135(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        lines = content.split('\n')
        result_lines = lines.copy()

        for i, line in enumerate(lines):

            match = re.match(r'^(\s*)for\s+([a-z_][a-z0-9_]*)\s*,\s*([a-z_][a-z0-9_]*)\s+in\s+([a-z_][a-z0-9_.]*)\.items\(\):\s*$', line)
            if not match:
                continue

            indent, key_var, val_var, dict_name = match.groups()


            if key_var == '_' or key_var.startswith('_unused'):
                old_text = line
                new_text = f'{indent}for {val_var} in {dict_name}.values():'
                result_lines[i] = new_text
                total_fixes += 1

        return '\n'.join(result_lines), total_fixes

    def _fix_furb111(self, content: str) -> tuple[str, int]:
        total_fixes = 0
        new_content = content


        pattern = r'\blambda:\s*([a-z_][a-z0-9_.]*(?:\([^)]*\))?)\s*(?=[,\)\]])'
        for match in re.finditer(pattern, new_content):
            call = match.group(1)
            old_text = match.group(0)


            if call.endswith('()'):
                new_text = call[:-2]
            else:
                new_text = call

            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes


class _StartswithTupleTransformer(ast.NodeTransformer):
    def __init__(self) -> None:
        self.fixes = 0

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:

        if not isinstance(node.op, ast.Or):
            return self.generic_visit(node)

        startswith_groups = self._group_startswith_calls(node.values)  # type: ignore[arg-type]

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
        tuple_arg = ast.Tuple(elts=string_args, ctx=ast.Load())  # type: ignore[arg-type]  # type: ignore[arg-type]
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
        return ast.BoolOp(op=ast.Or(), values=new_values)  # type: ignore[arg-type]

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
                new_tuple = ast.Tuple(elts=comparator.elts, ctx=ast.Load())  # type: ignore[attr-defined]
                new_comparators.append(new_tuple)
                self.fixes += 1
            else:
                new_comparators.append(self.visit(comparator))

        new_ids = [id(c) for c in new_comparators]
        if new_ids != original_ids:
            return ast.Compare(  # type: ignore[arg-type]
                left=self.visit(node.left),
                ops=node.ops,
                comparators=new_comparators,  # type: ignore[arg-type]
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
    def __init__(self) -> None:
        self.fixes = 0

    def visit_For(self, node: ast.For) -> ast.AST:

        if isinstance(node.iter, ast.List):
            if self._is_safe_list(node.iter):
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
