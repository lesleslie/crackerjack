"""Crackerjack Integration module for progress tracking and test monitoring.

This module provides deep integration with Crackerjack for:
- Progress tracking output parsing for memory enrichment
- Test result monitoring for context enhancement
- Command execution with result capture
- Quality metrics integration
"""

import asyncio
import json
import logging
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CrackerjackCommand(Enum):
    """Supported Crackerjack commands."""

    # Core quality commands
    ANALYZE = "analyze"  # Comprehensive analysis command
    CHECK = "check"
    TEST = "test"
    LINT = "lint"
    FORMAT = "format"
    TYPECHECK = "typecheck"  # Type checking support

    # Security and complexity
    SECURITY = "security"
    COMPLEXITY = "complexity"
    COVERAGE = "coverage"

    # Build and maintenance
    BUILD = "build"
    CLEAN = "clean"

    # Documentation
    DOCS = "docs"

    # Release management
    RELEASE = "release"  # Release command support


class TestStatus(Enum):
    """Test execution status."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    XFAIL = "xfail"
    XPASS = "xpass"


class QualityMetric(Enum):
    """Quality metrics tracked."""

    CODE_COVERAGE = "coverage"
    COMPLEXITY = "complexity"
    LINT_SCORE = "lint_score"
    SECURITY_SCORE = "security_score"
    TEST_PASS_RATE = "test_pass_rate"
    BUILD_STATUS = "build_status"


@dataclass
class CrackerjackResult:
    """Result of Crackerjack command execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    timestamp: datetime
    working_directory: str
    parsed_data: dict[str, Any] | None
    quality_metrics: dict[str, float]
    test_results: list[dict[str, Any]]
    memory_insights: list[str]


@dataclass
class TestResult:
    """Individual test result information."""

    test_id: str
    test_name: str
    status: TestStatus
    duration: float
    file_path: str
    line_number: int | None
    error_message: str | None
    traceback: str | None
    tags: list[str]
    coverage_data: dict[str, Any] | None


@dataclass
class ProgressSnapshot:
    """Progress tracking snapshot."""

    timestamp: datetime
    project_path: str
    command: str
    stage: str
    progress_percentage: float
    current_task: str
    completed_tasks: list[str]
    failed_tasks: list[str]
    quality_metrics: dict[str, float]
    estimated_completion: datetime | None
    memory_context: list[str]


class CrackerjackOutputParser:
    """Parses Crackerjack output for structured data extraction."""

    def __init__(self) -> None:
        """Initialize output parser."""
        self.patterns = {
            # Test results patterns
            "pytest_result": re.compile(
                r"(\w+\.py)::\s*(\w+)\s*(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\s*(?:\[(\d+%)\])?\s*(?:\((.+)\))?",
            ),
            "pytest_summary": re.compile(r"=+ (.+) =+"),
            "pytest_coverage": re.compile(r"TOTAL\s+\d+\s+\d+\s+(\d+)%"),
            # Lint results patterns
            "ruff_error": re.compile(r"(\S+):(\d+):(\d+):\s*(\w+):\s*(.+)"),
            "pyright_error": re.compile(
                r"(\S+):(\d+):(\d+)\s*-\s*(error|warning|info):\s*(.+)",
            ),
            # Security patterns
            "bandit_issue": re.compile(r">> Issue: \[([^\]]+)\]\s*(.+)"),
            "bandit_severity": re.compile(r"Severity: (\w+)\s*Confidence: (\w+)"),
            # Complexity patterns
            "complexity_score": re.compile(r"(\S+)\s+(\d+)\s+(\d+\.\d+)"),
            # Coverage patterns
            "coverage_line": re.compile(r"(\S+)\s+(\d+)\s+(\d+)\s+(\d+)%"),
            # Progress patterns
            "progress_indicator": re.compile(r"(?:Progress:|Stage:|Running:)\s*(.+)"),
            "percentage": re.compile(r"(\d+(?:\.\d+)?)%"),
            "task_completion": re.compile(r"✅\s*(.+)|PASSED\s*(.+)|SUCCESS\s*(.+)"),
            "task_failure": re.compile(r"❌\s*(.+)|FAILED\s*(.+)|ERROR\s*(.+)"),
            # New crackerjack v0.31.4+ patterns
            "ai_agent_action": re.compile(r"🤖\s*AI Agent:\s*(.+)"),
            "quality_gate": re.compile(r"Quality Gate:\s*(\w+)\s*\((\d+)%\)"),
            "release_info": re.compile(r"Release:\s*(.+)\s*→\s*(.+)"),
            "typecheck_error": re.compile(
                r"(\S+):(\d+):(\d+)\s*-\s*(error|warning):\s*(.+)"
            ),
            # Enhanced progress patterns
            "stage_progress": re.compile(r"Stage\s+(\d+)/(\d+):\s*(.+)"),
            "eta_estimate": re.compile(r"ETA:\s*(\d+m\s*\d+s|\d+s)"),
            "crackerjack_stage": re.compile(r"🔧\s*(.+)\s*\.\.\.\s*(.+)"),
            "auto_fix": re.compile(r"🔧\s*Auto-fixing:\s*(.+)"),
        }

    def parse_output(
        self,
        command: str,
        stdout: str,
        stderr: str,
    ) -> tuple[dict[str, Any], list[str]]:
        """Parse Crackerjack output and extract insights."""
        parsed_data = {
            "command": command,
            "test_results": [],
            "lint_issues": [],
            "security_issues": [],
            "coverage_data": {},
            "complexity_data": {},
            "progress_info": {},
            "quality_metrics": {},
        }

        memory_insights = []

        # Combine stdout and stderr for comprehensive parsing
        full_output = f"{stdout}\n{stderr}"

        # Parse based on command type
        if command in ["test", "check"]:
            parsed_data.update(self._parse_test_output(full_output))
            memory_insights.extend(self._extract_test_insights(parsed_data))

        if command in ["lint", "format", "check"]:
            parsed_data.update(self._parse_lint_output(full_output))
            memory_insights.extend(self._extract_lint_insights(parsed_data))

        if command in ["security", "check"]:
            parsed_data.update(self._parse_security_output(full_output))
            memory_insights.extend(self._extract_security_insights(parsed_data))

        if command in ["coverage", "test", "check"]:
            parsed_data.update(self._parse_coverage_output(full_output))
            memory_insights.extend(self._extract_coverage_insights(parsed_data))

        if command in ["complexity", "check"]:
            parsed_data.update(self._parse_complexity_output(full_output))
            memory_insights.extend(self._extract_complexity_insights(parsed_data))

        # Always parse progress information
        parsed_data.update(self._parse_progress_output(full_output))
        memory_insights.extend(self._extract_progress_insights(parsed_data))

        return parsed_data, memory_insights

    def _parse_test_output(self, output: str) -> dict[str, Any]:
        """Parse pytest output for test results."""
        data = {"test_results": [], "test_summary": {}}

        lines = output.split("\n")

        for line in lines:
            # Test result lines
            match = self.patterns["pytest_result"].search(line)
            if match:
                file_path, test_name, status, coverage, duration = match.groups()
                data["test_results"].append(
                    {
                        "file": file_path,
                        "test": test_name,
                        "status": status.lower(),
                        "coverage": coverage,
                        "duration": duration,
                    },
                )

            # Summary lines
            summary_match = self.patterns["pytest_summary"].search(line)
            if summary_match:
                summary_text = summary_match.group(1)
                if "passed" in summary_text or "failed" in summary_text:
                    data["test_summary"]["summary"] = summary_text

        return data

    def _parse_lint_output(self, output: str) -> dict[str, Any]:
        """Parse lint output for code quality issues."""
        data = {"lint_issues": [], "lint_summary": {}}

        lines = output.split("\n")
        total_errors = 0

        for line in lines:
            # Ruff errors
            ruff_match = self.patterns["ruff_error"].search(line)
            if ruff_match:
                file_path, line_num, col_num, error_type, message = ruff_match.groups()
                data["lint_issues"].append(
                    {
                        "tool": "ruff",
                        "file": file_path,
                        "line": int(line_num),
                        "column": int(col_num),
                        "type": error_type,
                        "message": message,
                    },
                )
                total_errors += 1

            # Pyright errors
            pyright_match = self.patterns["pyright_error"].search(line)
            if pyright_match:
                file_path, line_num, col_num, severity, message = pyright_match.groups()
                data["lint_issues"].append(
                    {
                        "tool": "pyright",
                        "file": file_path,
                        "line": int(line_num),
                        "column": int(col_num),
                        "type": severity,
                        "message": message,
                    },
                )
                total_errors += 1

        data["lint_summary"] = {"total_issues": total_errors}
        return data

    def _parse_security_output(self, output: str) -> dict[str, Any]:
        """Parse bandit security scan output."""
        data = {"security_issues": [], "security_summary": {}}

        lines = output.split("\n")
        current_issue = None

        for line in lines:
            issue_match = self.patterns["bandit_issue"].search(line)
            if issue_match:
                issue_id, description = issue_match.groups()
                current_issue = {
                    "id": issue_id,
                    "description": description,
                    "severity": None,
                    "confidence": None,
                }
                data["security_issues"].append(current_issue)

            severity_match = self.patterns["bandit_severity"].search(line)
            if severity_match and current_issue:
                severity, confidence = severity_match.groups()
                current_issue["severity"] = severity
                current_issue["confidence"] = confidence

        data["security_summary"] = {"total_issues": len(data["security_issues"])}
        return data

    def _parse_coverage_output(self, output: str) -> dict[str, Any]:
        """Parse coverage report output."""
        data = {"coverage_data": {}, "coverage_summary": {}}

        lines = output.split("\n")

        for line in lines:
            # Individual file coverage
            coverage_match = self.patterns["coverage_line"].search(line)
            if coverage_match:
                file_path, statements, missing, coverage = coverage_match.groups()
                data["coverage_data"][file_path] = {
                    "statements": int(statements),
                    "missing": int(missing),
                    "coverage": int(coverage.rstrip("%")),
                }

            # Total coverage
            total_match = self.patterns["pytest_coverage"].search(line)
            if total_match:
                total_coverage = int(total_match.group(1))
                data["coverage_summary"]["total_coverage"] = total_coverage

        return data

    def _parse_complexity_output(self, output: str) -> dict[str, Any]:
        """Parse complexity analysis output."""
        data = {"complexity_data": {}, "complexity_summary": {}}

        lines = output.split("\n")
        total_files = 0
        high_complexity = 0

        for line in lines:
            complexity_match = self.patterns["complexity_score"].search(line)
            if complexity_match:
                file_path, lines_count, complexity_score = complexity_match.groups()
                complexity_val = float(complexity_score)
                data["complexity_data"][file_path] = {
                    "lines": int(lines_count),
                    "complexity": complexity_val,
                }
                total_files += 1
                if complexity_val > 10:  # Configurable threshold
                    high_complexity += 1

        data["complexity_summary"] = {
            "total_files": total_files,
            "high_complexity_files": high_complexity,
        }
        return data

    def _parse_progress_output(self, output: str) -> dict[str, Any]:
        """Parse progress indicators from output."""
        data = {"progress_info": {}}

        lines = output.split("\n")
        completed_tasks = []
        failed_tasks = []
        current_percentage = 0

        for line in lines:
            # Progress indicators
            progress_match = self.patterns["progress_indicator"].search(line)
            if progress_match:
                data["progress_info"]["current_task"] = progress_match.group(1)

            # Percentage completion
            percentage_match = self.patterns["percentage"].search(line)
            if percentage_match:
                current_percentage = float(percentage_match.group(1))

            # Task completions
            completion_match = self.patterns["task_completion"].search(line)
            if completion_match:
                task = (
                    completion_match.group(1)
                    or completion_match.group(2)
                    or completion_match.group(3)
                )
                if task:
                    completed_tasks.append(task.strip())

            # Task failures
            failure_match = self.patterns["task_failure"].search(line)
            if failure_match:
                task = (
                    failure_match.group(1)
                    or failure_match.group(2)
                    or failure_match.group(3)
                )
                if task:
                    failed_tasks.append(task.strip())

        data["progress_info"].update(
            {
                "percentage": current_percentage,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
            },
        )

        return data

    def _extract_test_insights(self, parsed_data: dict[str, Any]) -> list[str]:
        """Extract memory insights from test results."""
        insights = []
        test_results = parsed_data.get("test_results", [])

        if test_results:
            passed = sum(1 for t in test_results if t["status"] == "passed")
            failed = sum(1 for t in test_results if t["status"] == "failed")
            total = len(test_results)

            if total > 0:
                pass_rate = (passed / total) * 100
                insights.append(
                    f"Test suite: {passed}/{total} tests passed ({pass_rate:.1f}% pass rate)",
                )

                if failed > 0:
                    failed_files = {
                        t["file"] for t in test_results if t["status"] == "failed"
                    }
                    insights.append(
                        f"Test failures found in {len(failed_files)} files: {', '.join(failed_files)}",
                    )

                if pass_rate == 100:
                    insights.append("All tests passing - code quality is stable")
                elif pass_rate < 80:
                    insights.append(
                        "Test pass rate below 80% - investigate failing tests",
                    )

        return insights

    def _extract_lint_insights(self, parsed_data: dict[str, Any]) -> list[str]:
        """Extract memory insights from lint results."""
        insights = []
        lint_issues = parsed_data.get("lint_issues", [])

        if lint_issues:
            total_issues = len(lint_issues)
            by_type = {}
            by_file = {}

            for issue in lint_issues:
                issue_type = issue.get("type", "unknown")
                file_path = issue.get("file", "unknown")

                by_type[issue_type] = by_type.get(issue_type, 0) + 1
                by_file[file_path] = by_file.get(file_path, 0) + 1

            insights.append(f"Code quality: {total_issues} lint issues found")

            # Top issue types
            top_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_types:
                type_summary = ", ".join(f"{t}: {c}" for t, c in top_types)
                insights.append(f"Most common issues: {type_summary}")

            # Files needing attention
            top_files = sorted(by_file.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_files and top_files[0][1] > 5:
                insights.append(
                    f"Files needing attention: {top_files[0][0]} ({top_files[0][1]} issues)",
                )
        else:
            insights.append("Code quality: No lint issues found - code is clean")

        return insights

    def _extract_security_insights(self, parsed_data: dict[str, Any]) -> list[str]:
        """Extract memory insights from security scan."""
        insights = []
        security_issues = parsed_data.get("security_issues", [])

        if security_issues:
            total_issues = len(security_issues)
            high_severity = sum(
                1 for i in security_issues if i.get("severity") == "HIGH"
            )

            insights.append(
                f"Security scan: {total_issues} potential security issues found",
            )

            if high_severity > 0:
                insights.append(
                    f"⚠️ {high_severity} high-severity security issues require immediate attention",
                )
            else:
                insights.append("No high-severity security issues detected")
        else:
            insights.append(
                "Security scan: No security issues detected - code appears secure",
            )

        return insights

    def _extract_coverage_insights(self, parsed_data: dict[str, Any]) -> list[str]:
        """Extract memory insights from coverage data."""
        insights = []
        coverage_summary = parsed_data.get("coverage_summary", {})

        if "total_coverage" in coverage_summary:
            coverage = coverage_summary["total_coverage"]
            insights.append(f"Test coverage: {coverage}% of code is covered by tests")

            if coverage >= 90:
                insights.append("Excellent test coverage - code is well tested")
            elif coverage >= 80:
                insights.append("Good test coverage - consider adding more tests")
            elif coverage >= 60:
                insights.append(
                    "Moderate test coverage - significant testing gaps exist",
                )
            else:
                insights.append(
                    "Low test coverage - critical testing gaps need attention",
                )

        return insights

    def _extract_complexity_insights(self, parsed_data: dict[str, Any]) -> list[str]:
        """Extract memory insights from complexity analysis."""
        insights = []
        complexity_summary = parsed_data.get("complexity_summary", {})

        if complexity_summary:
            total_files = complexity_summary.get("total_files", 0)
            high_complexity = complexity_summary.get("high_complexity_files", 0)

            if total_files > 0:
                complexity_rate = (high_complexity / total_files) * 100
                insights.append(
                    f"Code complexity: {high_complexity}/{total_files} files have high complexity ({complexity_rate:.1f}%)",
                )

                if complexity_rate == 0:
                    insights.append("Code complexity is well managed")
                elif complexity_rate > 20:
                    insights.append(
                        "Consider refactoring high-complexity files for maintainability",
                    )

        return insights

    def _extract_progress_insights(self, parsed_data: dict[str, Any]) -> list[str]:
        """Extract memory insights from progress information."""
        insights = []
        progress_info = parsed_data.get("progress_info", {})

        completed_tasks = progress_info.get("completed_tasks", [])
        failed_tasks = progress_info.get("failed_tasks", [])
        percentage = progress_info.get("percentage", 0)

        if completed_tasks:
            insights.append(f"Progress: Completed {len(completed_tasks)} tasks")

        if failed_tasks:
            insights.append(
                f"⚠️ {len(failed_tasks)} tasks failed: {', '.join(failed_tasks[:3])}",
            )

        if percentage > 0:
            insights.append(f"Overall progress: {percentage}% complete")

        return insights


class CrackerjackIntegration:
    """Main integration class for Crackerjack command execution and monitoring."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize Crackerjack integration."""
        self.db_path = db_path or str(
            Path.home() / ".claude" / "data" / "crackerjack_integration.db",
        )
        self.parser = CrackerjackOutputParser()
        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database for Crackerjack integration."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crackerjack_results (
                    id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    exit_code INTEGER,
                    stdout TEXT,
                    stderr TEXT,
                    execution_time REAL,
                    timestamp TIMESTAMP,
                    working_directory TEXT,
                    parsed_data TEXT,  -- JSON
                    quality_metrics TEXT,  -- JSON
                    memory_insights TEXT  -- JSON array
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_results (
                    id TEXT PRIMARY KEY,
                    result_id TEXT NOT NULL,
                    test_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration REAL,
                    file_path TEXT,
                    line_number INTEGER,
                    error_message TEXT,
                    timestamp TIMESTAMP,
                    FOREIGN KEY (result_id) REFERENCES crackerjack_results(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS progress_snapshots (
                    id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    command TEXT NOT NULL,
                    stage TEXT,
                    progress_percentage REAL,
                    current_task TEXT,
                    completed_tasks TEXT,  -- JSON array
                    failed_tasks TEXT,     -- JSON array
                    quality_metrics TEXT,  -- JSON
                    timestamp TIMESTAMP,
                    memory_context TEXT    -- JSON array
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS quality_metrics_history (
                    id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    timestamp TIMESTAMP,
                    result_id TEXT,
                    FOREIGN KEY (result_id) REFERENCES crackerjack_results(id)
                )
            """)

            # Create indices
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_results_timestamp ON crackerjack_results(timestamp)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_results_command ON crackerjack_results(command)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_test_results_status ON test_results(status)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_progress_project ON progress_snapshots(project_path)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metrics_type ON quality_metrics_history(metric_type)",
            )

    async def execute_crackerjack_command(
        self,
        command: str,
        args: list[str] | None = None,
        working_directory: str = ".",
        timeout: int = 300,
        ai_agent_mode: bool = False,
    ) -> CrackerjackResult:
        """Execute Crackerjack command and capture results."""
        args = args or []

        # Add AI agent mode support
        if ai_agent_mode:
            args.append("--ai-agent")

        full_command = ["crackerjack", command, *args]

        start_time = time.time()
        result_id = f"cj_{int(start_time * 1000)}"

        try:
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *full_command,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            exit_code = process.returncode
            execution_time = time.time() - start_time

            # Decode output
            stdout_text = stdout.decode("utf-8", errors="ignore")
            stderr_text = stderr.decode("utf-8", errors="ignore")

            # Parse output for insights
            parsed_data, memory_insights = self.parser.parse_output(
                command,
                stdout_text,
                stderr_text,
            )

            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(parsed_data, exit_code)

            # Create result object
            result = CrackerjackResult(
                command=command,
                exit_code=exit_code,
                stdout=stdout_text,
                stderr=stderr_text,
                execution_time=execution_time,
                timestamp=datetime.now(),
                working_directory=working_directory,
                parsed_data=parsed_data,
                quality_metrics=quality_metrics,
                test_results=parsed_data.get("test_results", []),
                memory_insights=memory_insights,
            )

            # Store in database
            await self._store_result(result_id, result)

            # Store progress snapshot
            await self._store_progress_snapshot(result_id, result, working_directory)

            return result

        except TimeoutError:
            execution_time = time.time() - start_time
            error_result = CrackerjackResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                execution_time=execution_time,
                timestamp=datetime.now(),
                working_directory=working_directory,
                parsed_data={},
                quality_metrics={},
                test_results=[],
                memory_insights=[
                    f"Command '{command}' timed out - consider optimizing or increasing timeout",
                ],
            )

            await self._store_result(result_id, error_result)
            return error_result

        except Exception as e:
            execution_time = time.time() - start_time
            error_result = CrackerjackResult(
                command=command,
                exit_code=-2,
                stdout="",
                stderr=f"Execution error: {e!s}",
                execution_time=execution_time,
                timestamp=datetime.now(),
                working_directory=working_directory,
                parsed_data={},
                quality_metrics={},
                test_results=[],
                memory_insights=[f"Command '{command}' failed with error: {e!s}"],
            )

            await self._store_result(result_id, error_result)
            return error_result

    async def get_recent_results(
        self,
        hours: int = 24,
        command: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent Crackerjack execution results."""
        since = datetime.now() - timedelta(hours=hours)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            where_conditions = ["timestamp >= ?"]
            params = [since]

            if command:
                where_conditions.append("command = ?")
                params.append(command)

            query = f"""
                SELECT * FROM crackerjack_results
                WHERE {" AND ".join(where_conditions)}
                ORDER BY timestamp DESC
            """

            cursor = conn.execute(query, params)
            results = []

            for row in cursor.fetchall():
                result = dict(row)
                result["parsed_data"] = json.loads(result["parsed_data"] or "{}")
                result["quality_metrics"] = json.loads(
                    result["quality_metrics"] or "{}",
                )
                result["memory_insights"] = json.loads(
                    result["memory_insights"] or "[]",
                )
                results.append(result)

            return results

    async def get_quality_metrics_history(
        self,
        project_path: str,
        metric_type: str | None = None,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get quality metrics history for trend analysis."""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            where_conditions = ["project_path = ?", "timestamp >= ?"]
            params = [project_path, since]

            if metric_type:
                where_conditions.append("metric_type = ?")
                params.append(metric_type)

            query = f"""
                SELECT * FROM quality_metrics_history
                WHERE {" AND ".join(where_conditions)}
                ORDER BY timestamp DESC
            """

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    async def get_test_failure_patterns(self, days: int = 7) -> dict[str, Any]:
        """Analyze test failure patterns for insights."""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get failed tests
            failed_tests = conn.execute(
                """
                SELECT test_name, file_path, error_message, COUNT(*) as failure_count
                FROM test_results
                WHERE status = 'failed' AND timestamp >= ?
                GROUP BY test_name, file_path, error_message
                ORDER BY failure_count DESC
            """,
                (since,),
            ).fetchall()

            # Get flaky tests (alternating pass/fail)
            flaky_tests = conn.execute(
                """
                SELECT test_name, file_path,
                       COUNT(DISTINCT status) as status_count,
                       COUNT(*) as total_runs
                FROM test_results
                WHERE timestamp >= ?
                GROUP BY test_name, file_path
                HAVING status_count > 1 AND total_runs >= 3
                ORDER BY status_count DESC, total_runs DESC
            """,
                (since,),
            ).fetchall()

            # Get most failing files
            failing_files = conn.execute(
                """
                SELECT file_path, COUNT(*) as failure_count
                FROM test_results
                WHERE status = 'failed' AND timestamp >= ?
                GROUP BY file_path
                ORDER BY failure_count DESC
                LIMIT 10
            """,
                (since,),
            ).fetchall()

            return {
                "failed_tests": [dict(row) for row in failed_tests],
                "flaky_tests": [dict(row) for row in flaky_tests],
                "failing_files": [dict(row) for row in failing_files],
                "analysis_period_days": days,
            }

    async def get_quality_trends(
        self,
        project_path: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Analyze quality trends over time."""
        metrics_history = await self.get_quality_metrics_history(
            project_path, None, days
        )

        # Calculate trends for each metric type
        trends = {}
        for metric_type in [
            "test_pass_rate",
            "code_coverage",
            "lint_score",
            "security_score",
            "complexity_score",
        ]:
            metric_values = [
                m for m in metrics_history if m["metric_type"] == metric_type
            ]
            if len(metric_values) >= 2:
                # Sort by timestamp (most recent first)
                metric_values.sort(key=lambda x: x["timestamp"], reverse=True)

                # Split into recent and older halves
                mid_point = len(metric_values) // 2
                recent = metric_values[:mid_point] if mid_point > 0 else metric_values
                older = metric_values[mid_point:] if mid_point > 0 else []

                if recent and older:
                    recent_avg = sum(m["metric_value"] for m in recent) / len(recent)
                    older_avg = sum(m["metric_value"] for m in older) / len(older)
                    change = recent_avg - older_avg

                    trends[metric_type] = {
                        "direction": "improving"
                        if change > 0
                        else "declining"
                        if change < 0
                        else "stable",
                        "change": abs(change),
                        "change_percentage": (abs(change) / older_avg * 100)
                        if older_avg > 0
                        else 0,
                        "recent_average": recent_avg,
                        "previous_average": older_avg,
                        "data_points": len(metric_values),
                        "trend_strength": "strong"
                        if abs(change) > 5
                        else "moderate"
                        if abs(change) > 1
                        else "weak",
                    }
                else:
                    # Not enough data for trend analysis
                    current_avg = sum(m["metric_value"] for m in metric_values) / len(
                        metric_values
                    )
                    trends[metric_type] = {
                        "direction": "insufficient_data",
                        "change": 0,
                        "change_percentage": 0,
                        "recent_average": current_avg,
                        "previous_average": current_avg,
                        "data_points": len(metric_values),
                        "trend_strength": "unknown",
                    }

        # Overall trend assessment
        improving_metrics = sum(
            1 for t in trends.values() if t["direction"] == "improving"
        )
        declining_metrics = sum(
            1 for t in trends.values() if t["direction"] == "declining"
        )

        overall_assessment = {
            "overall_direction": "improving"
            if improving_metrics > declining_metrics
            else "declining"
            if declining_metrics > improving_metrics
            else "stable",
            "improving_count": improving_metrics,
            "declining_count": declining_metrics,
            "stable_count": len(trends) - improving_metrics - declining_metrics,
            "analysis_period_days": days,
        }

        return {
            "trends": trends,
            "overall": overall_assessment,
            "recommendations": self._generate_trend_recommendations(trends),
        }

    def _generate_trend_recommendations(self, trends: dict[str, Any]) -> list[str]:
        """Generate recommendations based on quality trends."""
        recommendations = []

        for metric_type, trend_data in trends.items():
            direction = trend_data["direction"]
            strength = trend_data["trend_strength"]
            change = trend_data["change"]

            if direction == "declining" and strength in ["strong", "moderate"]:
                if metric_type == "test_pass_rate":
                    recommendations.append(
                        f"⚠️ Test pass rate declining by {change:.1f}% - investigate failing tests"
                    )
                elif metric_type == "code_coverage":
                    recommendations.append(
                        f"⚠️ Code coverage declining by {change:.1f}% - add more tests"
                    )
                elif metric_type == "lint_score":
                    recommendations.append(
                        "⚠️ Code quality declining - address lint issues"
                    )
                elif metric_type == "security_score":
                    recommendations.append(
                        "🔒 Security score declining - review security findings"
                    )
                elif metric_type == "complexity_score":
                    recommendations.append(
                        "🔧 Code complexity increasing - consider refactoring"
                    )

            elif direction == "improving" and strength == "strong":
                if (
                    metric_type == "test_pass_rate"
                    and trend_data["recent_average"] > 95
                ):
                    recommendations.append(
                        "✅ Excellent test pass rate trend - maintain current practices"
                    )
                elif (
                    metric_type == "code_coverage" and trend_data["recent_average"] > 85
                ):
                    recommendations.append(
                        "✅ Great coverage improvement - continue testing efforts"
                    )

        # Add general recommendations
        if not recommendations:
            recommendations.append(
                "📈 Quality metrics are stable - continue current practices"
            )

        return recommendations

    async def health_check(self) -> dict[str, Any]:
        """Check integration health and dependencies."""
        health = {
            "crackerjack_available": False,
            "database_accessible": False,
            "version_compatible": False,
            "recommendations": [],
            "status": "unhealthy",
        }

        try:
            # Check crackerjack availability
            process = await asyncio.create_subprocess_exec(
                "crackerjack",
                "--help",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await process.communicate()
            health["crackerjack_available"] = process.returncode == 0

            if health["crackerjack_available"]:
                health["recommendations"].append(
                    "✅ Crackerjack is available and responding"
                )
            else:
                health["recommendations"].append(
                    "❌ Crackerjack not available - install with 'uv add crackerjack'"
                )

            # Check database accessibility
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("SELECT 1").fetchone()
                health["database_accessible"] = True
                health["recommendations"].append("✅ Database connection successful")

                # Check if we have any data
                cursor = conn.execute("SELECT COUNT(*) FROM crackerjack_results")
                result_count = cursor.fetchone()[0]

                if result_count > 0:
                    health["recommendations"].append(
                        f"📊 {result_count} execution records available"
                    )
                else:
                    health["recommendations"].append(
                        "📝 No execution history - run some crackerjack commands"
                    )

            # Overall status
            if health["crackerjack_available"] and health["database_accessible"]:
                health["status"] = "healthy"
            elif health["database_accessible"]:
                health["status"] = "partial"
            else:
                health["status"] = "unhealthy"

        except sqlite3.Error as e:
            health["database_accessible"] = False
            health["recommendations"].append(f"❌ Database error: {e}")
        except Exception as e:
            health["error"] = str(e)
            health["recommendations"].append(f"❌ Health check error: {e}")

        return health

    def _calculate_quality_metrics(
        self,
        parsed_data: dict[str, Any],
        exit_code: int,
    ) -> dict[str, float]:
        """Calculate quality metrics from parsed data."""
        metrics = {}

        # Test metrics
        test_results = parsed_data.get("test_results", [])
        if test_results:
            passed = sum(1 for t in test_results if t["status"] == "passed")
            total = len(test_results)
            metrics["test_pass_rate"] = (passed / total) * 100 if total > 0 else 0

        # Coverage metrics
        coverage_summary = parsed_data.get("coverage_summary", {})
        if "total_coverage" in coverage_summary:
            metrics["code_coverage"] = float(coverage_summary["total_coverage"])

        # Lint metrics
        lint_summary = parsed_data.get("lint_summary", {})
        if "total_issues" in lint_summary:
            # Invert to make higher scores better
            total_issues = lint_summary["total_issues"]
            metrics["lint_score"] = (
                max(0, 100 - total_issues) if total_issues < 100 else 0
            )

        # Security metrics
        security_summary = parsed_data.get("security_summary", {})
        if "total_issues" in security_summary:
            total_issues = security_summary["total_issues"]
            metrics["security_score"] = (
                max(0, 100 - (total_issues * 10)) if total_issues < 10 else 0
            )

        # Complexity metrics
        complexity_summary = parsed_data.get("complexity_summary", {})
        if complexity_summary:
            total_files = complexity_summary.get("total_files", 0)
            high_complexity = complexity_summary.get("high_complexity_files", 0)
            if total_files > 0:
                complexity_rate = (high_complexity / total_files) * 100
                metrics["complexity_score"] = max(0, 100 - complexity_rate)

        # Overall build status
        metrics["build_status"] = 100 if exit_code == 0 else 0

        return metrics

    async def _store_result(self, result_id: str, result: CrackerjackResult) -> None:
        """Store Crackerjack result in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO crackerjack_results
                (id, command, exit_code, stdout, stderr, execution_time, timestamp,
                 working_directory, parsed_data, quality_metrics, memory_insights)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    result_id,
                    result.command,
                    result.exit_code,
                    result.stdout,
                    result.stderr,
                    result.execution_time,
                    result.timestamp,
                    result.working_directory,
                    json.dumps(result.parsed_data),
                    json.dumps(result.quality_metrics),
                    json.dumps(result.memory_insights),
                ),
            )

            # Store individual test results
            for test_result in result.test_results:
                test_id = f"test_{result_id}_{hash(test_result.get('test', 'unknown'))}"
                conn.execute(
                    """
                    INSERT INTO test_results
                    (id, result_id, test_name, status, duration, file_path, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        test_id,
                        result_id,
                        test_result.get("test", ""),
                        test_result.get("status", ""),
                        test_result.get("duration", 0),
                        test_result.get("file", ""),
                        result.timestamp,
                    ),
                )

            # Store quality metrics
            for metric_name, metric_value in result.quality_metrics.items():
                metric_id = f"metric_{result_id}_{metric_name}"
                conn.execute(
                    """
                    INSERT INTO quality_metrics_history
                    (id, project_path, metric_type, metric_value, timestamp, result_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        metric_id,
                        result.working_directory,
                        metric_name,
                        metric_value,
                        result.timestamp,
                        result_id,
                    ),
                )

    async def _store_progress_snapshot(
        self,
        result_id: str,
        result: CrackerjackResult,
        project_path: str,
    ) -> None:
        """Store progress snapshot from result."""
        progress_info = result.parsed_data.get("progress_info", {})

        if progress_info:
            snapshot_id = f"progress_{result_id}"

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO progress_snapshots
                    (id, project_path, command, stage, progress_percentage, current_task,
                     completed_tasks, failed_tasks, quality_metrics, timestamp, memory_context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        snapshot_id,
                        project_path,
                        result.command,
                        progress_info.get("stage", ""),
                        progress_info.get("percentage", 0),
                        progress_info.get("current_task", ""),
                        json.dumps(progress_info.get("completed_tasks", [])),
                        json.dumps(progress_info.get("failed_tasks", [])),
                        json.dumps(result.quality_metrics),
                        result.timestamp,
                        json.dumps(result.memory_insights),
                    ),
                )


# Global integration instance
_crackerjack_integration = None


def get_crackerjack_integration() -> CrackerjackIntegration:
    """Get global Crackerjack integration instance."""
    global _crackerjack_integration
    if _crackerjack_integration is None:
        _crackerjack_integration = CrackerjackIntegration()
    return _crackerjack_integration


# Public API functions for MCP tools
async def execute_crackerjack_command(
    command: str,
    args: list[str] | None = None,
    working_directory: str = ".",
    timeout: int = 300,
    ai_agent_mode: bool = False,
) -> dict[str, Any]:
    """Execute Crackerjack command and return structured results."""
    integration = get_crackerjack_integration()
    result = await integration.execute_crackerjack_command(
        command,
        args,
        working_directory,
        timeout,
        ai_agent_mode,
    )
    return asdict(result)


async def get_recent_crackerjack_results(
    hours: int = 24,
    command: str | None = None,
) -> list[dict[str, Any]]:
    """Get recent Crackerjack execution results."""
    integration = get_crackerjack_integration()
    return await integration.get_recent_results(hours, command)


async def get_quality_metrics_history(
    project_path: str,
    metric_type: str | None = None,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Get quality metrics history for trend analysis."""
    integration = get_crackerjack_integration()
    return await integration.get_quality_metrics_history(
        project_path,
        metric_type,
        days,
    )


async def analyze_test_failure_patterns(days: int = 7) -> dict[str, Any]:
    """Analyze test failure patterns for insights."""
    integration = get_crackerjack_integration()
    return await integration.get_test_failure_patterns(days)


async def get_quality_trends(
    project_path: str,
    days: int = 30,
) -> dict[str, Any]:
    """Analyze quality trends over time."""
    integration = get_crackerjack_integration()
    return await integration.get_quality_trends(project_path, days)


async def crackerjack_health_check() -> dict[str, Any]:
    """Check Crackerjack integration health and dependencies."""
    integration = get_crackerjack_integration()
    return await integration.health_check()
