"""JSON-based parsers for quality tools.

This module implements JSON parsers for tools that support structured output.
These parsers are more reliable than regex-based parsers because they work
with structured data that's part of the tool's API contract.
"""

import json
import logging

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.base import JSONParser
from crackerjack.parsers.factory import ParserFactory

logger = logging.getLogger(__name__)


class RuffJSONParser(JSONParser):
    """Parse ruff JSON output.

    Ruff JSON format documentation:
    https://docs.astral.sh/ruff/settings/#output_format

    Example output:
    [
        {
            "filename": "path/to/file.py",
            "location": {"row": 10, "column": 5},
            "end_location": {"row": 10, "column": 42},
            "code": "UP017",
            "message": "Use `datetime.UTC` alias",
            "fix": {"applicability": "automatic", "edits": [...]},
            "url": "https://docs.astral.sh/ruff/rules/upcase-datetime-alias",
            "parent": null
        }
    ]
    """

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        """Parse ruff JSON output into Issue objects.

        Args:
            data: Parsed JSON data (should be a list of issue objects)

        Returns:
            List of Issue objects

        Raises:
            TypeError: If data is not a list
            KeyError: If required fields are missing from issue objects
        """
        if not isinstance(data, list):
            logger.warning(f"Expected list from ruff, got {type(data)}")
            return []

        issues: list[Issue] = []

        for item in data:
            try:
                # Validate required fields
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

                # Build details list
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
        """Get issue count from ruff JSON data.

        Args:
            data: Parsed JSON data

        Returns:
            Number of issues in the data
        """
        return len(data) if isinstance(data, list) else 0

    def _get_issue_type(self, code: str) -> IssueType:
        """Map ruff error code to IssueType.

        Args:
            code: Ruff error code (e.g., "UP017", "C901")

        Returns:
            Corresponding IssueType
        """
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
        """Map ruff error code to Priority level.

        Args:
            code: Ruff error code

        Returns:
            Corresponding Priority level
        """
        if code.startswith(("C9", "S")):
            return Priority.HIGH
        if code.startswith("F4"):
            return Priority.MEDIUM
        return Priority.LOW


class MypyJSONParser(JSONParser):
    """Parse mypy JSON output.

    Mypy JSON format documentation:
    http://mypy-lang.readthedocs.io/en/stable/command_line.html#output-format

    Example output:
    [
        {
            "file": "path/to/file.py",
            "line": 10,
            "column": 5,
            "message": "Incompatible return value type",
            "severity": "error",
            "code": "error"
        }
    ]
    """

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        """Parse mypy JSON output into Issue objects.

        Args:
            data: Parsed JSON data (should be a list of issue objects)

        Returns:
            List of Issue objects
        """
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

                # Validate required fields
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
        """Get issue count from mypy JSON data.

        Args:
            data: Parsed JSON data

        Returns:
            Number of issues in the data
        """
        return len(data) if isinstance(data, list) else 0


class BanditJSONParser(JSONParser):
    """Parse bandit JSON output.

    Bandit JSON format documentation:
    https://bandit.readthedocs.io/en/latest/formatter.html#json-formatter

    Example output:
    {
        "metrics": {...},
        "results": [
            {
                "filename": "path/to/file.py",
                "line_number": 42,
                "issue_text": "Description of security issue",
                "issue_severity": "HIGH",
                "test_id": "B201",
                "test_name": "flask_debug_true"
            }
        ],
        "generated_at": "2025-01-29T12:34:56Z"
    }
    """

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        """Parse bandit JSON output into Issue objects.

        Args:
            data: Parsed JSON data (should be a dict with 'results' key)

        Returns:
            List of Issue objects
        """
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

                # Validate required fields
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
        """Get issue count from bandit JSON data.

        Args:
            data: Parsed JSON data

        Returns:
            Number of issues in the data
        """
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            return len(results) if isinstance(results, list) else 0
        return 0

    def _map_severity(self, severity_str: str) -> Priority:
        """Map bandit severity string to Priority enum.

        Args:
            severity_str: Bandit severity string (HIGH, MEDIUM, LOW)

        Returns:
            Corresponding Priority value
        """
        mapping = {
            "HIGH": Priority.CRITICAL,
            "MEDIUM": Priority.HIGH,
            "LOW": Priority.MEDIUM,
        }
        return mapping.get(severity_str.upper(), Priority.MEDIUM)


class ComplexipyJSONParser(JSONParser):
    """Parse complexipy JSON output.

    Complexipy saves JSON to a file and prints text output to stdout.
    The stdout contains the file path like:
        Results saved at
        /path/to/complexipy_results_YYYY_MM_DD__HH-MM-SS.json

    Example JSON content:
        [
            {
                "complexity": 20,
                "file_name": "example.py",
                "function_name": "my_function",
                "path": "path/to/example.py"
            }
        ]
    """

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        """Parse complexipy output by extracting JSON file path and reading it.

        Args:
            output: Raw text output from complexipy (contains file path)
            tool_name: Name of the tool (for logging, currently unused)

        Returns:
            List of Issue objects for functions exceeding complexity threshold
        """
        import os
        import re

        # Extract file path from output
        match = re.search(r"Results saved at\s+(.+?\.json)", output)
        if not match:
            logger.warning("Could not find complexipy JSON file path in output")
            return []

        json_path = match.group(1).strip()

        # Read JSON from file
        if not os.path.exists(json_path):
            logger.warning(f"Complexipy JSON file not found: {json_path}")
            return []

        try:
            with open(json_path) as f:
                json_content = f.read()
            data = json.loads(json_content)

            # Clean up the temporary JSON file immediately after reading
            try:
                os.remove(json_path)
                logger.debug(f"Cleaned up complexipy JSON file: {json_path}")
            except Exception as e:
                logger.warning(
                    f"Failed to remove complexipy JSON file {json_path}: {e}"
                )
        except Exception as e:
            logger.error(f"Error reading/parsing complexipy JSON file: {e}")
            return []

        # Parse the JSON data
        return self.parse_json(data)

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        """Parse complexipy JSON data.

        Note: This parser returns ALL functions from complexipy output without filtering.
        The ComplexipyAdapter is responsible for filtering by max_complexity threshold.
        This separation ensures the parser is stateless and the adapter handles config.

        Args:
            data: Parsed JSON data from complexipy

        Returns:
            List of Issue objects for all functions (no threshold filtering)
        """
        issues: list[Issue] = []

        # complexipy outputs a list directly
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

                # Validate required fields
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

                file_path = str(item["path"])
                function_name = str(item["function_name"])

                # Note: No threshold filtering here - adapter handles that
                # Severity based on complexity level for prioritization
                if complexity > 20:
                    severity = Priority.HIGH
                elif complexity > 15:
                    severity = Priority.MEDIUM
                else:
                    severity = Priority.LOW

                message = f"Function '{function_name}' has complexity {complexity}"

                issues.append(
                    Issue(
                        type=IssueType.COMPLEXITY,
                        severity=severity,
                        message=message,
                        file_path=file_path,
                        line_number=None,  # complexipy doesn't provide line numbers
                        stage="complexity",
                        details=[
                            f"complexity: {complexity}",
                            f"function: {function_name}",
                        ],
                    )
                )
            except Exception as e:
                logger.error(f"Error parsing complexipy JSON item: {e}", exc_info=True)

        logger.info(f"Parsed {len(issues)} issues from complexipy JSON output")
        return issues

    def get_issue_count(self, data: dict[str, object] | list[object]) -> int:
        """Get issue count from complexipy JSON data.

        Note: Returns count of ALL functions, no threshold filtering.
        The adapter is responsible for filtering by max_complexity threshold.

        Args:
            data: Parsed JSON data

        Returns:
            Number of functions in the data (all, not filtered)
        """
        if isinstance(data, list):
            # Count all valid function entries (adapter will filter by threshold)
            return sum(
                1
                for item in data
                if isinstance(item, dict) and isinstance(item.get("complexity"), int)
            )
        return 0


class SemgrepJSONParser(JSONParser):
    """Parse semgrep JSON output.

    Example output:
        {
            "results": [
                {
                    "check_id": "python.flask.security.xss...",
                    "path": "path/to/file.py",
                    "start": {"line": 10},
                    "extra": {"message": "Possible XSS...", "severity": "ERROR"}
                }
            ]
        }
    """

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        """Parse semgrep JSON data.

        Args:
            data: Parsed JSON data from semgrep

        Returns:
            List of Issue objects for security findings
        """
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

                # Extract path
                path = str(item.get("path", ""))
                if not path:
                    logger.warning("Skipping semgrep item without path")
                    continue

                # Extract line number
                start = item.get("start")
                if isinstance(start, dict):
                    line_number = start.get("line")
                    if isinstance(line_number, int):
                        line_number = int(line_number)
                    else:
                        line_number = None
                else:
                    line_number = None

                # Extract message and metadata
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
        """Get issue count from semgrep JSON data.

        Args:
            data: Parsed JSON data

        Returns:
            Number of issues in the data
        """
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            return len(results) if isinstance(results, list) else 0
        return 0

    def _map_severity(self, severity_str: str) -> Priority:
        """Map semgrep severity string to Priority enum.

        Args:
            severity_str: Semgrep severity string (ERROR, WARNING, INFO)

        Returns:
            Corresponding Priority value
        """
        mapping = {
            "ERROR": Priority.CRITICAL,
            "WARNING": Priority.HIGH,
            "INFO": Priority.MEDIUM,
        }
        return mapping.get(severity_str.upper(), Priority.MEDIUM)


class PipAuditJSONParser(JSONParser):
    """Parse pip-audit JSON output.

    Example output:
        {
            "dependencies": [
                {
                    "name": "package",
                    "vulns": [
                        {
                            "id": "CVE-2025-12345",
                            "description": "Description",
                            "severity": "HIGH"
                        }
                    ]
                }
            ]
        }
    """

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        """Parse pip-audit JSON data.

        Args:
            data: Parsed JSON data from pip-audit

        Returns:
            List of Issue objects for vulnerability findings
        """
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
                            file_path=None,  # Dependency-level issue
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
        """Get issue count from pip-audit JSON data.

        Args:
            data: Parsed JSON data

        Returns:
            Number of issues in the data
        """
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
        """Map pip-audit severity string to Priority enum.

        Args:
            severity_str: pip-audit severity string (HIGH, MEDIUM, LOW)

        Returns:
            Corresponding Priority value
        """
        mapping = {
            "HIGH": Priority.CRITICAL,
            "MEDIUM": Priority.HIGH,
            "LOW": Priority.MEDIUM,
        }
        return mapping.get(severity_str.upper(), Priority.MEDIUM)


class GitleaksJSONParser(JSONParser):
    """Parse gitleaks JSON output.

    Gitleaks saves JSON to a file specified by --report flag.
    The command line specifies: --report /tmp/gitleaks-report.json

    Example JSON content:
        [
            {
                "Description": "AWS Access Key",
                "File": "path/to/file.py",
                "StartLine": 10,
                "RuleID": "aws-access-key",
                "Severity": "HIGH"
            }
        ]
    """

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        """Parse gitleaks output by reading JSON from the report file.

        Args:
            output: Raw text output from gitleaks (may be empty or have summary)
            tool_name: Name of the tool (for logging, currently unused)

        Returns:
            List of Issue objects for secret leaks
        """
        import os

        # Gitleaks writes to fixed path from command line
        json_path = "/tmp/gitleaks-report.json"

        # Read JSON from file
        if not os.path.exists(json_path):
            logger.debug(
                f"Gitleaks JSON file not found: {json_path} (may be no leaks found)"
            )
            return []

        try:
            with open(json_path) as f:
                json_content = f.read()
            data = json.loads(json_content)

            # Clean up the temporary JSON file immediately after reading
            try:
                os.remove(json_path)
                logger.debug(f"Cleaned up gitleaks JSON file: {json_path}")
            except Exception as e:
                logger.warning(f"Failed to remove gitleaks JSON file {json_path}: {e}")
        except Exception as e:
            logger.error(f"Error reading/parsing gitleaks JSON file: {e}")
            return []

        # Parse the JSON data
        return self.parse_json(data)

    def parse_json(self, data: dict[str, object] | list[object]) -> list[Issue]:
        """Parse gitleaks JSON data.

        Args:
            data: Parsed JSON data from gitleaks

        Returns:
            List of Issue objects for secret leaks
        """
        issues: list[Issue] = []

        # gitleaks outputs a list directly
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

                # Extract fields (gitleaks uses PascalCase)
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
        """Get issue count from gitleaks JSON data.

        Args:
            data: Parsed JSON data

        Returns:
            Number of issues in the data
        """
        if isinstance(data, list):
            return len(data)
        return 0

    def _map_severity(self, severity_str: str) -> Priority:
        """Map gitleaks severity string to Priority enum.

        Args:
            severity_str: Gitleaks severity string (HIGH, MEDIUM, LOW)

        Returns:
            Corresponding Priority value
        """
        mapping = {
            "HIGH": Priority.CRITICAL,
            "MEDIUM": Priority.HIGH,
            "LOW": Priority.MEDIUM,
        }
        return mapping.get(severity_str.upper(), Priority.MEDIUM)


# Register parsers with factory
def register_json_parsers(factory: ParserFactory) -> None:
    """Register all JSON parsers with the parser factory.

    This function is called during module initialization to register
    all JSON parsers with the factory.

    Args:
        factory: ParserFactory instance to register parsers with
    """
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
