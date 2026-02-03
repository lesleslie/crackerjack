import json
import logging

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.base import JSONParser
from crackerjack.parsers.factory import ParserFactory

logger = logging.getLogger(__name__)


class RuffJSONParser(JSONParser):
    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
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

        required_fields = ["filename", "location", "code", "message"]
        if not all(k in item for k in required_fields):
            missing = required_fields - item.keys()
            logger.warning(
                f"Skipping ruff item missing required fields {missing}: {item}"
            )
            return None

        file_path = str(item["filename"])
        line_number = self._extract_line_number_from_location(item.get("location"))
        if line_number is None and "location" in item:
            logger.warning(
                f"Invalid location format in ruff output: {item['location']}"
            )
            return None

        code = str(item["code"])
        message = str(item["message"])

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
        if code.startswith("C9"):
            return IssueType.COMPLEXITY
        if code.startswith("S"):
            return IssueType.SECURITY
        if code.startswith("F4"):
            return IssueType.IMPORT_ERROR
        if code.startswith("F"):
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

                required_fields = ["filename", "issue_text", "line_number"]
                if not all(k in item for k in required_fields):
                    missing = required_fields - item.keys()
                    logger.warning(
                        f"Skipping bandit item missing required fields {missing}: {item}"
                    )
                    continue

                file_path = str(item["filename"])
                line_number = item.get("line_number")
                if isinstance(line_number, int):
                    line_number = int(line_number)
                else:
                    line_number = None

                message = str(item["issue_text"])
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

        if not Path(file_path).exists():
            logger.debug(f"File not found for line number extraction: {file_path}")
            return False

        if not file_path.endswith(".py"):
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

        try:
            content = Path(file_path).read_text()
                # Removed

            tree = ast.parse(content)

            for search_name in search_names:
                if line_number := self._find_function_in_ast(tree, search_name):
                    self._line_number_cache[file_path][function_name] = line_number
                    logger.debug(
                        f"Found line number for '{function_name}' (searched as '{search_name}') "
                        f"in {file_path}: {line_number}"
                    )
                    return line_number

            logger.debug(
                f"Function '{function_name}' not found in {file_path} "
                f"(searched for: {search_names})"
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

    def _find_function_in_ast(self, tree: object, search_name: str) -> int | None:
        import ast

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == search_name:
                    return node.lineno
        return None

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        from pathlib import Path
        import re

        match = re.search(r"Results saved at\s+(.+?\.json)", output)
        if not match:
            logger.warning("Could not find complexipy JSON file path in output")
            return []

        json_path = match.group(1).strip()

        if not Path(json_path).exists():
            logger.warning(f"Complexipy JSON file not found: {json_path}")
            return []

        try:
            json_content = Path(json_path).read_text()
                # Removed
            data = json.loads(json_content)

            logger.debug(
                f"Read complexipy JSON file: {json_path} ({len(data) if isinstance(data, list) else 'N/A'} entries)"
            )
        except Exception as e:
            logger.error(f"Error reading/parsing complexipy JSON file: {e}")
            return []

        return self.parse_json(data)

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
            f"Parsed {len(issues)} issues from complexipy JSON output "
            f"(filtered from {len(data)} total functions, threshold: >{self.max_complexity})"
        )
        return issues

    def _parse_complexipy_item(self, item: object) -> Issue | None:
        if not isinstance(item, dict):
            logger.warning(f"Skipping non-dict item in complexipy output: {type(item)}")
            return None

        required_fields = ["complexity", "file_name", "function_name", "path"]
        if not all(k in item for k in required_fields):
            missing = required_fields - item.keys()
            logger.warning(
                f"Skipping complexipy item missing required fields {missing}: {item}"
            )
            return None

        complexity = item["complexity"]
        if not self._validate_complexity_value(complexity):
            return None

        if not self._is_complexity_above_threshold(complexity):
            return None

        return self._create_complexipy_issue(item, complexity)

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
                and item["complexity"] > self.max_complexity
            )
        return 0


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
            return dependencies if isinstance(dependencies, list) else None
        return None

    def _count_vulnerabilities_in_dep(self, dep: object) -> int:
        if isinstance(dep, dict):
            vulns = dep.get("vulns")
            if isinstance(vulns, list):
                return len(vulns)
        return 0

    def _map_severity(self, severity_str: str) -> Priority:
        mapping = {
            "HIGH": Priority.CRITICAL,
            "MEDIUM": Priority.HIGH,
            "LOW": Priority.MEDIUM,
        }
        return mapping.get(severity_str.upper(), Priority.MEDIUM)


class GitleaksJSONParser(JSONParser):
    def parse(self, output: str, tool_name: str) -> list[Issue]:
        from pathlib import Path

        json_path = "/tmp/gitleaks-report.json"

        if not Path(json_path).exists():
            logger.debug(
                f"Gitleaks JSON file not found: {json_path} (may be no leaks found)"
            )
            return []

        try:
            json_content = Path(json_path).read_text()
                # Removed
            data = json.loads(json_content)

            try:
                Path(json_path).unlink()
                logger.debug(f"Cleaned up gitleaks JSON file: {json_path}")
            except Exception as e:
                logger.warning(f"Failed to remove gitleaks JSON file {json_path}: {e}")
        except Exception as e:
            logger.error(f"Error reading/parsing gitleaks JSON file: {e}")
            return []

        return self.parse_json(data)

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        issues: list[Issue] = []

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
            "HIGH": Priority.CRITICAL,
            "MEDIUM": Priority.HIGH,
            "LOW": Priority.MEDIUM,
        }
        return mapping.get(severity_str.upper(), Priority.MEDIUM)


def register_json_parsers(factory: ParserFactory) -> None:
    factory.register_json_parser("ruff", RuffJSONParser)
    factory.register_json_parser("ruff-check", RuffJSONParser)
    factory.register_json_parser("mypy", MypyJSONParser)
    factory.register_json_parser("bandit", BanditJSONParser)
    factory.register_json_parser("complexipy", ComplexipyJSONParser)
    factory.register_json_parser("semgrep", SemgrepJSONParser)
    factory.register_json_parser("pip-audit", PipAuditJSONParser)
    factory.register_json_parser("gitleaks", GitleaksJSONParser)
    logger.info(
        "Registered JSON parsers: ruff, mypy, bandit, complexipy, semgrep, pip-audit, gitleaks"
    )
