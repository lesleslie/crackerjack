"""Issue parsing and classification for workflow failures.

Parses test and hook failures into structured Issue objects for AI agent processing.
Extracted from WorkflowOrchestrator to improve modularity and testability.

This module handles:
- Collection of test failure issues
- Collection of hook failure issues
- Classification of issues by type and priority
- Detection of specific error patterns (complexity, type, security, etc.)
"""

from __future__ import annotations

import typing as t

from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.models.protocols import (
    DebugServiceProtocol,
    LoggerProtocol,
)


class WorkflowIssueParser:
    """Parses and classifies workflow failures into structured issues.

    This parser extracts issues from test failures and hook execution results,
    classifying them by type (complexity, security, type errors, etc.) and
    priority level for AI agent processing.

    Uses dependency injection for all required services (Console, Logger, Debug).
    """

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        logger: Inject[LoggerProtocol],
        debugger: Inject[DebugServiceProtocol],
    ) -> None:
        """Initialize the issue parser with injected dependencies.

        Args:
            console: Console for output
            logger: Logger for diagnostic messages
            debugger: Debug service for detailed diagnostics
        """
        self.console = console
        self.logger = logger
        self.debugger = debugger

    async def _collect_issues_from_failures(
        self,
        phases: t.Any,
        session: t.Any,
        debug_enabled: bool = False,
    ) -> list[Issue]:
        """Collect all issues from test and hook failures.

        Args:
            phases: PhaseCoordinator instance with test_manager and hook_manager
            session: SessionCoordinator instance with session_tracker
            debug_enabled: Whether debug mode is enabled

        Returns:
            List of structured Issue objects for AI agent processing
        """
        issues: list[Issue] = []

        test_issues, test_count = self._collect_test_failure_issues(phases)
        hook_issues, hook_count = self._collect_hook_failure_issues(phases, session)

        issues.extend(test_issues)
        issues.extend(hook_issues)

        self._log_failure_counts_if_debugging(test_count, hook_count, debug_enabled)

        return issues

    def _collect_test_failure_issues(self, phases: t.Any) -> tuple[list[Issue], int]:
        """Collect issues from test failures.

        Args:
            phases: PhaseCoordinator instance with test_manager

        Returns:
            Tuple of (list of test failure issues, count of test failures)
        """
        issues: list[Issue] = []
        test_count = 0

        if hasattr(phases, "test_manager") and hasattr(
            phases.test_manager,
            "get_test_failures",
        ):
            test_failures = phases.test_manager.get_test_failures()
            test_count = len(test_failures)
            for i, failure in enumerate(
                test_failures[:20],
            ):
                issue = Issue(
                    id=f"test_failure_{i}",
                    type=IssueType.TEST_FAILURE,
                    severity=Priority.HIGH,
                    message=failure.strip(),
                    stage="tests",
                )
                issues.append(issue)

        return issues, test_count

    def _collect_hook_failure_issues(
        self, phases: t.Any, session: t.Any
    ) -> tuple[list[Issue], int]:
        """Collect issues from hook execution failures.

        Args:
            phases: PhaseCoordinator instance with hook_manager
            session: SessionCoordinator instance with session_tracker

        Returns:
            Tuple of (list of hook failure issues, count of hook failures)
        """
        issues: list[Issue] = []
        hook_count = 0

        try:
            hook_results = phases.hook_manager.run_comprehensive_hooks()
            issues, hook_count = self._process_hook_results(hook_results)
        except Exception:
            issues, hook_count = self._fallback_to_session_tracker(session)

        return issues, hook_count

    def _process_hook_results(self, hook_results: t.Any) -> tuple[list[Issue], int]:
        """Process hook execution results into issues.

        Args:
            hook_results: Results from hook manager execution

        Returns:
            Tuple of (list of issues, count of failed hooks)
        """
        issues: list[Issue] = []
        hook_count = 0

        for result in hook_results:
            if not self._is_hook_result_failed(result):
                continue

            hook_count += 1
            result_issues = self._extract_issues_from_hook_result(result)
            issues.extend(result_issues)

        return issues, hook_count

    def _is_hook_result_failed(self, result: t.Any) -> bool:
        """Check if a hook result indicates failure.

        Args:
            result: Hook execution result object

        Returns:
            True if the hook failed, error occurred, or timed out
        """
        return result.status in ("failed", "error", "timeout")

    def _extract_issues_from_hook_result(self, result: t.Any) -> list[Issue]:
        """Extract structured issues from a failed hook result.

        Args:
            result: Failed hook execution result

        Returns:
            List of Issue objects parsed from the hook failure
        """
        if result.issues_found:
            return self._create_specific_issues_from_hook_result(result)
        return [self._create_generic_issue_from_hook_result(result)]

    def _create_specific_issues_from_hook_result(self, result: t.Any) -> list[Issue]:
        """Create specific issues from hook result with detailed issue information.

        Args:
            result: Hook result with issues_found list

        Returns:
            List of parsed and classified issues
        """
        issues: list[Issue] = []
        hook_context = f"{result.name}: "

        for issue_text in result.issues_found:
            parsed_issues = self._parse_issues_for_agents([hook_context + issue_text])
            issues.extend(parsed_issues)

        return issues

    def _create_generic_issue_from_hook_result(self, result: t.Any) -> Issue:
        """Create a generic issue from a hook result without specific details.

        Args:
            result: Failed hook execution result

        Returns:
            Generic Issue object for the hook failure
        """
        issue_type = self._determine_hook_issue_type(result.name)
        return Issue(
            id=f"hook_failure_{result.name}",
            type=issue_type,
            severity=Priority.MEDIUM,
            message=f"Hook {result.name} failed with no specific details",
            stage="comprehensive",
        )

    def _determine_hook_issue_type(self, hook_name: str) -> IssueType:
        """Determine issue type from hook name.

        Args:
            hook_name: Name of the failed hook

        Returns:
            IssueType classification based on hook name
        """
        formatting_hooks = {
            "trailing-whitespace",
            "end-of-file-fixer",
            "ruff-format",
            "ruff-check",
        }

        if hook_name == "validate-regex-patterns":
            return IssueType.REGEX_VALIDATION

        return (
            IssueType.FORMATTING
            if hook_name in formatting_hooks
            else IssueType.TYPE_ERROR
        )

    def _fallback_to_session_tracker(self, session: t.Any) -> tuple[list[Issue], int]:
        """Fallback to session tracker when hook manager fails.

        Args:
            session: SessionCoordinator instance with session_tracker

        Returns:
            Tuple of (list of issues, count of failed hooks)
        """
        issues: list[Issue] = []
        hook_count = 0

        if not session.session_tracker:
            return issues, hook_count

        for task_id, task_data in session.session_tracker.tasks.items():
            if self._is_failed_hook_task(task_data, task_id):
                hook_count += 1
                hook_issues = self._process_hook_failure(task_id, task_data)
                issues.extend(hook_issues)

        return issues, hook_count

    def _is_failed_hook_task(self, task_data: t.Any, task_id: str) -> bool:
        """Check if a task is a failed hook task.

        Args:
            task_data: Task data from session tracker
            task_id: Task identifier

        Returns:
            True if task is a failed hook task
        """
        return task_data.status == "failed" and task_id in (
            "fast_hooks",
            "comprehensive_hooks",
        )

    def _process_hook_failure(self, task_id: str, task_data: t.Any) -> list[Issue]:
        """Process a hook failure from session tracker.

        Args:
            task_id: Task identifier
            task_data: Failed task data

        Returns:
            List of issues parsed from the hook failure
        """
        error_msg = getattr(task_data, "error_message", "Unknown error")
        specific_issues = self._parse_hook_error_details(task_id, error_msg)

        if specific_issues:
            return specific_issues

        return [self._create_generic_hook_issue(task_id, error_msg)]

    def _create_generic_hook_issue(self, task_id: str, error_msg: str) -> Issue:
        """Create a generic issue from a hook task failure.

        Args:
            task_id: Task identifier
            error_msg: Error message from the task

        Returns:
            Generic Issue object for the hook failure
        """
        issue_type = IssueType.FORMATTING if "fast" in task_id else IssueType.TYPE_ERROR
        return Issue(
            id=f"hook_failure_{task_id}",
            type=issue_type,
            severity=Priority.MEDIUM,
            message=error_msg,
            stage=task_id.replace("_hooks", ""),
        )

    def _parse_hook_error_details(self, task_id: str, error_msg: str) -> list[Issue]:
        """Parse specific error details from hook error messages.

        Args:
            task_id: Task identifier
            error_msg: Error message to parse

        Returns:
            List of specific issues, or empty list if no patterns match
        """
        issues: list[Issue] = []

        if task_id == "comprehensive_hooks":
            issues.extend(self._parse_comprehensive_hook_errors(error_msg))
        elif task_id == "fast_hooks":
            issues.append(self._create_fast_hook_issue())

        return issues

    def _parse_comprehensive_hook_errors(self, error_msg: str) -> list[Issue]:
        """Parse comprehensive hook errors using pattern checkers.

        Args:
            error_msg: Error message from comprehensive hooks

        Returns:
            List of specific issues found in the error message
        """
        error_lower = error_msg.lower()
        error_checkers = self._get_comprehensive_error_checkers()

        issues = []
        for check_func in error_checkers:
            issue = check_func(error_lower)
            if issue:
                issues.append(issue)

        return issues

    def _get_comprehensive_error_checkers(
        self,
    ) -> list[t.Callable[[str], Issue | None]]:
        """Get list of error checking functions for comprehensive hooks.

        Returns:
            List of checker functions that return Issue if pattern matches
        """
        return [
            self._check_complexity_error,
            self._check_type_error,
            self._check_security_error,
            self._check_performance_error,
            self._check_dead_code_error,
            self._check_regex_validation_error,
        ]

    def _check_complexity_error(self, error_lower: str) -> Issue | None:
        """Check for complexity violation errors.

        Args:
            error_lower: Lowercase error message

        Returns:
            Issue if complexity error detected, None otherwise
        """
        if "complexipy" in error_lower or "c901" in error_lower:
            return Issue(
                id="complexity_violation",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Code complexity violation detected",
                stage="comprehensive",
            )
        return None

    def _check_type_error(self, error_lower: str) -> Issue | None:
        """Check for type checking errors.

        Args:
            error_lower: Lowercase error message

        Returns:
            Issue if type error detected, None otherwise
        """
        if "pyright" in error_lower:
            return Issue(
                id="pyright_type_error",
                type=IssueType.TYPE_ERROR,
                severity=Priority.HIGH,
                message="Type checking errors detected by pyright",
                stage="comprehensive",
            )
        return None

    def _check_security_error(self, error_lower: str) -> Issue | None:
        """Check for security vulnerability errors.

        Args:
            error_lower: Lowercase error message

        Returns:
            Issue if security error detected, None otherwise
        """
        if "bandit" in error_lower:
            return Issue(
                id="bandit_security_issue",
                type=IssueType.SECURITY,
                severity=Priority.HIGH,
                message="Security vulnerabilities detected by bandit",
                stage="comprehensive",
            )
        return None

    def _check_performance_error(self, error_lower: str) -> Issue | None:
        """Check for performance/quality errors.

        Args:
            error_lower: Lowercase error message

        Returns:
            Issue if performance error detected, None otherwise
        """
        if "refurb" in error_lower:
            return Issue(
                id="refurb_quality_issue",
                type=IssueType.PERFORMANCE,
                severity=Priority.MEDIUM,
                message="Code quality issues detected by refurb",
                stage="comprehensive",
            )
        return None

    def _check_dead_code_error(self, error_lower: str) -> Issue | None:
        """Check for dead code errors.

        Args:
            error_lower: Lowercase error message

        Returns:
            Issue if dead code detected, None otherwise
        """
        if "vulture" in error_lower:
            return Issue(
                id="vulture_dead_code",
                type=IssueType.DEAD_CODE,
                severity=Priority.MEDIUM,
                message="Dead code detected by vulture",
                stage="comprehensive",
            )
        return None

    def _check_regex_validation_error(self, error_lower: str) -> Issue | None:
        """Check for regex validation errors.

        Args:
            error_lower: Lowercase error message

        Returns:
            Issue if regex validation error detected, None otherwise
        """
        regex_keywords = ("raw regex", "regex pattern", r"\g<", "replacement")
        if "validate-regex-patterns" in error_lower or any(
            keyword in error_lower for keyword in regex_keywords
        ):
            return Issue(
                id="regex_validation_failure",
                type=IssueType.REGEX_VALIDATION,
                severity=Priority.HIGH,
                message="Unsafe regex patterns detected by validate-regex-patterns",
                stage="fast",
            )
        return None

    def _create_fast_hook_issue(self) -> Issue:
        """Create an issue for fast hook formatting failures.

        Returns:
            Issue object for fast hook formatting failure
        """
        return Issue(
            id="fast_hooks_formatting",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Code formatting issues detected",
            stage="fast",
        )

    def _parse_issues_for_agents(self, issue_strings: list[str]) -> list[Issue]:
        """Parse issue strings into classified Issue objects.

        Args:
            issue_strings: List of issue description strings

        Returns:
            List of classified Issue objects
        """
        issues: list[Issue] = []

        for i, issue_str in enumerate(issue_strings):
            issue_type, priority = self._classify_issue(issue_str)

            issue = Issue(
                id=f"parsed_issue_{i}",
                type=issue_type,
                severity=priority,
                message=issue_str.strip(),
                stage="comprehensive",
            )
            issues.append(issue)

        return issues

    def _classify_issue(self, issue_str: str) -> tuple[IssueType, Priority]:
        """Classify an issue string by type and priority.

        Args:
            issue_str: Issue description string

        Returns:
            Tuple of (IssueType, Priority) based on content analysis
        """
        issue_lower = issue_str.lower()

        # Check high priority issues first
        high_priority_result = self._check_high_priority_issues(issue_lower)
        if high_priority_result:
            return high_priority_result

        # Check medium priority issues
        medium_priority_result = self._check_medium_priority_issues(issue_lower)
        if medium_priority_result:
            return medium_priority_result

        # Default to formatting issue
        return IssueType.FORMATTING, Priority.MEDIUM

    def _check_high_priority_issues(
        self, issue_lower: str
    ) -> tuple[IssueType, Priority] | None:
        """Check for high priority issue types.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            Tuple of issue type and priority if found, None otherwise
        """
        high_priority_checks = [
            (self._is_type_error, IssueType.TYPE_ERROR),
            (self._is_security_issue, IssueType.SECURITY),
            (self._is_complexity_issue, IssueType.COMPLEXITY),
            (self._is_regex_validation_issue, IssueType.REGEX_VALIDATION),
        ]

        for check_func, issue_type in high_priority_checks:
            if check_func(issue_lower):
                return issue_type, Priority.HIGH

        return None

    def _check_medium_priority_issues(
        self, issue_lower: str
    ) -> tuple[IssueType, Priority] | None:
        """Check for medium priority issue types.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            Tuple of issue type and priority if found, None otherwise
        """
        medium_priority_checks = [
            (self._is_dead_code_issue, IssueType.DEAD_CODE),
            (self._is_performance_issue, IssueType.PERFORMANCE),
            (self._is_import_error, IssueType.IMPORT_ERROR),
        ]

        for check_func, issue_type in medium_priority_checks:
            if check_func(issue_lower):
                return issue_type, Priority.MEDIUM

        return None

    def _is_type_error(self, issue_lower: str) -> bool:
        """Check if issue is a type error.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            True if type error pattern detected
        """
        return any(
            keyword in issue_lower for keyword in ("type", "annotation", "pyright")
        )

    def _is_security_issue(self, issue_lower: str) -> bool:
        """Check if issue is a security concern.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            True if security pattern detected
        """
        return any(
            keyword in issue_lower for keyword in ("security", "bandit", "hardcoded")
        )

    def _is_complexity_issue(self, issue_lower: str) -> bool:
        """Check if issue is a complexity violation.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            True if complexity pattern detected
        """
        return any(
            keyword in issue_lower
            for keyword in ("complexity", "complexipy", "c901", "too complex")
        )

    def _is_regex_validation_issue(self, issue_lower: str) -> bool:
        """Check if issue is a regex validation problem.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            True if regex validation pattern detected
        """
        return any(
            keyword in issue_lower
            for keyword in (
                "regex",
                "pattern",
                "validate-regex-patterns",
                r"\g<",
                "replacement",
            )
        )

    def _is_dead_code_issue(self, issue_lower: str) -> bool:
        """Check if issue is dead/unused code.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            True if dead code pattern detected
        """
        return any(keyword in issue_lower for keyword in ("unused", "dead", "vulture"))

    def _is_performance_issue(self, issue_lower: str) -> bool:
        """Check if issue is a performance concern.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            True if performance pattern detected
        """
        return any(
            keyword in issue_lower for keyword in ("performance", "refurb", "furb")
        )

    def _is_import_error(self, issue_lower: str) -> bool:
        """Check if issue is an import error.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            True if import error pattern detected
        """
        return any(keyword in issue_lower for keyword in ("import", "creosote"))

    def _log_failure_counts_if_debugging(
        self, test_count: int, hook_count: int, debug_enabled: bool
    ) -> None:
        """Log failure counts when debugging is enabled.

        Args:
            test_count: Number of test failures
            hook_count: Number of hook failures
            debug_enabled: Whether debug mode is enabled
        """
        if debug_enabled:
            self.debugger.log_test_failures(test_count)
            self.debugger.log_hook_failures(hook_count)


# Register with ACB dependency injection
depends.set(WorkflowIssueParser, WorkflowIssueParser)
