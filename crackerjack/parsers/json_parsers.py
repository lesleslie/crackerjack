from __future__ import annotations

import json
import logging
import typing as t
from pathlib import Path

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.base import JSONParser
from crackerjack.parsers.factory import ParserFactory
from crackerjack.services.testing.test_result_parser import TestResultParser

logger = logging.getLogger(__name__)


class RuffJSONParser(JSONParser):
    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        logger.debug(f"🐛 RuffJSONParser.parse_json() received: {type(data).__name__}")
        if not isinstance(data, list):
            logger.warning(f"Expected list from ruff, got {type(data)}")
            return []
        issues: list[Issue] = []
        for item in data:
            try:
                issue = self._parse_ruff_item(item)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.error(f"Error parsing ruff JSON item: {e}", exc_info=True)
        logger.info(f"Parsed {len(issues)} issues from ruff JSON output")
        return issues

    def _parse_ruff_item(self, item: object) -> Issue | None:
        if not isinstance(item, dict):
            logger.warning(f"Skipping non-dict item in ruff output: {type(item)}")
            return None
        ruff_item = t.cast("dict[str, t.Any]", item)
        required_fields = ["filename", "location", "code", "message"]
        if not all(k in ruff_item for k in required_fields):
            missing = required_fields - ruff_item.keys()
            logger.warning(
                f"Skipping ruff item missing required fields {missing}: {ruff_item}"
            )
            return None
        file_path = str(ruff_item["filename"])
        line_number = self._extract_line_number_from_location(ruff_item.get("location"))
        if line_number is None and "location" in ruff_item:
            logger.warning(
                f"Invalid location format in ruff output: {ruff_item['location']}"
            )
            return None
        code = str(ruff_item["code"])
        message = str(ruff_item["message"])
        return Issue(
            type=self._get_issue_type(code),
            severity=self._get_severity(code),
            message=f"{code} {message}",
            file_path=file_path,
            line_number=line_number,
            stage="ruff-check",
            details=self._build_ruff_details(item, code),
        )

    def _extract_line_number_from_location(self, location: object | None) -> int | None:
        if not isinstance(location, dict):
            return None
        line_number = location.get("row")
        return int(line_number) if isinstance(line_number, int) else None

    def _build_ruff_details(self, item: dict, code: str) -> list[str]:
        details = [f"code: {code}"]
        details.append("fixable: True" if "fix" in item else "fixable: False")
        if "url" in item:
            details.append(f"url: {item['url']}")
        return details

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        return len(data) if isinstance(data, list) else 0

    def _get_issue_type(self, code: str) -> IssueType:
        if not code:
            return IssueType.FORMATTING

        code_prefix_handlers = {
            "UP": IssueType.FORMATTING,
            "C": IssueType.COMPLEXITY,
            "PE": IssueType.PERFORMANCE,
            "F4": IssueType.IMPORT_ERROR,
            "F8": IssueType.FORMATTING,
            "E999": IssueType.TYPE_ERROR,
            "E502": IssueType.TYPE_ERROR,
            "S": IssueType.SECURITY,
            "PLR": IssueType.COMPLEXITY,
        }

        for prefix, issue_type in code_prefix_handlers.items():
            if len(prefix) >= 2 and code.startswith(prefix):
                return issue_type
            elif code == prefix:
                return issue_type
            elif len(prefix) == 1 and code.startswith(prefix):
                return issue_type

        if code.startswith("F"):
            return IssueType.FORMATTING
        if code.startswith("E"):
            return IssueType.FORMATTING
        if code.startswith("W"):
            return IssueType.FORMATTING

        return IssueType.FORMATTING

    def _get_severity(self, code: str) -> Priority:
        if code.startswith(("C9", "S")):
            return Priority.HIGH
        if code.startswith("F4"):
            return Priority.MEDIUM
        return Priority.LOW


class MypyJSONParser(JSONParser):
    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        if not isinstance(data, list):
            logger.warning(f"Expected list from mypy, got {type(data)}")
            return []
        issues: list[Issue] = []
        for item in data:
            try:
                issue = self._parse_mypy_item(item)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.error(f"Error parsing mypy JSON item: {e}", exc_info=True)
        logger.info(f"Parsed {len(issues)} issues from mypy JSON output")
        return issues

    def _parse_mypy_item(self, item: object) -> Issue | None:
        if not isinstance(item, dict):
            logger.warning(f"Skipping non-dict item in mypy output: {type(item)}")
            return None
        if not self._validate_mypy_item(item):
            return None
        return self._build_mypy_issue(item)

    def _validate_mypy_item(self, item: dict) -> bool:
        required_fields = ["file", "line", "message"]
        if not all(k in item for k in required_fields):
            missing = required_fields - item.keys()
            logger.warning(
                f"Skipping mypy item missing required fields {missing}: {item}"
            )
            return False
        return True

    def _build_mypy_issue(self, item: dict) -> Issue:
        file_path = str(item["file"])
        line_number = self._parse_line_number(item.get("line"))
        message = str(item["message"])
        severity_str = str(item.get("severity", "error"))
        severity = Priority.HIGH if severity_str == "error" else Priority.MEDIUM
        return Issue(
            type=IssueType.TYPE_ERROR,
            severity=severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
            stage="mypy",
            details=[f"severity: {severity_str}"],
        )

    def _parse_line_number(self, value: object) -> int | None:
        if isinstance(value, int):
            return int(value)
        return None

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        return len(data) if isinstance(data, list) else 0


class BanditJSONParser(JSONParser):
    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        if not isinstance(data, dict) or "results" not in data:
            logger.warning(
                f"Expected dict with 'results' from bandit, got {type(data)}"
            )
            return []
        results = data["results"]
        if not isinstance(results, list):
            logger.warning(f"Bandit 'results' is not a list: {type(results)}")
            return []
        issues: list[Issue] = []
        for item in results:
            try:
                if not isinstance(item, dict):
                    logger.warning(
                        f"Skipping non-dict item in bandit output: {type(item)}"
                    )
                    continue
                bandit_item = t.cast("dict[str, t.Any]", item)
                required_fields = ["filename", "issue_text", "line_number"]
                if not all(k in bandit_item for k in required_fields):
                    missing = required_fields - bandit_item.keys()
                    logger.warning(
                        f"Skipping bandit item missing required fields {missing}: {bandit_item}"
                    )
                    continue
                file_path = str(bandit_item["filename"])
                line_number = bandit_item.get("line_number")
                if isinstance(line_number, int):
                    line_number = int(line_number)
                else:
                    line_number = None
                message = str(bandit_item["issue_text"])
                severity_str = str(item.get("issue_severity", "MEDIUM"))
                test_id = str(item.get("test_id", "UNKNOWN"))
                severity = self._map_severity(severity_str)
                issues.append(
                    Issue(
                        type=IssueType.SECURITY,
                        severity=severity,
                        message=f"{test_id}: {message}",
                        file_path=file_path,
                        line_number=line_number,
                        stage="bandit",
                        details=[f"test_id: {test_id}", f"severity: {severity_str}"],
                    )
                )
            except Exception as e:
                logger.error(f"Error parsing bandit JSON item: {e}", exc_info=True)
        logger.info(f"Parsed {len(issues)} issues from bandit JSON output")
        return issues

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            return len(results) if isinstance(results, list) else 0
        return 0

    def _map_severity(self, severity_str: str) -> Priority:
        mapping = {
            "CRITICAL": Priority.CRITICAL,
            "HIGH": Priority.CRITICAL,
            "MEDIUM": Priority.HIGH,
            "LOW": Priority.MEDIUM,
        }
        return mapping.get(severity_str.upper(), Priority.MEDIUM)


class ComplexipyJSONParser(JSONParser):
    def __init__(self, max_complexity: int = 15) -> None:
        super().__init__()
        self.max_complexity = max_complexity
        self._line_number_cache: dict[str, dict[str, int]] = {}

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        from pathlib import Path

        json_path = self._find_json_path(output)
        if not json_path:
            logger.warning("Could not find complexipy JSON file path in output")
            return []
        if not Path(json_path).exists():
            logger.warning(f"Complexipy JSON file not found: {json_path}")
            return []
        try:
            json_content = Path(json_path).read_text()
            data = json.loads(json_content)
            logger.debug(
                f"Read complexipy JSON file: {json_path} ({(len(data) if isinstance(data, list) else 'N/A')} entries)"
            )
        except Exception as e:
            logger.error(f"Error reading/parsing complexipy JSON file: {e}")
            return []
        return self.parse_json(data)

    def _find_json_path(self, output: str) -> str | None:
        import re
        from pathlib import Path

        match = re.search("Results saved at\\s+(.+?\\.json)", output, re.DOTALL)
        if match:
            return match.group(1).strip()

        if "Results saved at" not in output:
            return None
        project_root = Path.cwd()
        patterns = [
            "complexipy_results_*.json",
            "complexipy.json",
            ".complexipy_cache/*.json",
            ".complexipy/*.json",
        ]
        for pattern in patterns:
            matches = sorted(
                project_root.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if matches:
                logger.debug(f"Found complexipy JSON at: {matches[0]}")
                return str(matches[0])
        from crackerjack.adapters._output_paths import AdapterOutputPaths

        output_dir = AdapterOutputPaths.get_output_dir("complexipy")
        if output_dir.exists():
            matches = sorted(
                output_dir.glob("complexipy_results_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if matches:
                logger.debug(f"Found complexipy JSON in cache: {matches[0]}")
                return str(matches[0])
        return None

    def _extract_line_number_tier1(
        self, file_path: str, function_name: str
    ) -> int | None:
        if cached_line := self._get_cached_line_number(file_path, function_name):
            return cached_line
        if not self._is_valid_file_for_ast_extraction(file_path):
            return None
        self._ensure_cache_entry_exists(file_path)
        search_names = self._build_search_names(function_name)
        line_number = self._search_ast_for_line_number(
            file_path, function_name, search_names
        )
        return line_number

    def _get_cached_line_number(self, file_path: str, function_name: str) -> int | None:
        if file_path in self._line_number_cache:
            return self._line_number_cache[file_path].get(function_name)
        return None

    def _is_valid_file_for_ast_extraction(self, file_path: str) -> bool:
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            logger.debug(f"File not found for line number extraction: {file_path}")
            return False
        if path.suffix != ".py":
            logger.debug(f"Not a Python file, skipping AST extraction: {file_path}")
            return False
        return True

    def _ensure_cache_entry_exists(self, file_path: str) -> None:
        if file_path not in self._line_number_cache:
            self._line_number_cache[file_path] = {}

    def _build_search_names(self, function_name: str) -> list[str]:
        search_names = [function_name]
        if "::" in function_name:
            method_name = function_name.split("::")[-1]
            search_names.insert(0, method_name)
        return search_names

    def _search_ast_for_line_number(
        self, file_path: str, function_name: str, search_names: list[str]
    ) -> int | None:
        import ast
        from pathlib import Path

        try:
            content = Path(file_path).read_text()
            tree = ast.parse(content)
            for search_name in search_names:
                if line_number := self._find_function_in_ast(tree, search_name):
                    self._line_number_cache[file_path][function_name] = line_number
                    logger.debug(
                        f"Found line number for '{function_name}' (searched as '{search_name}') in {file_path}: {line_number}"
                    )
                    return line_number
            logger.debug(
                f"Function '{function_name}' not found in {file_path} (searched for: {search_names})"
            )
            return None
        except (SyntaxError, OSError, UnicodeDecodeError) as e:
            logger.debug(
                f"Failed to extract line number for '{function_name}' in {file_path}: {e}"
            )
            return None
        except Exception as e:
            logger.warning(
                f"Unexpected error extracting line number for '{function_name}' in {file_path}: {e}"
            )
            return None

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        if not isinstance(data, list):
            logger.warning(f"Complexipy JSON data is not a list: {type(data)}")
            return []
        issues: list[Issue] = []
        for item in data:
            try:
                issue = self._parse_complexipy_item(item)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.error(f"Error parsing complexipy JSON item: {e}", exc_info=True)
        logger.info(
            f"Parsed {len(issues)} issues from complexipy JSON output (filtered from {len(data)} total functions, threshold: >{self.max_complexity})"
        )
        return issues

    def _parse_complexipy_item(self, item: object) -> Issue | None:
        if not isinstance(item, dict):
            logger.warning(f"Skipping non-dict item in complexipy output: {type(item)}")
            return None
        cx_item = t.cast("dict[str, t.Any]", item)
        required_fields = ["complexity", "file_name", "function_name", "path"]
        if not all(k in cx_item for k in required_fields):
            missing = required_fields - cx_item.keys()
            logger.warning(
                f"Skipping complexipy item missing required fields {missing}: {cx_item}"
            )
            return None
        complexity = cx_item["complexity"]
        if not self._validate_complexity_value(complexity):
            return None
        if not self._is_complexity_above_threshold(complexity):
            return None
        return self._create_complexipy_issue(cx_item, complexity)

    def _validate_complexity_value(self, complexity: object) -> bool:
        if not isinstance(complexity, int):
            logger.warning(
                f"Skipping invalid complexity value: {complexity} (type: {type(complexity)})"
            )
            return False
        return True

    def _is_complexity_above_threshold(self, complexity: int) -> bool:
        if complexity <= self.max_complexity:
            logger.debug(
                f"Skipping function with complexity {complexity} <= threshold {self.max_complexity}"
            )
            return False
        return True

    def _create_complexipy_issue(self, item: dict, complexity: int) -> Issue:
        file_path = str(item["path"])
        function_name = str(item["function_name"])
        line_number = self._extract_line_number_tier1(file_path, function_name)
        severity = self._calculate_severity(complexity)
        message = f"Function '{function_name}' has complexity {complexity}"
        details = self._build_complexipy_details(complexity, function_name, line_number)
        return Issue(
            type=IssueType.COMPLEXITY,
            severity=severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
            stage="complexity",
            details=details,
        )

    def _calculate_severity(self, complexity: int) -> Priority:
        if complexity > self.max_complexity * 2:
            return Priority.HIGH
        if complexity > self.max_complexity:
            return Priority.MEDIUM
        return Priority.LOW

    def _build_complexipy_details(
        self, complexity: int, function_name: str, line_number: int | None
    ) -> list[str]:
        details = [
            f"complexity: {complexity}",
            f"function: {function_name}",
            f"threshold: >{self.max_complexity}",
        ]
        if line_number:
            details.append(f"line_number: {line_number} (extracted via AST)")
        else:
            details.append("line_number: None (agent will search by function name)")
        return details

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        if isinstance(data, list):
            return sum(
                1
                for item in data
                if isinstance(item, dict)
                and isinstance(item.get("complexity"), int)
                and (
                    t.cast("dict[str, t.Any]", item)["complexity"] > self.max_complexity
                )
            )
        return 0

    def _find_function_in_ast(self, tree: t.Any, search_name: str) -> int | None:
        if "::" in search_name:
            return self._find_class_method_in_ast(tree, search_name)
        return self._find_simple_function_in_ast(tree, search_name)

    def _find_class_method_in_ast(self, tree: t.Any, search_name: str) -> int | None:
        class_name, method_name = search_name.split("::", 1)
        if line_number := self._search_method_in_class(tree, class_name, method_name):
            return line_number
        logger.debug(
            f"Could not find class-qualified method '{search_name}', falling back to bare name '{method_name}'"
        )
        return self._find_simple_function_in_ast(tree, method_name)

    def _search_method_in_class(
        self, tree: t.Any, class_name: str, method_name: str
    ) -> int | None:
        class_node = self._find_class_node(tree, class_name)
        if class_node:
            return self._find_method_in_class_node(class_node, method_name)
        return None

    def _find_class_node(self, tree: t.Any, class_name: str) -> t.Any | None:
        import ast

        for node in ast.walk(t.cast(ast.AST, tree)):
            if self._is_class_def_with_name(node, class_name):
                return node
        return None

    def _is_class_def_with_name(self, node: t.Any, class_name: str) -> bool:
        import ast

        return isinstance(node, ast.ClassDef) and node.name == class_name

    def _find_method_in_class_node(
        self, class_node: t.Any, method_name: str
    ) -> int | None:
        import ast

        for child in ast.walk(class_node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name == method_name:
                    logger.debug(f"Found class-qualified method at line {child.lineno}")
                    return child.lineno
        return None

    def _find_simple_function_in_ast(
        self, tree: t.Any, function_name: str
    ) -> int | None:
        import ast

        for node in ast.walk(t.cast(ast.AST, tree)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    return node.lineno
        return None

    def _is_function_def_with_name(self, node: t.Any, function_name: str) -> bool:
        import ast

        return (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        )


class PyscnJSONParser(JSONParser):
    def __init__(self, max_complexity: int = 15) -> None:
        super().__init__()
        self.max_complexity = max_complexity

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        json_path = self._find_json_path(output)
        if not json_path:
            from crackerjack.parsers.factory import ParsingError

            raise ParsingError(
                "pyscn output doesn't reference a JSON report "
                "(cobra/text output or pre-write failure?)",
                tool_name=tool_name,
                output=output[:200],
            )
        json_file = Path(json_path)
        if not json_file.exists():
            logger.warning(f"pyscn JSON report not found: {json_path}")
            return []
        try:
            data = json.loads(json_file.read_text())
        except Exception as e:
            logger.error(f"Error reading/parsing pyscn JSON report: {e}")
            return []
        return self.parse_json(data)

    def _find_json_path(self, output: str) -> str | None:
        import re

        match = re.search(
            r"(?:Unified\s+)?JSON\s+report\s+generated:\s+(?P<path>\S+\.json)",
            output,
        )
        if match:
            return match.group("path").strip()
        return None

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        if not isinstance(data, dict):
            logger.warning(f"Expected dict from pyscn, got {type(data)}")
            return []
        issues: list[Issue] = []
        issues.extend(self._parse_complexity_section(data))
        issues.extend(self._parse_dead_code_section(data))
        logger.info(
            f"Parsed {len(issues)} total issues from pyscn JSON "
            f"(complexity + dead_code)"
        )
        return issues

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        if not isinstance(data, dict):
            return 0
        return self._count_complexity_above_threshold(
            data
        ) + self._count_dead_code_blocks(data)

    def _count_complexity_above_threshold(self, data: dict) -> int:
        complexity_section = data.get("complexity")
        if not isinstance(complexity_section, dict):
            return 0
        functions = complexity_section.get("Functions")
        if not isinstance(functions, list):
            return 0
        count = 0
        for item in functions:
            if not isinstance(item, dict):
                continue
            metrics = item.get("Metrics")
            if not isinstance(metrics, dict):
                continue
            complexity = metrics.get("Complexity")
            if isinstance(complexity, int) and complexity > self.max_complexity:
                count += 1
        return count

    def _count_dead_code_blocks(self, data: dict) -> int:
        dead_section = data.get("dead_code")
        if not isinstance(dead_section, dict):
            return 0
        files_list = dead_section.get("files")

        if files_list is None:
            return 0
        if not isinstance(files_list, list):
            return 0
        count = 0
        for file_entry in files_list:
            if not isinstance(file_entry, dict):
                continue
            functions = file_entry.get("functions")
            if not isinstance(functions, list):
                continue
            for fn in functions:
                if not isinstance(fn, dict):
                    continue
                dead_blocks = fn.get("dead_blocks")
                if isinstance(dead_blocks, list):
                    count += len(dead_blocks)
        return count

    def _parse_complexity_section(self, data: dict[str, object]) -> list[Issue]:
        complexity_section = data.get("complexity")
        if not isinstance(complexity_section, dict):
            logger.debug("pyscn JSON has no 'complexity' section")
            return []
        functions = complexity_section.get("Functions")
        if not isinstance(functions, list):
            logger.warning(
                f"pyscn 'complexity.Functions' is not a list: {type(functions)}"
            )
            return []
        issues: list[Issue] = []
        for item in functions:
            try:
                issue = self._parse_pyscn_function(item)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.error(f"Error parsing pyscn function item: {e}", exc_info=True)
        logger.debug(
            f"pyscn complexity: {len(issues)} issues from "
            f"{len(functions)} functions (threshold: >{self.max_complexity})"
        )
        return issues

    def _parse_dead_code_section(self, data: dict[str, object]) -> list[Issue]:
        dead_section = data.get("dead_code")
        if not isinstance(dead_section, dict):
            logger.debug("pyscn JSON has no 'dead_code' section")
            return []
        files_list = dead_section.get("files")
        if files_list is None:
            return []
        if not isinstance(files_list, list):
            logger.warning(f"pyscn 'dead_code.files' is not a list: {type(files_list)}")
            return []
        issues: list[Issue] = []
        for file_entry in files_list:
            if not isinstance(file_entry, dict):
                continue
            file_path = str(file_entry.get("file_path", ""))
            functions = file_entry.get("functions")
            if not isinstance(functions, list):
                continue
            for fn in functions:
                if not isinstance(fn, dict):
                    continue
                fn_name = str(fn.get("name", "<unknown>"))
                start_line = fn.get("start_line")
                if not isinstance(start_line, int):
                    start_line = None
                dead_blocks = fn.get("dead_blocks")
                if not isinstance(dead_blocks, list):
                    continue
                for block in dead_blocks:
                    if not isinstance(block, dict):
                        continue
                    reason = str(block.get("reason", "unknown"))
                    message = f"Dead code in '{fn_name}': {reason}"
                    issues.append(
                        Issue(
                            type=IssueType.DEAD_CODE,
                            severity=Priority.MEDIUM,
                            message=message,
                            file_path=file_path or None,
                            line_number=start_line,
                            stage="dead_code",
                            details=[
                                f"function: {fn_name}",
                                f"reason: {reason}",
                            ],
                        )
                    )
        logger.debug(f"pyscn dead_code: {len(issues)} issues")
        return issues

    def _parse_pyscn_function(self, item: object) -> Issue | None:
        if not isinstance(item, dict):
            return None
        fn = t.cast("dict[str, t.Any]", item)
        name = str(fn.get("Name", "<unknown>"))
        file_path = str(fn.get("FilePath", ""))
        line_number = fn.get("StartLine")
        if not isinstance(line_number, int):
            line_number = None
        metrics = fn.get("Metrics")
        if not isinstance(metrics, dict):
            return None
        complexity = metrics.get("Complexity")
        if not isinstance(complexity, int):
            return None
        if complexity <= self.max_complexity:
            return None
        message = f"Function '{name}' has cyclomatic complexity {complexity}"
        return Issue(
            type=IssueType.COMPLEXITY,
            severity=self._severity(complexity),
            message=message,
            file_path=file_path or None,
            line_number=line_number,
            stage="complexity",
            details=[
                f"function: {name}",
                f"complexity: {complexity} (threshold: >{self.max_complexity})",
                f"risk_level: {fn.get('RiskLevel', 'unknown')}",
            ],
        )

    def _severity(self, complexity: int) -> Priority:
        if complexity > self.max_complexity * 2:
            return Priority.HIGH
        if complexity > self.max_complexity:
            return Priority.MEDIUM
        return Priority.LOW


class SemgrepJSONParser(JSONParser):
    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        if not isinstance(data, dict):
            logger.warning(f"Semgrep JSON data is not a dict: {type(data)}")
            return []
        results = data.get("results")
        if not isinstance(results, list):
            logger.warning("Semgrep JSON 'results' field is not a list")
            return []
        issues: list[Issue] = []
        for item in results:
            try:
                issue = self._parse_semgrep_item(item)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.error(f"Error parsing semgrep JSON item: {e}", exc_info=True)
        logger.info(f"Parsed {len(issues)} issues from semgrep JSON output")
        return issues

    def _parse_semgrep_item(self, item: object) -> Issue | None:
        if not isinstance(item, dict):
            logger.warning(f"Skipping non-dict item in semgrep results: {type(item)}")
            return None
        path = str(item.get("path", ""))
        if not path:
            logger.warning("Skipping semgrep item without path")
            return None
        line_number = self._extract_line_number_from_start(item.get("start"))
        extra = self._get_extra_data(item)
        message = str(extra.get("message", "Security issue detected"))
        check_id = str(item.get("check_id", "UNKNOWN"))
        severity_str = str(extra.get("severity", "WARNING"))
        return Issue(
            type=IssueType.SECURITY,
            severity=self._map_severity(severity_str),
            message=f"{check_id}: {message}",
            file_path=path,
            line_number=line_number,
            stage="semgrep",
            details=[f"check_id: {check_id}", f"severity: {severity_str}"],
        )

    def _extract_line_number_from_start(self, start: object | None) -> int | None:
        if not isinstance(start, dict):
            return None
        line_number = start.get("line")
        return int(line_number) if isinstance(line_number, int) else None

    def _get_extra_data(self, item: dict) -> dict:
        if not isinstance(item, dict):
            return {}
        extra = item.get("extra", {})
        return extra if isinstance(extra, dict) else {}

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            return len(results) if isinstance(results, list) else 0
        return 0

    def _map_severity(self, severity_str: str) -> Priority:
        mapping = {
            "ERROR": Priority.CRITICAL,
            "WARNING": Priority.HIGH,
            "INFO": Priority.MEDIUM,
        }
        return mapping.get(severity_str.upper(), Priority.MEDIUM)


class PipAuditJSONParser(JSONParser):
    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        if not isinstance(data, dict):
            logger.warning(f"pip-audit JSON data is not a dict: {type(data)}")
            return []
        dependencies = data.get("dependencies")
        if not isinstance(dependencies, list):
            logger.warning("pip-audit JSON 'dependencies' field is not a list")
            return []
        issues: list[Issue] = []
        for dep in dependencies:
            try:
                dep_issues = self._parse_dependency(dep)
                issues.extend(dep_issues)
            except Exception as e:
                logger.error(f"Error parsing pip-audit JSON item: {e}", exc_info=True)
        logger.info(f"Parsed {len(issues)} issues from pip-audit JSON output")
        return issues

    def _parse_dependency(self, dep: object) -> list[Issue]:
        if not isinstance(dep, dict):
            logger.warning(
                f"Skipping non-dict item in pip-audit dependencies: {type(dep)}"
            )
            return []
        name = str(dep.get("name", "UNKNOWN"))
        vulns = dep.get("vulns", [])
        if not isinstance(vulns, list):
            logger.warning(f"Vulnerabilities for {name} is not a list")
            return []
        return [
            self._create_vulnerability_issue(name, vuln)
            for vuln in vulns
            if isinstance(vuln, dict)
        ]

    def _create_vulnerability_issue(self, package_name: str, vuln: dict) -> Issue:
        vuln_id = str(vuln.get("id", "UNKNOWN"))
        description = str(vuln.get("description", "No description"))
        severity_str = str(vuln.get("severity", "MEDIUM"))
        return Issue(
            type=IssueType.SECURITY,
            severity=self._map_severity(severity_str),
            message=f"{vuln_id}: {description}",
            file_path=None,
            line_number=None,
            stage="pip-audit",
            details=[
                f"package: {package_name}",
                f"vulnerability_id: {vuln_id}",
                f"severity: {severity_str}",
            ],
        )

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        dependencies = self._get_dependencies_list(data)
        if not dependencies:
            return 0
        return sum(self._count_vulnerabilities_in_dep(dep) for dep in dependencies)

    def _get_dependencies_list(
        self, data: dict[str, object] | list[object]
    ) -> list[object] | None:
        if isinstance(data, dict) and "dependencies" in data:
            dependencies = data["dependencies"]
            if not isinstance(dependencies, list):
                return None
            return t.cast("list[object]", dependencies)
        return None

    def _count_vulnerabilities_in_dep(self, dep: object) -> int:
        if isinstance(dep, dict):
            vulns = dep.get("vulns")
            if isinstance(vulns, list):
                return len(vulns)
        return 0

    def _map_severity(self, severity_str: str) -> Priority:
        mapping = {
            "CRITICAL": Priority.CRITICAL,
            "HIGH": Priority.CRITICAL,
            "MEDIUM": Priority.HIGH,
            "LOW": Priority.MEDIUM,
        }
        return mapping.get(severity_str.upper(), Priority.MEDIUM)


class GitleaksJSONParser(JSONParser):
    REPORT_PATH = Path(".cache/gitleaks-report.json")

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        data = self._extract_json_from_output(output)
        if data is not None:
            return self.parse_json(data)
        logger.debug("No gitleaks JSON found in output (may be clean)")
        return []

    def _extract_json_from_output(
        self, output: str
    ) -> dict[str, object] | list[object] | None:

        if not output.strip():
            return None

        if self.REPORT_PATH.exists():
            try:
                report_text = self.REPORT_PATH.read_text(encoding="utf-8")
                if report_text.strip():
                    data = json.loads(report_text)
                    return data
            except (OSError, json.JSONDecodeError):
                pass

        import re

        stripped = output.strip()
        if stripped.startswith(("[", "{")):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
        json_pattern = "\\[[\\s\\S]*?\\](?=\\s*$|\\s*[^\\]\\s])"
        matches = re.findall(json_pattern, output)
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                continue
        if "[]" in output or "no leaks found" in output.lower():
            return []
        return None

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        issues: list[Issue] = []
        if isinstance(data, dict):
            if "findings" in data:
                data = t.cast("list[object]", data["findings"])
            else:
                data = [data]
        if not isinstance(data, list):
            logger.warning(f"Gitleaks JSON data is not a list: {type(data)}")
            return issues
        for item in data:
            try:
                if not isinstance(item, dict):
                    logger.warning(
                        f"Skipping non-dict item in gitleaks output: {type(item)}"
                    )
                    continue
                description = str(item.get("Description", "Secret detected"))
                file_path = str(item.get("File", ""))
                line_number = item.get("StartLine")
                if isinstance(line_number, int):
                    line_number = int(line_number)
                else:
                    line_number = None
                rule_id = str(item.get("RuleID", "UNKNOWN"))
                severity_str = str(item.get("Severity", "MEDIUM"))
                severity = self._map_severity(severity_str)
                message = f"{rule_id}: {description}"
                issues.append(
                    Issue(
                        type=IssueType.SECURITY,
                        severity=severity,
                        message=message,
                        file_path=file_path,
                        line_number=line_number,
                        stage="gitleaks",
                        details=[
                            f"rule_id: {rule_id}",
                            f"severity: {severity_str}",
                            f"secret_type: {description}",
                        ],
                    )
                )
            except Exception as e:
                logger.error(f"Error parsing gitleaks JSON item: {e}", exc_info=True)
        logger.info(f"Parsed {len(issues)} issues from gitleaks JSON output")
        return issues

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        if isinstance(data, list):
            return len(data)
        return 0

    def _map_severity(self, severity_str: str) -> Priority:
        mapping = {
            "CRITICAL": Priority.CRITICAL,
            "HIGH": Priority.CRITICAL,
            "MEDIUM": Priority.HIGH,
            "LOW": Priority.MEDIUM,
        }
        return mapping.get(severity_str.upper(), Priority.MEDIUM)


class BetterleaksJSONParser(GitleaksJSONParser):
    REPORT_PATH = Path(".cache/betterleaks-report.json")

    def parse(self, output: str, tool_name: str) -> list[Issue]:

        if self.REPORT_PATH.exists():
            try:
                report_text = self.REPORT_PATH.read_text(encoding="utf-8")
                stripped_report = report_text.strip()
                if stripped_report and stripped_report != "null":
                    data = json.loads(report_text)
                    if data is not None:
                        return self.parse_json(data)
            except (OSError, json.JSONDecodeError):
                pass

        if not output.strip():
            return []

        stripped = output.strip()

        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return []
        if data is None:
            return []
        return self.parse_json(data)


class PytestJSONParser(JSONParser):
    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        if not isinstance(data, dict):
            logger.warning(f"Pytest JSON data is not a dict: {type(data)}")
            return []
        parser = TestResultParser()
        json_str = json.dumps(data)
        failures = parser.parse_json_output(json_str)
        issues = []
        for failure in failures:
            try:
                issues.append(failure.to_issue())
            except Exception as e:
                logger.error(f"Error converting test failure to issue: {e}")
        logger.info(f"Parsed {len(issues)} test failures from pytest JSON output")
        return issues

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        if isinstance(data, dict) and "tests" in data:
            tests = data["tests"]
            if isinstance(tests, list):
                failed = [
                    t
                    for t in tests
                    if isinstance(t, dict) and t.get("outcome") == "failed"
                ]
                return len(failed)
        return 0


class LycheeJSONParser(JSONParser):
    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        if not isinstance(data, dict):
            logger.warning(f"Lychee JSON data is not a dict: {type(data)}")
            return []
        errors = data.get("errors", 0)
        if errors == 0:
            logger.info("Lychee found no broken links")
            return []
        error_map = t.cast("dict[str, list[object]]", data.get("error_map", {}))
        if not isinstance(error_map, dict):
            logger.warning("Lychee 'error_map' is not a dict")
            return []
        issues: list[Issue] = []
        for file_path, file_errors in error_map.items():
            if not isinstance(file_errors, list):
                continue
            for error_entry in file_errors:
                try:
                    issue = self._parse_lychee_error(file_path, error_entry)
                    if issue:
                        issues.append(issue)
                except Exception as e:
                    logger.error(f"Error parsing lychee error entry: {e}")
        logger.info(f"Parsed {len(issues)} issues from lychee JSON output")
        return issues

    def _parse_lychee_error(self, file_path: str, error_entry: object) -> Issue | None:
        if not isinstance(error_entry, dict):
            return None
        url = str(error_entry.get("url", ""))
        status = error_entry.get("status")
        if not isinstance(status, dict):
            return None
        error_text = str(status.get("text", "Unknown error"))
        span = error_entry.get("span")
        line_number = None
        if isinstance(span, dict):
            line = span.get("line")
            if isinstance(line, int):
                line_number = line
        message = (
            f"Broken link: {url} - {error_text}"
            if url != "error:"
            else f"Link error: {error_text}"
        )
        severity = self._get_severity(error_text)
        return Issue(
            type=IssueType.DOCUMENTATION,
            severity=severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
            stage="lychee",
            details=[
                f"url: {url}",
                f"error: {error_text}",
            ],
        )

    def _get_severity(self, error_message: str) -> Priority:
        error_lower = error_message.lower()
        if any(code in error_message for code in ("404", "410", "403", "401")):
            return Priority.HIGH
        if "network" in error_lower or "timeout" in error_lower:
            return Priority.MEDIUM
        if any(code in error_message for code in ("500", "502", "503", "504")):
            return Priority.LOW
        return Priority.MEDIUM

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        if isinstance(data, dict):
            errors = data.get("errors", 0)
            if isinstance(errors, int):
                return errors
            if isinstance(errors, (float, str)) and errors:
                return int(errors)
        return 0


class CheckJSONSchemaJSONParser(JSONParser):
    def parse(self, output: str, tool_name: str) -> list[Issue]:
        if not output.strip():
            return []
        issues: list[Issue] = []
        seen: set[tuple[str, str, str]] = set()
        for frame in self._iter_frames(output):
            issues.extend(self._parse_frame(frame, seen))
        logger.info(f"Parsed {len(issues)} issues from check-jsonschema JSON output")
        return issues

    def _iter_frames(self, output: str) -> t.Iterator[dict[str, object]]:
        decoder = json.JSONDecoder()
        idx = 0
        text = output
        n = len(text)
        while idx < n:
            while idx < n and text[idx] in " \t\r\n":
                idx += 1
            if idx >= n:
                break
            try:
                obj, end = decoder.raw_decode(text, idx)
            except json.JSONDecodeError:
                break
            if isinstance(obj, dict):
                yield t.cast("dict[str, object]", obj)
            idx = end

    def _parse_frame(
        self,
        frame: dict[str, object],
        seen: set[tuple[str, str, str]],
    ) -> list[Issue]:
        success = frame.get("success", True)
        if success:
            return []
        raw_errors = frame.get("errors")
        if not isinstance(raw_errors, list):
            return []

        file_path = self._extract_frame_file(frame)
        issues: list[Issue] = []
        for entry in raw_errors:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path", "") or "")
            message = str(entry.get("message", "Schema validation error"))
            validator = str(entry.get("validator", "schema") or "schema")
            dedup_key = (file_path, path, message)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            issues.append(
                Issue(
                    type=IssueType.FORMATTING,
                    severity=Priority.MEDIUM,
                    message=f"{validator}: {message}",
                    file_path=file_path,
                    line_number=None,
                    stage="check-jsonschema",
                    details=[
                        f"validator: {validator}",
                        f"json_path: {path or '<root>'}",
                    ],
                )
            )
        return issues

    def _extract_frame_file(self, frame: dict[str, object]) -> str:
        files = frame.get("files")
        if isinstance(files, list) and files:
            first = files[0]
            if isinstance(first, dict):
                return str(first.get("path", "unknown"))
        return "unknown"

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:

        seen: set[tuple[str, str, str]] = set()
        if isinstance(data, dict):
            return self._parse_frame(data, seen)
        return []

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        if not isinstance(data, dict):
            return 0
        raw_errors = data.get("errors")
        if isinstance(raw_errors, list):
            return len(raw_errors)
        return 0


def register_json_parsers(factory: ParserFactory) -> None:
    factory.register_json_parser("ruff", RuffJSONParser)
    factory.register_json_parser("ruff-check", RuffJSONParser)
    factory.register_json_parser("mypy", MypyJSONParser)
    factory.register_json_parser("bandit", BanditJSONParser)
    factory.register_json_parser("complexipy", ComplexipyJSONParser)
    factory.register_json_parser("pyscn", PyscnJSONParser)
    factory.register_json_parser("semgrep", SemgrepJSONParser)
    factory.register_json_parser("pip-audit", PipAuditJSONParser)
    factory.register_json_parser("gitleaks", GitleaksJSONParser)
    factory.register_json_parser("pytest", PytestJSONParser)
    factory.register_json_parser("lychee", LycheeJSONParser)

    factory.register_json_parser("betterleaks", BetterleaksJSONParser)
    factory.register_json_parser("check-jsonschema", CheckJSONSchemaJSONParser)
    logger.info(
        "Registered JSON parsers: ruff, mypy, bandit, complexipy, pyscn, "
        "semgrep, pip-audit, gitleaks, betterleaks, pytest, lychee, "
        "check-jsonschema"
    )
