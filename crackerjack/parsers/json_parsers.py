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
                if not isinstance(item, dict):
                    logger.warning(
                        f"Skipping non-dict item in ruff output: {type(item)}"
                    )
                    continue

                required_fields = ["filename", "location", "code", "message"]
                if not all(k in item for k in required_fields):
                    missing = required_fields - item.keys()
                    logger.warning(
                        f"Skipping ruff item missing required fields {missing}: {item}"
                    )
                    continue

                file_path = str(item["filename"])
                location = item["location"]
                if not isinstance(location, dict):
                    logger.warning(
                        f"Invalid location format in ruff output: {location}"
                    )
                    continue

                line_number = location.get("row")
                if isinstance(line_number, int):
                    line_number = int(line_number)
                else:
                    line_number = None

                code = str(item["code"])
                message = str(item["message"])

                issue_type = self._get_issue_type(code)
                severity = self._get_severity(code)

                details = [f"code: {code}"]
                if "fix" in item:
                    details.append("fixable: True")
                else:
                    details.append("fixable: False")

                if "url" in item:
                    details.append(f"url: {item['url']}")

                issues.append(
                    Issue(
                        type=issue_type,
                        severity=severity,
                        message=f"{code} {message}",
                        file_path=file_path,
                        line_number=line_number,
                        stage="ruff-check",
                        details=details,
                    )
                )
            except Exception as e:
                logger.error(f"Error parsing ruff JSON item: {e}", exc_info=True)

        logger.info(f"Parsed {len(issues)} issues from ruff JSON output")
        return issues

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
                if not isinstance(item, dict):
                    logger.warning(
                        f"Skipping non-dict item in mypy output: {type(item)}"
                    )
                    continue

                required_fields = ["file", "line", "message"]
                if not all(k in item for k in required_fields):
                    missing = required_fields - item.keys()
                    logger.warning(
                        f"Skipping mypy item missing required fields {missing}: {item}"
                    )
                    continue

                file_path = str(item["file"])
                line_number = item.get("line")
                if isinstance(line_number, int):
                    line_number = int(line_number)
                else:
                    line_number = None

                message = str(item["message"])
                severity_str = str(item.get("severity", "error"))

                severity = Priority.HIGH if severity_str == "error" else Priority.MEDIUM

                issues.append(
                    Issue(
                        type=IssueType.TYPE_ERROR,
                        severity=severity,
                        message=message,
                        file_path=file_path,
                        line_number=line_number,
                        stage="mypy",
                        details=[f"severity: {severity_str}"],
                    )
                )
            except Exception as e:
                logger.error(f"Error parsing mypy JSON item: {e}", exc_info=True)

        logger.info(f"Parsed {len(issues)} issues from mypy JSON output")
        return issues

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
        import ast
        import os

        if file_path in self._line_number_cache:
            if function_name in self._line_number_cache[file_path]:
                return self._line_number_cache[file_path][function_name]

        if not os.path.exists(file_path):
            logger.debug(f"File not found for line number extraction: {file_path}")
            return None

        if not file_path.endswith(".py"):
            logger.debug(f"Not a Python file, skipping AST extraction: {file_path}")
            return None

        if file_path not in self._line_number_cache:
            self._line_number_cache[file_path] = {}

        search_names = [function_name]
        if "::" in function_name:
            method_name = function_name.split("::")[-1]
            search_names.insert(0, method_name)

        try:
            with open(file_path) as f:
                content = f.read()

            tree = ast.parse(content)

            for search_name in search_names:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name == search_name:
                            line_number = node.lineno

                            self._line_number_cache[file_path][function_name] = (
                                line_number
                            )
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

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        import os
        import re

        match = re.search(r"Results saved at\s+(.+?\.json)", output)
        if not match:
            logger.warning("Could not find complexipy JSON file path in output")
            return []

        json_path = match.group(1).strip()

        if not os.path.exists(json_path):
            logger.warning(f"Complexipy JSON file not found: {json_path}")
            return []

        try:
            with open(json_path) as f:
                json_content = f.read()
            data = json.loads(json_content)

            logger.debug(
                f"Read complexipy JSON file: {json_path} ({len(data) if isinstance(data, list) else 'N/A'} entries)"
            )
        except Exception as e:
            logger.error(f"Error reading/parsing complexipy JSON file: {e}")
            return []

        return self.parse_json(data)

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        issues: list[Issue] = []

        if not isinstance(data, list):
            logger.warning(f"Complexipy JSON data is not a list: {type(data)}")
            return issues

        for item in data:
            try:
                if not isinstance(item, dict):
                    logger.warning(
                        f"Skipping non-dict item in complexipy output: {type(item)}"
                    )
                    continue

                required_fields = ["complexity", "file_name", "function_name", "path"]
                if not all(k in item for k in required_fields):
                    missing = required_fields - item.keys()
                    logger.warning(
                        f"Skipping complexipy item missing required fields {missing}: {item}"
                    )
                    continue

                complexity = item["complexity"]
                if not isinstance(complexity, int):
                    logger.warning(
                        f"Skipping invalid complexity value: {complexity} (type: {type(complexity)})"
                    )
                    continue

                if complexity <= self.max_complexity:
                    logger.debug(
                        f"Skipping function with complexity {complexity} <= threshold {self.max_complexity}"
                    )
                    continue

                file_path = str(item["path"])
                function_name = str(item["function_name"])

                line_number = self._extract_line_number_tier1(file_path, function_name)

                if complexity > self.max_complexity * 2:
                    severity = Priority.HIGH
                elif complexity > self.max_complexity:
                    severity = Priority.MEDIUM
                else:
                    severity = Priority.LOW

                message = f"Function '{function_name}' has complexity {complexity}"

                details = [
                    f"complexity: {complexity}",
                    f"function: {function_name}",
                    f"threshold: >{self.max_complexity}",
                ]
                if line_number:
                    details.append(f"line_number: {line_number} (extracted via AST)")
                else:
                    details.append(
                        "line_number: None (agent will search by function name)"
                    )

                issues.append(
                    Issue(
                        type=IssueType.COMPLEXITY,
                        severity=severity,
                        message=message,
                        file_path=file_path,
                        line_number=line_number,
                        stage="complexity",
                        details=details,
                    )
                )
            except Exception as e:
                logger.error(f"Error parsing complexipy JSON item: {e}", exc_info=True)

        logger.info(
            f"Parsed {len(issues)} issues from complexipy JSON output "
            f"(filtered from {len(data)} total functions, threshold: >{self.max_complexity})"
        )
        return issues

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
        issues: list[Issue] = []

        if not isinstance(data, dict):
            logger.warning(f"Semgrep JSON data is not a dict: {type(data)}")
            return issues

        results = data.get("results")
        if not isinstance(results, list):
            logger.warning("Semgrep JSON 'results' field is not a list")
            return issues

        for item in results:
            try:
                if not isinstance(item, dict):
                    logger.warning(
                        f"Skipping non-dict item in semgrep results: {type(item)}"
                    )
                    continue

                path = str(item.get("path", ""))
                if not path:
                    logger.warning("Skipping semgrep item without path")
                    continue

                start = item.get("start")
                if isinstance(start, dict):
                    line_number = start.get("line")
                    if isinstance(line_number, int):
                        line_number = int(line_number)
                    else:
                        line_number = None
                else:
                    line_number = None

                extra = item.get("extra", {})
                if not isinstance(extra, dict):
                    extra = {}

                message = str(extra.get("message", "Security issue detected"))
                check_id = str(item.get("check_id", "UNKNOWN"))
                severity_str = str(extra.get("severity", "WARNING"))

                severity = self._map_severity(severity_str)

                issues.append(
                    Issue(
                        type=IssueType.SECURITY,
                        severity=severity,
                        message=f"{check_id}: {message}",
                        file_path=path,
                        line_number=line_number,
                        stage="semgrep",
                        details=[f"check_id: {check_id}", f"severity: {severity_str}"],
                    )
                )
            except Exception as e:
                logger.error(f"Error parsing semgrep JSON item: {e}", exc_info=True)

        logger.info(f"Parsed {len(issues)} issues from semgrep JSON output")
        return issues

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
        issues: list[Issue] = []

        if not isinstance(data, dict):
            logger.warning(f"pip-audit JSON data is not a dict: {type(data)}")
            return issues

        dependencies = data.get("dependencies")
        if not isinstance(dependencies, list):
            logger.warning("pip-audit JSON 'dependencies' field is not a list")
            return issues

        for dep in dependencies:
            try:
                if not isinstance(dep, dict):
                    logger.warning(
                        f"Skipping non-dict item in pip-audit dependencies: {type(dep)}"
                    )
                    continue

                name = str(dep.get("name", "UNKNOWN"))
                vulns = dep.get("vulns", [])

                if not isinstance(vulns, list):
                    logger.warning(f"Vulnerabilities for {name} is not a list")
                    continue

                for vuln in vulns:
                    if not isinstance(vuln, dict):
                        continue

                    vuln_id = str(vuln.get("id", "UNKNOWN"))
                    description = str(vuln.get("description", "No description"))
                    severity_str = str(vuln.get("severity", "MEDIUM"))

                    severity = self._map_severity(severity_str)

                    message = f"{vuln_id}: {description}"

                    issues.append(
                        Issue(
                            type=IssueType.SECURITY,
                            severity=severity,
                            message=message,
                            file_path=None,
                            line_number=None,
                            stage="pip-audit",
                            details=[
                                f"package: {name}",
                                f"vulnerability_id: {vuln_id}",
                                f"severity: {severity_str}",
                            ],
                        )
                    )
            except Exception as e:
                logger.error(f"Error parsing pip-audit JSON item: {e}", exc_info=True)

        logger.info(f"Parsed {len(issues)} issues from pip-audit JSON output")
        return issues

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        if isinstance(data, dict) and "dependencies" in data:
            dependencies = data["dependencies"]
            if isinstance(dependencies, list):
                total = 0
                for dep in dependencies:
                    if isinstance(dep, dict):
                        vulns = dep.get("vulns")
                        if isinstance(vulns, list):
                            total += len(vulns)
                return total
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
        import os

        json_path = "/tmp/gitleaks-report.json"

        if not os.path.exists(json_path):
            logger.debug(
                f"Gitleaks JSON file not found: {json_path} (may be no leaks found)"
            )
            return []

        try:
            with open(json_path) as f:
                json_content = f.read()
            data = json.loads(json_content)

            try:
                os.remove(json_path)
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
